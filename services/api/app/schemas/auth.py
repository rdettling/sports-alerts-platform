from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class MagicLinkStartRequest(BaseModel):
    email: EmailStr


class MagicLinkStartResponse(BaseModel):
    message: str


class MagicLinkVerifyRequest(BaseModel):
    token: str = Field(min_length=20, max_length=1024)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
