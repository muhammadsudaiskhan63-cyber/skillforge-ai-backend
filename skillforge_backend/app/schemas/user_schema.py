from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    city: str
    skills: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class ForgotPassword(BaseModel):
    email: EmailStr


class VerifyOTP(BaseModel):
    email: EmailStr
    otp: int


class ResetPassword(BaseModel):
    email: EmailStr
    otp: int
    new_password: str