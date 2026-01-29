from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from enum import Enum
import re


class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class MaritalStatus(str, Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"


class UserRegisterSchema(BaseModel):
    email: EmailStr = Field(..., max_length=254, alias="e-mail")
    password: str = Field(..., min_length=8, max_length=72)
    fullName: str = Field(..., min_length=2, max_length=200)
    age: Optional[int] = Field(None, ge=18, le=120)
    region: Optional[str] = Field(None, max_length=32)
    gender: Optional[Gender] = None
    maritalStatus: Optional[MaritalStatus] = None

    @validator('password')
    def validate_password(cls, v):
        if not any(char.isdigit() for char in v) or not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least 1 letter and 1 digit')
        return v

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "e-mail": "ivan@example.com",
                "password": "SecurePass123",
                "fullName": "Иван Иванов",
                "age": 20,
                "region": "RU-MOW",
                "gender": "MALE",
                "maritalStatus": "SINGLE"
            }
        }

class UserLoginSchema(BaseModel):
    email: EmailStr = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=72)