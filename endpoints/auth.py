from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.session import get_async_session
from model.user import User
from schemas.auth import UserRegisterSchema, UserLoginSchema
from utils.security import hash_password, create_access_token, verify_password
from uuid import uuid4
from typing import Dict, Any

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post('/register', status_code=status.HTTP_201_CREATED)
async def register_user(
        user_in: UserRegisterSchema,
        db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already taken"
        )

    new_user = User(
        id=str(uuid4()),
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.fullName,
        age=user_in.age,
        region=user_in.region,
        gender=user_in.gender.value if user_in.gender else None,
        marital_status=user_in.maritalStatus.value if user_in.maritalStatus else None,
        role="USER",
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_access_token(data={"sub": str(new_user.id), "role": new_user.role})

    return {
        "accessToken": token,
        "expiresIn": 3600,
        "user": {
            "id": str(new_user.id),
            "email": new_user.email,
            "fullName": new_user.full_name,
            "age": new_user.age,
            "region": new_user.region,
            "gender": new_user.gender,
            "maritalStatus": new_user.marital_status,
            "role": new_user.role,
            "isActive": new_user.is_active,
            "createdAt": new_user.created_at.isoformat() if new_user.created_at else None,
            "updatedAt": new_user.updated_at.isoformat() if new_user.updated_at else None
        }
    }

@router.post('/login', status_code=status.HTTP_200_OK)
async def login_user(
    user_data: UserLoginSchema,
    db: AsyncSession = Depends(get_async_session)
):
    query = select(User).where(User.email == user_data.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="deactivated"
        )

    token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return {
        "accessToken": token,
        "expiresIn": 3600,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "fullName": user.full_name,
            "age": user.age,
            "region": user.region,
            "gender": user.gender,
            "maritalStatus": user.marital_status,
            "role": user.role,
            "isActive": user.is_active,
            "createdAt": user.created_at.isoformat() if user.created_at else None,
            "updatedAt": user.updated_at.isoformat() if user.updated_at else None
        }
    }