from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, distinct, cast, Float, extract
from typing import Optional, List
from datetime import datetime, timezone as dt_timezone, timedelta
from uuid import UUID, uuid4

from db.session import get_async_session
from model.transactions import Transaction, RuleResult
from model.rule import FraudRule
from model.user import User
from utils.security import get_current_user

router = APIRouter(prefix="/api/v1/stats", tags=["Statistics"])

def get_error_response(status_code: int, code: str, message: str, request: Request):
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "traceId": str(uuid4()),
            "timestamp": datetime.now(dt_timezone.utc).isoformat().replace("+00:00", "Z"),
            "path": request.url.path
        }
    )


def get_error_response(status_code: int, code: str, message: str, request: Request):
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "traceId": str(uuid4()),
            "timestamp": datetime.now(dt_timezone.utc).isoformat().replace("+00:00", "Z"),
            "path": request.url.path
        }
    )

@router.get("/rules/matches")
async def get_rule_stats(
        request: Request,
        from_date: Optional[datetime] = Query(None, alias="from"),
        to_date: Optional[datetime] = Query(None, alias="to"),
        top: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN": raise get_error_response(403, "DENIED", "Admin only", request)
    if not to_date: to_date = datetime.now(dt_timezone.utc)
    if not from_date: from_date = to_date - timedelta(days=30)

    total_declined_q = select(func.count(Transaction.id)).where(
        Transaction.timestamp >= from_date,
        Transaction.timestamp < to_date,
        func.upper(Transaction.status) == "DECLINED"
    )
    total_declined = (await db.execute(total_declined_q)).scalar() or 0

    query = select(
        RuleResult.rule_id.label("ruleId"),
        RuleResult.rule_name.label("ruleName"),
        func.count(RuleResult.id).label("matches"),
        func.count(distinct(Transaction.user_id)).label("uniqueUsers"),
        func.count(distinct(Transaction.merchant_id)).label("uniqueMerchants")
    ).join(Transaction, RuleResult.transaction_id == Transaction.id) \
        .where(Transaction.timestamp >= from_date, Transaction.timestamp < to_date, RuleResult.matched == True) \
        .group_by(RuleResult.rule_id, RuleResult.rule_name).order_by(desc("matches")).limit(top)

    res = await db.execute(query)
    items = []
    for r in res.all():
        items.append({
            "ruleId": str(r.ruleId),
            "ruleName": r.ruleName,
            "matches": r.matches,
            "uniqueUsers": r.uniqueUsers,
            "uniqueMerchants": r.uniqueMerchants,
            "shareOfDeclines": round(r.matches / total_declined, 2) if total_declined > 0 else 0
        })
    return {"items": items}


@router.get("/merchants/risk")
async def get_merchant_risk(
        request: Request,
        from_date: Optional[datetime] = Query(None, alias="from"),
        to_date: Optional[datetime] = Query(None, alias="to"),
        merchantCategoryCode: Optional[str] = None,
        top: int = Query(50, ge=1, le=200),
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN": raise get_error_response(403, "DENIED", "Admin only", request)
    if not to_date: to_date = datetime.now(dt_timezone.utc)
    if not from_date: from_date = to_date - timedelta(days=30)

    query = select(
        Transaction.merchant_id.label("merchantId"),
        Transaction.mcc.label("merchantCategoryCode"),
        func.count(Transaction.id).label("txCount"),
        func.coalesce(func.sum(Transaction.amount), 0).label("gmv"),
        (cast(func.count(Transaction.id).filter(func.upper(Transaction.status) == "DECLINED"), Float) /
         func.nullif(func.count(Transaction.id), 0)).label("declineRate")
    ).where(Transaction.timestamp >= from_date, Transaction.timestamp < to_date)

    if merchantCategoryCode:
        query = query.where(Transaction.mcc == merchantCategoryCode)

    res = await db.execute(
        query.group_by(Transaction.merchant_id, Transaction.mcc).order_by(desc("declineRate")).limit(top))

    return {"items": [
        {
            "merchantId": r.merchantId,
            "merchantCategoryCode": r.merchantCategoryCode,
            "txCount": r.txCount,
            "gmv": float(r.gmv),
            "declineRate": round(float(r.declineRate or 0), 2)
        } for r in res.all()
    ]}

