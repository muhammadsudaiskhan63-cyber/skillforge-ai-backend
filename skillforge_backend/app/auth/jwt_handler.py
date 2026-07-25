from jose import jwt, JWTError
from datetime import datetime, timedelta

SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"


# ---------------- CREATE ACCESS TOKEN ----------------
def create_access_token(data: dict):
    token_data = data.copy()

    expire = datetime.utcnow() + timedelta(minutes=60)

    token_data.update({
        "exp": expire,
        "sub": data["sub"],
        "role": data["role"]   # <-- Add role to JWT
    })

    token = jwt.encode(
        token_data,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


# ---------------- VERIFY TOKEN ----------------
def verify_token(token: str):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:
        return None