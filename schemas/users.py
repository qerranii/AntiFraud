from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

class Role(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"

class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"

class MaritalStatus(str, Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"

class UserResponseSchema(BaseModel):
    id: UUID
    email: str
    fullName: str
    age: Optional[int]
    region: Optional[str]
    gender: Optional[Gender]
    maritalStatus: Optional[MaritalStatus]
    role: Role
    isActive: bool
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    items: List[UserResponseSchema]
    total: int
    page: int
    size: int

class UserCreateSchema(BaseModel):
    email: EmailStr = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=72)
    fullName: str = Field(..., min_length=2, max_length=200)
    role: Role = Role.USER
    age: Optional[int] = Field(None, ge=18, le=120)
    region: Optional[str] = Field(None, max_length=32)
    gender: Optional[Gender] = None
    maritalStatus: Optional[MaritalStatus] = None

    @validator('password')
    def validate_password(cls, v):
        if not any(char.isdigit() for char in v) or not any(char.isalpha() for char in v):
            raise ValueError('Password must contain')
        return v

class UserUpdateSchema(BaseModel):
    fullName: str = Field(..., min_length=2, max_length=200)
    age: Optional[int] = Field(None, ge=18, le=120)
    region: Optional[str] = Field(None, max_length=32)
    gender: Optional[Gender] = None
    maritalStatus: Optional[MaritalStatus] = None