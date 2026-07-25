from fastapi import APIRouter, UploadFile, File
from app.services.gemini import analyze_resume
import fitz
import os

router = APIRouter()

@router.post("/parse-resume")
async def parse_resume(file: UploadFile = File(...)):

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

    return {
        "message": "Resume analyzed successfully!",
        "resume_text": text,
        "ai_analysis": ai_result
    }