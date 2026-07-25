from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from app.auth.jwt_bearer import get_current_user, get_current_admin
from app.services.gemini import analyze_resume
from app.database.connection import connection, cursor
import fitz
import os
import json

router = APIRouter()


class JobApplication(BaseModel):
    full_name: str
    email: str
    phone: str
    cover_letter: str
    job_title: str
    company: str


# ======================================================
# PARSE RESUME
# ======================================================

@router.post("/parse-resume")
async def parse_resume(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    try:
        email = current_user["sub"]

        upload_folder = "uploads"
        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(upload_folder, file.filename)

        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        pdf = fitz.open(file_path)

        resume_text = ""

        for page in pdf:
            resume_text += page.get_text()

        pdf.close()

        ai_result = analyze_resume(resume_text)

        try:
            ai_result = json.loads(ai_result)
        except Exception:
            ai_result = {
                "resume_score": 0,
                "skills_found": [],
                "missing_skills": [],
                "suggestions": ["AI returned invalid JSON"]
            }

        query = """
        INSERT INTO resume_analysis
        (
            user_email,
            resume_score,
            skills_found,
            missing_skills,
            suggestions
        )
        VALUES (%s,%s,%s,%s,%s)
        """

        values = (
            email,
            ai_result.get("resume_score", 0),
            ", ".join(ai_result.get("skills_found", [])),
            ", ".join(ai_result.get("missing_skills", [])),
            ", ".join(ai_result.get("suggestions", []))
        )

        cursor.execute(query, values)
        connection.commit()

        return {
            "success": True,
            "message": "Resume analyzed successfully!",
            "analysis": ai_result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ======================================================
# MY ANALYSIS
# ======================================================

@router.get("/my-analysis")
def my_analysis(
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    query = """
    SELECT *
    FROM resume_analysis
    WHERE user_email=%s
    ORDER BY created_at DESC
    """

    cursor.execute(query, (email,))
    analyses = cursor.fetchall()

    return {
        "success": True,
        "resume_history": analyses
    }


# ======================================================
# DELETE ANALYSIS
# ======================================================

@router.delete("/delete-analysis/{analysis_id}")
def delete_analysis(
    analysis_id: int,
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    cursor.execute(
        """
        SELECT *
        FROM resume_analysis
        WHERE id=%s AND user_email=%s
        """,
        (analysis_id, email),
    )

    analysis = cursor.fetchone()

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    cursor.execute(
        """
        DELETE FROM resume_analysis
        WHERE id=%s
        """,
        (analysis_id,),
    )

    connection.commit()

    return {
        "success": True,
        "message": "Resume deleted successfully!"
    }
    # ======================================================
# DASHBOARD
# ======================================================

@router.get("/dashboard")
def dashboard(
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    # User Information
    cursor.execute(
        """
        SELECT full_name, phone, city, skills
        FROM users
        WHERE email=%s
        """,
        (email,),
    )

    user = cursor.fetchone()

    if user:
        user_name = user[0]
        phone = user[1] or ""
        city = user[2] or ""
        skills = user[3] or ""
    else:
        user_name = "Unknown"
        phone = ""
        city = ""
        skills = ""

    # Total resumes
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM resume_analysis
        WHERE user_email=%s
        """,
        (email,),
    )

    total_resumes = cursor.fetchone()[0]

    # Average score
    cursor.execute(
        """
        SELECT AVG(resume_score)
        FROM resume_analysis
        WHERE user_email=%s
        """,
        (email,),
    )

    average_score = cursor.fetchone()[0] or 0

    # Latest resume score
    cursor.execute(
        """
        SELECT resume_score
        FROM resume_analysis
        WHERE user_email=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email,),
    )

    latest = cursor.fetchone()

    latest_resume_score = latest[0] if latest else 0

    return {
        "success": True,
        "user_name": user_name,
        "logged_in_user": email,
        "phone": phone,
        "city": city,
        "skills": skills,
        "total_resumes": total_resumes,
        "average_score": round(average_score, 2),
        "latest_resume_score": latest_resume_score,
    }


# ======================================================
# JOB RECOMMENDATIONS
# ======================================================

@router.get("/job-recommendations")
def job_recommendations(
    current_user=Depends(get_current_user)
):

    cursor.execute(
        """
        SELECT
            id,
            job_title,
            required_skills,
            company_name,
            salary,
            location
        FROM jobs
        """
    )

    jobs = cursor.fetchall()

    job_list = []

    for job in jobs:
        job_list.append({
            "id": job[0],
            "job_title": job[1],
            "required_skills": job[2],
            "company_name": job[3],
            "salary": job[4],
            "location": job[5]
        })

    return {
        "success": True,
        "jobs": job_list
    }


# ======================================================
# RECOMMENDED JOBS
# ======================================================

@router.get("/recommended-jobs")
def recommended_jobs(
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    cursor.execute(
        """
        SELECT skills_found
        FROM resume_analysis
        WHERE user_email=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email,),
    )

    resume = cursor.fetchone()

    if resume is None:
        return {
            "success": True,
            "recommended_jobs": []
        }

    user_skills = [
        skill.strip().lower()
        for skill in resume[0].split(",")
        if skill.strip()
    ]

    cursor.execute(
        """
        SELECT *
        FROM jobs
        """
    )

    jobs = cursor.fetchall()

    matched_jobs = []

    for job in jobs:

        required_skills = job[2].lower()

        score = 0

        for skill in user_skills:
            if skill in required_skills:
                score += 1

        if score > 0:
            matched_jobs.append({
                "job_title": job[1],
                "company": job[3],
                "salary": job[4],
                "location": job[5],
                "match_score": score
            })

    matched_jobs.sort(
        key=lambda x: x["match_score"],
        reverse=True,
    )

    return {
        "success": True,
        "user": email,
        "recommended_jobs": matched_jobs
    }
    # ======================================================
# ADMIN - ALL ANALYSES
# ======================================================

@router.get("/admin/all-analyses")
def admin_all_analyses(
    current_admin=Depends(get_current_admin)
):

    cursor.execute(
        """
        SELECT *
        FROM resume_analysis
        ORDER BY created_at DESC
        """
    )

    analyses = cursor.fetchall()

    return {
        "success": True,
        "admin": current_admin["sub"],
        "total_records": len(analyses),
        "analyses": analyses
    }


# ======================================================
# APPLY JOB
# ======================================================

@router.post("/apply-job")
def apply_job(
    application: JobApplication,
    current_user=Depends(get_current_user)
):

    try:

        query = """
        INSERT INTO job_applications
        (
            user_email,
            job_title,
            company,
            full_name,
            email,
            phone,
            cover_letter
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """

        values = (
            current_user["sub"],
            application.job_title,
            application.company,
            application.full_name,
            application.email,
            application.phone,
            application.cover_letter,
        )

        cursor.execute(query, values)
        connection.commit()

        return {
            "success": True,
            "message": "Application submitted successfully!"
        }

    except Exception as e:
        connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ======================================================
# MY APPLICATIONS
# ======================================================

@router.get("/my-applications")
def my_applications(
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    cursor.execute(
        """
        SELECT
            id,
            job_title,
            company,
            status,
            applied_at
        FROM job_applications
        WHERE user_email=%s
        ORDER BY applied_at DESC
        """,
        (email,),
    )

    applications = cursor.fetchall()

    return {
        "success": True,
        "user": email,
        "applications": applications
    }


# ======================================================
# HEALTH CHECK
# ======================================================

@router.get("/health")
def health():

    return {
        "status": "OK",
        "message": "SkillForge AI Backend is running successfully."
    }