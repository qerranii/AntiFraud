from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
import re
from db.session import get_async_session
from model.rule import FraudRule
from schemas.rules import FraudRuleCreate, FraudRuleUpdate, FraudRuleResponse, DslValidateRequest, DslValidateResponse
from utils.security import get_current_user
from model.user import User
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/api/v1/fraud-rules", tags=["Fraud Rules"])

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

@router.post("", response_model=FraudRuleResponse, status_code=201)
async def create_rule(
        request: Request,
        rule: FraudRuleCreate,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if user_role != "ADMIN":
        return get_error_response(403, "FORBIDDEN", "Forbidden", request)

    existing = await db.execute(select(FraudRule).where(FraudRule.name == rule.name))
    if existing.scalar_one_or_none():
        return get_error_response(409, "ALREADY_EXISTS", "Rule name already exists", request)

    new_rule = FraudRule(
        name=rule.name,
        description=rule.description,
        dsl_expression=rule.dslExpression,
        enabled=rule.enabled,
        priority=rule.priority
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    return FraudRuleResponse.from_orm_model(new_rule)


@router.get("", response_model=List[FraudRuleResponse])
async def list_rules(
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403)

    result = await db.execute(select(FraudRule).order_by(FraudRule.priority.asc()))
    rules = result.scalars().all()
    return [FraudRuleResponse.from_orm_model(r) for r in rules]


@router.get("/{id}", response_model=FraudRuleResponse)
async def get_rule(
        id: UUID,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403)

    result = await db.execute(select(FraudRule).where(FraudRule.id == id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Not Found")
    return FraudRuleResponse.from_orm_model(rule)


@router.put("/{id}", response_model=FraudRuleResponse)
async def update_rule(
        id: UUID,
        rule_update: FraudRuleUpdate,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403)

    result = await db.execute(select(FraudRule).where(FraudRule.id == id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404)

    if rule.name != rule_update.name:
        check = await db.execute(select(FraudRule).where(FraudRule.name == rule_update.name))
        if check.scalar_one_or_none():
            raise HTTPException(status_code=409)

    rule.name = rule_update.name
    rule.description = rule_update.description
    rule.dsl_expression = rule_update.dslExpression
    rule.enabled = rule_update.enabled
    rule.priority = rule_update.priority

    await db.commit()
    await db.refresh(rule)
    return FraudRuleResponse.from_orm_model(rule)


@router.delete("/{id}", status_code=204)
async def deactivate_rule(
        id: UUID,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403)

    result = await db.execute(select(FraudRule).where(FraudRule.id == id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404)

    rule.enabled = False
    await db.commit()
    return None


def normalize_dsl(expression: str) -> str:
    expr = expression.replace('(', ' ').replace(')', ' ')
    expr = re.sub(r'\s+', ' ', expr).strip()

    expr = re.sub(r'\band\b', 'AND', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bor\b', 'OR', expr, flags=re.IGNORECASE)

    return expr


@router.post("/validate", response_model=DslValidateResponse)
async def validate_rule_dsl(
        data: DslValidateRequest,
        current_user: User = Depends(get_current_user)
):
    is_valid = True
    errors = []

    normalized = normalize_dsl(data.dslExpression)

    return {
        "isValid": is_valid,
        "errors": errors,
        "normalizedExpression": normalized
    }