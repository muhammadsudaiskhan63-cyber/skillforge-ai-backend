from jose import jwt, JWTError
from datetime import datetime, timedelta

# =====================================================
# JWT CONFIGURATION
# =====================================================

SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# =====================================================
# CREATE ACCESS TOKEN
# =====================================================

def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({
        "exp": expire
    })

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt


# =====================================================
# VERIFY ACCESS TOKEN
# =====================================================

def verify_token(token: str):

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        email = payload.get("sub")
        role = payload.get("role")

        if email is None or role is None:
            return None

        return {
            "sub": email,
            "role": role
        }

    except JWTError:
        return None