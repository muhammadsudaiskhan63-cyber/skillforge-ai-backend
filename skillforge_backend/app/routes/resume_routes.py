from fastapi import APIRouter, UploadFile, File, Form, Depends
from pydantic import BaseModel
from app.auth.jwt_bearer import get_current_user,get_current_admin
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


# ---------------- PARSE RESUME ----------------
@router.post("/parse-resume")
async def parse_resume(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    
    email = current_user["sub"]

    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    pdf = fitz.open(file_path)

    text = ""

    for page in pdf:
        text += page.get_text()

    pdf.close()

    ai_result = analyze_resume(text)

    try:
        ai_result = json.loads(ai_result)
    except:
        ai_result = {
            "error": "Invalid JSON returned by Gemini",
            "raw_response": ai_result
        }

    query = """
    INSERT INTO resume_analysis
    (user_email, resume_score, skills_found, missing_skills, suggestions)
    VALUES (%s, %s, %s, %s, %s)
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
        "message": "Resume analyzed successfully!",
        "logged_in_user": current_user,
        "resume_text": text,
        "ai_analysis": ai_result
    }


# ---------------- MY ANALYSIS ----------------
@router.get(
    "/my-analysis",
    dependencies=[Depends(get_current_user)]
)
def my_analysis(
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    query = """
    SELECT *
    FROM resume_analysis
    WHERE user_email = %s
    """

    cursor.execute(query, (email,))
    analyses = cursor.fetchall()

    return {
        "logged_in_user": email,
        "resume_history": analyses
    }


# ---------------- DELETE ANALYSIS ----------------
@router.delete(
    "/delete-analysis/{analysis_id}",
    dependencies=[Depends(get_current_user)]
)
def delete_analysis(
    analysis_id: int,
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    # Check if the resume belongs to the logged-in user
    check_query = """
    SELECT *
    FROM resume_analysis
    WHERE id = %s AND user_email = %s
    """

    cursor.execute(check_query, (analysis_id, email))
    analysis = cursor.fetchone()

    if analysis is None:
        return {
            "message": "Resume not found!"
        }

    # Delete the resume
    delete_query = """
    DELETE FROM resume_analysis
    WHERE id = %s
    """

    cursor.execute(delete_query, (analysis_id,))
    connection.commit()

    return {
        "message": "Resume deleted successfully!"
    }
 # ---------------- DASHBOARD ----------------
@router.get(
    "/dashboard",
    dependencies=[Depends(get_current_user)]
)
def dashboard(
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    # Get user information
    user_query = """
    SELECT
        full_name,
        phone,
        city,
        skills
    FROM users
    WHERE email = %s
    """

    cursor.execute(user_query, (email,))
    user = cursor.fetchone()

    if user:
        user_name = user[0]
        phone = user[1] if user[1] else ""
        city = user[2] if user[2] else ""
        skills = user[3] if user[3] else ""
    else:
        user_name = "Unknown"
        phone = ""
        city = ""
        skills = ""

    # Total resumes
    count_query = """
    SELECT COUNT(*)
    FROM resume_analysis
    WHERE user_email = %s
    """

    cursor.execute(count_query, (email,))
    total_resumes = cursor.fetchone()[0]

    # Average score
    avg_query = """
    SELECT AVG(resume_score)
    FROM resume_analysis
    WHERE user_email = %s
    """

    cursor.execute(avg_query, (email,))
    average_score = cursor.fetchone()[0]

    if average_score is None:
        average_score = 0

    # Latest resume score
    latest_query = """
    SELECT resume_score
    FROM resume_analysis
    WHERE user_email = %s
    ORDER BY created_at DESC
    LIMIT 1
    """

    cursor.execute(latest_query, (email,))
    latest = cursor.fetchone()

    latest_resume_score = latest[0] if latest else 0

    return {
        "user_name": user_name,
        "logged_in_user": email,
        "phone": phone,
        "city": city,
        "skills": skills,
        "total_resumes": total_resumes,
        "average_score": round(average_score, 2),
        "latest_resume_score": latest_resume_score
    }
    # ---------------- JOB RECOMMENDATIONS ----------------
@router.get(
    "/job-recommendations",
    dependencies=[Depends(get_current_user)]
)
def job_recommendations(
    current_user=Depends(get_current_user)
):

    cursor.execute("""
        SELECT id,
               job_title,
               required_skills,
               company_name,
               salary,
               location
        FROM jobs
    """)

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
        "logged_in_user": current_user["sub"],
        "jobs": job_list
    }
@router.get("/recommended-jobs")
def recommended_jobs(
    current_user=Depends(get_current_user)
):
    email = current_user["sub"]

    # Get latest resume skills
    query = """
    SELECT skills_found
    FROM resume_analysis
    WHERE user_email = %s
    ORDER BY created_at DESC
    LIMIT 1
    """

    cursor.execute(query, (email,))
    resume = cursor.fetchone()

    if resume is None:
        return {
            "message": "No resume found!"
        }

    user_skills = resume[0].lower()

    # Get all jobs
    cursor.execute("SELECT * FROM jobs")
    jobs = cursor.fetchall()

    matched_jobs = []

    for job in jobs:
        required_skills = job[2].lower()

        score = 0

        for skill in user_skills.split(","):
            if skill.strip() in required_skills:
                score += 1

        if score > 0:
            matched_jobs.append({
                "job_title": job[1],
                "company": job[3],
                "location": job[5],
                "salary": job[4],
                "match_score": score
            })

    matched_jobs.sort(
        key=lambda x: x["match_score"],
        reverse=True
    )

    return {
        "user": email,
        "recommended_jobs": matched_jobs
    }    
    # ---------------- ADMIN ALL ANALYSES ----------------
@router.get("/admin/all-analyses")
def admin_all_analyses(
    current_admin=Depends(get_current_admin)
):

    query = """
    SELECT *
    FROM resume_analysis
    """

    cursor.execute(query)
    analyses = cursor.fetchall()

    return {
        "admin": current_admin["sub"],
        "total_records": len(analyses),
        "analyses": analyses
    }
    # ---------------- APPLY JOB ----------------
@router.post(
    "/apply-job",
    dependencies=[Depends(get_current_user)]
)
def apply_job(
    application: JobApplication,
    current_user=Depends(get_current_user)
):

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
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    values = (
        current_user["sub"],
        application.job_title,
        application.company,
        application.full_name,
        application.email,
        application.phone,
        application.cover_letter
    )

    cursor.execute(query, values)
    connection.commit()

    return {
        "message": "Application submitted successfully!"
    }
    # ---------------- MY APPLICATIONS ----------------
@router.get(
    "/my-applications",
    dependencies=[Depends(get_current_user)]
)
def my_applications(
    current_user=Depends(get_current_user)
):

    email = current_user["sub"]

    query = """
    SELECT id,
           job_title,
           company,
           status,
           applied_at
    FROM job_applications
    WHERE user_email = %s
    ORDER BY applied_at DESC
    """

    cursor.execute(query, (email,))
    applications = cursor.fetchall()

    return {
        "user": email,
        "applications": applications
    }