from fastapi import FastAPI
from app.routes.user_routes import router as user_router
from app.routes.resume_routes import router as resume_router
from app.routes.chat_routes import router as chat_router

app = FastAPI(
    title="SkillForge AI Backend",
    version="1.0.0"
)

# User APIs
app.include_router(
    user_router,
    tags=["Users"]
)

# Resume APIs
app.include_router(
    resume_router,
    tags=["Resume"]
)

# Chat APIs
app.include_router(
    chat_router,
    tags=["Chat"]
)