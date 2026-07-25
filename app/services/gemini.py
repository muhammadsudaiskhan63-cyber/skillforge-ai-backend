import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise Exception("GEMINI_API_KEY not found in .env file")

genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-2.5-flash")


def analyze_resume(resume_text):
    prompt = f"""
You are an ATS Resume Analyzer.

Analyze the resume below.

Return ONLY valid JSON.

Use exactly this format:

{{
    "resume_score": 0,
    "skills_found": [],
    "missing_skills": [],
    "suggestions": []
}}

Rules:
- resume_score must be a number between 0 and 100.
- skills_found must be an array.
- missing_skills must be an array.
- suggestions must be an array.
- Do NOT write explanations.
- Do NOT use markdown.
- Return ONLY JSON.

Resume:

{resume_text}
"""

    response = model.generate_content(prompt)

    return response.text