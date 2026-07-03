from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


UserRole = Literal["learner", "educator", "administrator"]


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=1)
    age: int = Field(..., gt=0)
    email: EmailStr
    password: str = Field(..., min_length=8)
    preferred_language: str = Field(..., min_length=1)
    education_level: str = Field(..., min_length=1)
    role: UserRole

    @field_validator("full_name", "preferred_language", "education_level")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Field must not be empty")
        return cleaned_value


class UserResponse(BaseModel):
    id: int
    full_name: str
    age: int
    email: EmailStr
    preferred_language: str
    education_level: str
    role: UserRole
    is_active: bool
    created_at: datetime
