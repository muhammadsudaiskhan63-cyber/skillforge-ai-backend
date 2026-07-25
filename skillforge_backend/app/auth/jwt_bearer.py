from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt_handler import verify_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    print("TOKEN RECEIVED:", credentials.credentials)

    payload = verify_token(credentials.credentials)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
            
            
            
        )

    return payload
    # ---------------- ADMIN AUTH ----------------
from fastapi import HTTPException


def get_current_admin(
    current_user=Depends(get_current_user)
):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Access denied! Admins only."
        )

    return current_user