import random
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status

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

# ======================================================
# REGISTER
# ======================================================

@router.post("/register")
def register(user: UserCreate):

    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (user.email,),
    )

    existing_user = cursor.fetchone()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists."
        )

    hashed_password = bcrypt.hashpw(
        user.password.encode(),
        bcrypt.gensalt()
    ).decode()

    cursor.execute(
        """
        INSERT INTO users
        (
            full_name,
            email,
            password,
            role
        )
        VALUES (%s,%s,%s,%s)
        """,
        (
            user.full_name,
            user.email,
            hashed_password,
            "student",
        ),
    )

    connection.commit()

    return {
        "success": True,
        "message": "User registered successfully."
    }


# ======================================================
# LOGIN
# ======================================================

@router.post("/login")
def login(user: UserLogin):

    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (user.email,),
    )

    existing_user = cursor.fetchone()

    if existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    stored_password = existing_user[3]

    if not bcrypt.checkpw(
        user.password.encode(),
        stored_password.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    access_token = create_access_token(
        {
            "sub": existing_user[2],
            "role": existing_user[4],
        }
    )

    return {
        "success": True,
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
    # ======================================================
# PROFILE
# ======================================================

@router.get("/profile")
def profile(current_user=Depends(get_current_user)):

    email = current_user["sub"]

    cursor.execute(
        """
        SELECT
            id,
            full_name,
            email,
            phone,
            city,
            skills,
            role
        FROM users
        WHERE email=%s
        """,
        (email,),
    )

    user = cursor.fetchone()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    return {
        "success": True,
        "profile": {
            "id": user[0],
            "full_name": user[1],
            "email": user[2],
            "phone": user[3],
            "city": user[4],
            "skills": user[5],
            "role": user[6],
        },
    }


# ======================================================
# UPDATE PROFILE
# ======================================================

@router.put("/update-profile")
def update_profile(
    user: UserUpdate,
    current_user=Depends(get_current_user)
):

    current_email = current_user["sub"]

    cursor.execute(
        """
        UPDATE users
        SET
            full_name=%s,
            email=%s,
            phone=%s,
            city=%s,
            skills=%s
        WHERE email=%s
        """,
        (
            user.full_name,
            user.email,
            user.phone,
            user.city,
            user.skills,
            current_email,
        ),
    )

    connection.commit()

    return {
        "success": True,
        "message": "Profile updated successfully."
    }


# ======================================================
# CHANGE PASSWORD
# ======================================================

@router.put("/change-password")
def change_password(
    password_data: ChangePassword,
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    cursor.execute(
        "SELECT password FROM users WHERE email=%s",
        (email,),
    )

    user = cursor.fetchone()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if not bcrypt.checkpw(
        password_data.old_password.encode(),
        user[0].encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Old password is incorrect."
        )

    hashed_password = bcrypt.hashpw(
        password_data.new_password.encode(),
        bcrypt.gensalt()
    ).decode()

    cursor.execute(
        """
        UPDATE users
        SET password=%s
        WHERE email=%s
        """,
        (
            hashed_password,
            email,
        ),
    )

    connection.commit()

    return {
        "success": True,
        "message": "Password changed successfully."
    }
    # ======================================================
# FORGOT PASSWORD
# ======================================================

@router.post("/forgot-password")
def forgot_password(user: ForgotPassword):

    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (user.email,),
    )

    existing_user = cursor.fetchone()

    if existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found."
        )

    otp = random.randint(100000, 999999)

    cursor.execute(
        """
        INSERT INTO password_reset_otp
        (email, otp)
        VALUES (%s,%s)
        """,
        (user.email, str(otp)),
    )

    connection.commit()

    return {
        "success": True,
        "message": "OTP generated successfully.",
        "otp": otp
    }


# ======================================================
# VERIFY OTP
# ======================================================

@router.post("/verify-otp")
def verify_otp(data: VerifyOTP):

    cursor.execute(
        """
        SELECT *
        FROM password_reset_otp
        WHERE email=%s AND otp=%s
        """,
        (data.email, data.otp),
    )

    otp_record = cursor.fetchone()

    if otp_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP."
        )

    return {
        "success": True,
        "message": "OTP verified successfully."
    }


# ======================================================
# RESET PASSWORD
# ======================================================

@router.post("/reset-password")
def reset_password(user: ResetPassword):

    cursor.execute(
        """
        SELECT *
        FROM password_reset_otp
        WHERE email=%s AND otp=%s
        """,
        (user.email, user.otp),
    )

    otp_record = cursor.fetchone()

    if otp_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP."
        )

    hashed_password = bcrypt.hashpw(
        user.new_password.encode(),
        bcrypt.gensalt()
    ).decode()

    cursor.execute(
        """
        UPDATE users
        SET password=%s
        WHERE email=%s
        """,
        (hashed_password, user.email),
    )

    cursor.execute(
        """
        DELETE FROM password_reset_otp
        WHERE email=%s
        """,
        (user.email,),
    )

    connection.commit()

    return {
        "success": True,
        "message": "Password reset successfully."
    }


# ======================================================
# ADMIN DASHBOARD
# ======================================================

@router.get("/admin/dashboard")
def admin_dashboard(
    current_admin=Depends(get_current_admin)
):

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM resume_analysis")
    total_resumes = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(resume_score) FROM resume_analysis")
    average_score = cursor.fetchone()[0] or 0

    return {
        "success": True,
        "admin": current_admin["sub"],
        "total_users": total_users,
        "total_resumes": total_resumes,
        "average_resume_score": round(average_score, 2),
    }


# ======================================================
# DELETE ANALYSIS (ADMIN)
# ======================================================

@router.delete("/admin/delete-analysis/{analysis_id}")
def delete_analysis(
    analysis_id: int,
    current_admin=Depends(get_current_admin)
):

    cursor.execute(
        "DELETE FROM resume_analysis WHERE id=%s",
        (analysis_id,),
    )

    connection.commit()

    return {
        "success": True,
        "message": "Resume analysis deleted successfully."
    }


# ======================================================
# ADMIN STATISTICS
# ======================================================

@router.get("/admin/statistics")
def admin_statistics(
    current_admin=Depends(get_current_admin)
):

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

    average = round(result[0], 2) if result[0] else 0
    highest = result[1] if result[1] else 0
    lowest = result[2] if result[2] else 0

    return {
        "success": True,
        "admin": current_admin["sub"],
        "total_users": total_users,
        "total_resume_analyses": total_analyses,
        "average_score": average,
        "highest_score": highest,
        "lowest_score": lowest,
    }