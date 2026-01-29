from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from uuid import UUID, uuid4
from db.session import get_async_session
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone

from model.user import User
from schemas.users import (
    UserUpdateSchema,
    UserCreateSchema,
    UserResponseSchema,
    UserListResponse,
    Role
)
from utils.security import get_current_user, hash_password, raise_formatted_error

router = APIRouter(prefix="/api/v1/users", tags=["users"])

def get_error_response(status_code: int, code: str, message: str, request: Request):
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "traceId": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "path": request.url.path
        }
    )

@router.get("/me", response_model=UserResponseSchema)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user.to_dict()


@router.put("/me", response_model=UserResponseSchema)
async def update_me(
        user_data: UserUpdateSchema,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    current_user.full_name = user_data.fullName
    current_user.age = user_data.age
    current_user.region = user_data.region
    current_user.gender = user_data.gender.value if user_data.gender else None
    current_user.marital_status = user_data.maritalStatus.value if user_data.maritalStatus else None

    await db.commit()
    await db.refresh(current_user)
    return current_user.to_dict()


@router.get("", response_model=UserListResponse)
async def get_all_users(
        request: Request,
        page: int = Query(0, ge=0),
        size: int = Query(20, ge=1, le=100),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    admin_val = Role.ADMIN.value if hasattr(Role.ADMIN, 'value') else Role.ADMIN

    if user_role != admin_val:
        return get_error_response(403, "FORBIDDEN", "Admin access required", request)

    count_res = await db.execute(select(func.count()).select_from(User))
    total = count_res.scalar()

    query = select(User).offset(page * size).limit(size)
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "items": [u.to_dict() for u in users],
        "total": total,
        "page": page,
        "size": size
    }


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponseSchema)
async def create_user(
        user_in: UserCreateSchema,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=403)

    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="already")

    new_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.fullName,
        age=user_in.age,
        region=user_in.region,
        gender=user_in.gender.value if user_in.gender else None,
        marital_status=user_in.maritalStatus.value if user_in.maritalStatus else None,
        role=user_in.role.value,
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user.to_dict()


@router.get("/{id}", response_model=UserResponseSchema)
async def get_user_by_id(
        id: UUID,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    admin_val = Role.ADMIN.value if hasattr(Role.ADMIN, 'value') else Role.ADMIN

    if user_role != admin_val and str(current_user.id) != str(id):
        return get_error_response(403, "FORBIDDEN", "Access denied", request)

    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()

    if not user:
        return get_error_response(404, "NOT_FOUND", "User not found", request)

    return user.to_dict()

@router.put("/{id}", response_model=UserResponseSchema)
async def update_user_by_id(
        request: Request,
        id: UUID,
        user_data: UserUpdateSchema,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    admin_val = Role.ADMIN.value if hasattr(Role.ADMIN, 'value') else Role.ADMIN

    if user_role != admin_val and str(current_user.id) != str(id):
        return get_error_response(403, "FORBIDDEN", "Access denied", request)

    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()

    if not user:
        return get_error_response(404, "NOT_FOUND", "User not found", request)

    user.full_name = user_data.fullName
    user.age = user_data.age
    user.region = user_data.region
    user.gender = user_data.gender.value if user_data.gender else None
    user.marital_status = user_data.maritalStatus.value if user_data.maritalStatus else None

    await db.commit()
    await db.refresh(user)
    return user.to_dict()

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
        id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=403)

    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="not found")

    user.is_active = False
    await db.commit()
    return None