from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.jwt_bearer import get_current_user
from app.services.gemini import model

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    response = model.generate_content(request.message)

    return {
        "user": current_user["sub"],
        "reply": response.text,
    }