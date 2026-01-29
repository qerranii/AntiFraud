from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi.exceptions import RequestValidationError
from db.session import get_async_session
from model.transactions import Transaction, RuleResult
from model.rule import FraudRule
from model.user import User
from schemas.transactions import TransactionCreate, BatchTransactionRequest
from utils.security import get_current_user
from utils.dsl import evaluate_dsl

router = APIRouter(prefix="/api/v1/transactions", tags=["Transactions"])


async def _process_single_tx(db: AsyncSession, data: TransactionCreate, target_user: User):
    r_res = await db.execute(
        select(FraudRule).where(FraudRule.enabled == True).order_by(FraudRule.priority, FraudRule.id))
    rules = r_res.scalars().all()

    context = {
        "amount": data.amount,
        "currency": data.currency,
        "mcc": data.merchantCategoryCode,
        "merchantId": data.merchantId,
        "user": {"age": target_user.age, "region": target_user.region}
    }

    is_fraud = False
    rule_results = []
    for r in rules:
        matched = False
        try:
            matched = evaluate_dsl(r.dsl_expression, context)
        except:
            matched = False

        if matched:
            is_fraud = True
        rule_results.append(RuleResult(
            rule_id=r.id, rule_name=r.name, matched=matched,
            priority=r.priority, description=f"Rule {r.name} matched={matched}"
        ))

    new_tx = Transaction(
        user_id=target_user.id, amount=data.amount, currency=data.currency,
        status="DECLINED" if is_fraud else "APPROVED", is_fraud=is_fraud,
        timestamp=data.timestamp.replace(tzinfo=None),
        merchant_id=data.merchantId, mcc=data.merchantCategoryCode,
        ip_address=data.ipAddress, device_id=data.deviceId, channel=data.channel,
        location=data.location.model_dump() if data.location else None,
        metadata_json=data.metadata
    )
    db.add(new_tx)
    await db.flush()

    for rr in rule_results:
        rr.transaction_id = new_tx.id
        db.add(rr)

    return new_tx, rule_results


def _format_tx_response(tx: Transaction, results: List[RuleResult]):
    return {
        "transaction": {
            "id": str(tx.id), "userId": str(tx.user_id), "amount": float(tx.amount),
            "currency": tx.currency, "status": tx.status, "isFraud": tx.is_fraud,
            "timestamp": tx.timestamp.isoformat() + "Z", "merchantId": tx.merchant_id,
            "merchantCategoryCode": tx.mcc, "ipAddress": tx.ip_address,
            "deviceId": tx.device_id, "channel": tx.channel,
            "location": tx.location, "metadata": tx.metadata_json,
            "createdAt": datetime.now(timezone.utc).isoformat()
        },
        "ruleResults": [
            {
                "ruleId": str(r.rule_id), "ruleName": r.rule_name,
                "priority": r.priority, "matched": r.matched, "description": r.description
            } for r in results
        ]
    }


@router.post("", status_code=201)
async def create_transaction(
        request: Request,
        data: TransactionCreate,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role == "ADMIN":
        if not data.userId:
            raise RequestValidationError([{
                "loc": ("body", "userId"),
                "msg": "userId is required for admin",
                "type": "missing"
            }])

        user_res = await db.execute(select(User).where(User.id == data.userId))
        target_user = user_res.scalar_one_or_none()

        if not target_user:
            raise HTTPException(
                status_code=404,
                detail={
                    "userId": str(data.userId),
                    "message": f"User with id {data.userId} not found"
                }
            )
    else:
        target_user = current_user

    if not target_user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    tx_obj, results_objs = await _process_single_tx(db, data, target_user)
    await db.commit()
    await db.refresh(tx_obj)
    return JSONResponse(status_code=201, content=jsonable_encoder(_format_tx_response(tx_obj, results_objs)))


@router.get("")
async def list_transactions(
        userId: Optional[UUID] = None,
        status: Optional[str] = None,
        isFraud: Optional[bool] = None,
        from_date: Optional[datetime] = Query(None, alias="from"),
        to_date: Optional[datetime] = Query(None, alias="to"),
        page: int = Query(0, ge=0),
        size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    query = select(Transaction)
    if current_user.role != "ADMIN":
        query = query.where(Transaction.user_id == current_user.id)
    elif userId:
        query = query.where(Transaction.user_id == userId)

    if status: query = query.where(Transaction.status == status)
    if isFraud is not None: query = query.where(Transaction.is_fraud == isFraud)
    if from_date: query = query.where(Transaction.timestamp >= from_date)
    if to_date: query = query.where(Transaction.timestamp <= to_date)

    query = query.order_by(desc(Transaction.timestamp)).offset(page * size).limit(size)
    res = await db.execute(query)
    items = res.scalars().all()
    return JSONResponse(content=jsonable_encoder([_format_tx_response(it, [])["transaction"] for it in items]))


@router.get("/{id}")
async def get_transaction(
        id: UUID,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Transaction).where(Transaction.id == id))
    tx = res.scalar_one_or_none()
    if not tx: raise HTTPException(404)
    if current_user.role != "ADMIN" and tx.user_id != current_user.id:
        raise HTTPException(403)

    res_rules = await db.execute(
        select(RuleResult).where(RuleResult.transaction_id == id).order_by(RuleResult.priority))
    rules = res_rules.scalars().all()
    return JSONResponse(content=jsonable_encoder(_format_tx_response(tx, rules)))


@router.post("/batch")
async def create_batch_transactions(
        payload: BatchTransactionRequest,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403)

    results = []
    has_error = False

    for idx, item_data in enumerate(payload.items):
        try:
            try:
                if isinstance(item_data, dict):
                    tx_data = TransactionCreate(**item_data)
                else:
                    raise ValueError("Invalid item format")
            except Exception as ve:
                has_error = True
                results.append({
                    "index": idx,
                    "error": {
                        "code": "VALIDATION_FAILED",
                        "message": str(ve)
                    }
                })
                continue

            async with db.begin_nested():
                user_id = tx_data.userId or current_user.id
                user_res = await db.execute(select(User).where(User.id == user_id))
                target_user = user_res.scalar_one_or_none()

                if not target_user:
                    has_error = True
                    results.append({
                        "index": idx,
                        "error": {
                            "code": "NOT_FOUND",
                            "message": f"User with id {user_id} not found",
                            "details": {"userId": str(user_id)}
                        }
                    })
                    continue

                tx_obj, rule_objs = await _process_single_tx(db, tx_data, target_user)
                await db.flush()

                results.append({
                    "index": idx,
                    "decision": _format_tx_response(tx_obj, rule_objs)
                })

        except Exception as e:
            has_error = True
            results.append({
                "index": idx,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)}
            })

    await db.commit()

    return JSONResponse(
        status_code=207 if has_error else 201,
        content=jsonable_encoder({"items": results})
    )