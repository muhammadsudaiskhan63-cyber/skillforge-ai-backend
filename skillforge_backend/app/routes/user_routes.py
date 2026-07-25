import random
import bcrypt
from fastapi import APIRouter, Depends


from app.auth.jwt_bearer import get_current_admin, get_current_user
from app.auth.jwt_handler import create_access_token
from app.database.connection import connection, cursor
from app.schemas.user_schema import (
    ChangePassword,
    ForgotPassword,
    ResetPassword,
    UserCreate,
    UserLogin,
    UserUpdate,
    VerifyOTP,
)

router = APIRouter()

# ---------------- REGISTER ----------------
@router.post("/register")
def register(user: UserCreate):
    # Check if email already exists
    check_query = "SELECT * FROM users WHERE email = %s"
    cursor.execute(check_query, (user.email,))
    existing_user = cursor.fetchone()

    if existing_user:
        return {"message": "Email already exists!"}

    # Hash password
    hashed_password = bcrypt.hashpw(
        user.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    # Insert new user
    query = """
    INSERT INTO users (full_name, email, password, role)
    VALUES (%s, %s, %s, %s)
    """
    values = (user.full_name, user.email, hashed_password, "student")

    cursor.execute(query, values)
    connection.commit()

    return {"message": "User registered successfully!"}


# ---------------- LOGIN ----------------
@router.post("/login")
def login(user: UserLogin):
    # Find user by email
    query = "SELECT * FROM users WHERE email = %s"
    cursor.execute(query, (user.email,))
    existing_user = cursor.fetchone()

    if not existing_user:
        return {"message": "Invalid email or password!"}

    # Password is in the 4th column (index 3)
    stored_password = existing_user[3]

    # Verify password
    if bcrypt.checkpw(user.password.encode("utf-8"), stored_password.encode("utf-8")):
        # Create JWT Token
        access_token = create_access_token(
            data={
                "sub": existing_user[2],  # Email
                "role": existing_user[4],  # User role (student/admin)
            }
        )

        return {
            "message": "Login successful!",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": existing_user[0],
                "full_name": existing_user[1],
                "email": existing_user[2],
                "role": existing_user[4],
            },
        }

    return {"message": "Invalid email or password!"}


# ---------------- PROFILE ----------------
@router.get("/profile")
def profile(current_user=Depends(get_current_user)):
    email = current_user["sub"]

    query = """
    SELECT id, full_name, email, role
    FROM users
    WHERE email = %s
    """
    cursor.execute(query, (email,))
    user = cursor.fetchone()

    return {
        "profile": {
            "id": user[0],
            "full_name": user[1],
            "email": user[2],
            "role": user[3],
        }
    }


# ---------------- UPDATE PROFILE ----------------
@router.put("/update-profile")
def update_profile(user: UserUpdate, current_user=Depends(get_current_user)):
    current_email = current_user["sub"]

    query = """
    UPDATE users
    SET full_name = %s,
        email = %s,
        phone = %s,
        city = %s,
        skills = %s
    WHERE email = %s
    """
    values = (user.full_name, user.email, user.phone, user.city, user.skills, current_email)

    cursor.execute(query, values)
    connection.commit()

    return {"message": "Profile updated successfully!"}


# ---------------- CHANGE PASSWORD ----------------
@router.put("/change-password")
def change_password(password_data: ChangePassword, current_user=Depends(get_current_user)):
    email = current_user["sub"]

    # Find the logged-in user
    query = """
    SELECT * FROM users
    WHERE email = %s
    """
    cursor.execute(query, (email,))
    user = cursor.fetchone()

    if user is None:
        return {"message": "User not found!"}

    # Check old password
    if not bcrypt.checkpw(password_data.old_password.encode(), user[3].encode()):
        return {"message": "Old password is incorrect!"}

    # Hash new password
    hashed_password = bcrypt.hashpw(password_data.new_password.encode(), bcrypt.gensalt()).decode()

    # Update password
    update_query = """
    UPDATE users
    SET password = %s
    WHERE email = %s
    """
    cursor.execute(update_query, (hashed_password, email))
    connection.commit()

    return {"message": "Password changed successfully!"}


# ---------------- FORGOT PASSWORD ----------------
@router.post("/forgot-password")
def forgot_password(user: ForgotPassword):
    query = """
    SELECT *
    FROM users
    WHERE email = %s
    """
    cursor.execute(query, (user.email,))
    existing_user = cursor.fetchone()

    if existing_user is None:
        return {"message": "Email not found!"}

    # Generate 6-digit OTP
    otp = random.randint(100000, 999999)
    query = """
    INSERT INTO password_reset_otp (email, otp)
    VALUES (%s, %s)
    """
    cursor.execute(query, (user.email, str(otp)))
    connection.commit()

    return {"message": "OTP generated successfully!", "email": user.email, "otp": otp}


# ---------------- VERIFY OTP ----------------
@router.post("/verify-otp")
def verify_otp(data: VerifyOTP):
    query = """
    SELECT *
    FROM password_reset_otp
    WHERE email = %s
    AND otp = %s
    """
    cursor.execute(query, (data.email, data.otp))
    otp_record = cursor.fetchone()

    if otp_record is None:
        return {"message": "Invalid OTP!"}

    return {"message": "OTP verified successfully!"}


# ---------------- RESET PASSWORD ----------------
@router.post("/reset-password")
def reset_password(user: ResetPassword):
    # Check if OTP exists
    query = """
    SELECT *
    FROM password_reset_otp
    WHERE email = %s AND otp = %s
    """
    cursor.execute(query, (user.email, user.otp))
    otp_record = cursor.fetchone()

    if otp_record is None:
        return {"message": "Invalid OTP!"}

    # Hash the new password
    hashed_password = bcrypt.hashpw(user.new_password.encode(), bcrypt.gensalt()).decode()

    # Update password
    update_query = """
    UPDATE users
    SET password = %s
    WHERE email = %s
    """
    cursor.execute(update_query, (hashed_password, user.email))

    # Delete used OTP
    delete_query = """
    DELETE FROM password_reset_otp
    WHERE email = %s
    """
    cursor.execute(delete_query, (user.email,))

    connection.commit()

    return {"message": "Password reset successfully!"}


# ---------------- ADMIN DASHBOARD ----------------
@router.get("/admin/dashboard")
def admin_dashboard(current_admin=Depends(get_current_admin)):
    # Total Users
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # Total Resumes
    cursor.execute("SELECT COUNT(*) FROM resume_analysis")
    total_resumes = cursor.fetchone()[0]

    # Average Resume Score
    cursor.execute("SELECT AVG(resume_score) FROM resume_analysis")
    average_score = cursor.fetchone()[0]

    return {
        "admin": current_admin["sub"],
        "total_users": total_users,
        "total_resumes": total_resumes,
        "average_resume_score": average_score,
    }


# ---------------- DELETE ANALYSIS (ADMIN) ----------------
@router.delete("/admin/delete-analysis/{analysis_id}")
def delete_analysis(analysis_id: int, current_admin=Depends(get_current_admin)):
    query = """
    DELETE FROM resume_analysis
    WHERE id = %s
    """
    cursor.execute(query, (analysis_id,))
    connection.commit()

    return {
        "admin": current_admin["sub"],
        "message": "Resume analysis deleted successfully!",
    }


# ---------------- ADMIN STATISTICS ----------------
@router.get("/admin/statistics")
def admin_statistics(current_admin=Depends(get_current_admin)):
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM resume_analysis")
    total_analyses = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT
            AVG(resume_score),
            MAX(resume_score),
            MIN(resume_score)
        FROM resume_analysis
    """
    )
    result = cursor.fetchone()

    return {
        "admin": current_admin["sub"],
        "total_users": total_users,
        "total_resume_analyses": total_analyses,
        "average_score": round(result[0], 2) if result[0] else 0,
        "highest_score": result[1] if result[1] else 0,
        "lowest_score": result[2] if result[2] else 0,
    }