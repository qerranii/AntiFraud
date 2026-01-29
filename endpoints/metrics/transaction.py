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

router = APIRouter(prefix='/api/v1/stats', tags=['Statistics'])

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

@router.get("/transactions/timeseries")
async def get_timeseries(
        request: Request,
        from_date: Optional[datetime] = Query(None, alias="from"),
        to_date: Optional[datetime] = Query(None, alias="to"),
        group_by: str = Query("day", alias="groupBy"),
        channel: Optional[str] = None,
        tz: str = Query("UTC", alias="timezone"),
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise get_error_response(403, "ACCESS_DENIED", "Admin only", request)

    if not to_date: to_date = datetime.now(dt_timezone.utc)
    if not from_date: from_date = to_date - timedelta(days=7)

    days = (to_date - from_date).days
    if group_by == "hour" and days > 7: raise get_error_response(400, "LIMIT", "Max 7d for hour", request)
    if group_by == "day" and days > 90: raise get_error_response(400, "LIMIT", "Max 90d for day", request)
    if group_by == "week" and days > 365: raise get_error_response(400, "LIMIT", "Max 1y for week", request)

    bucket = func.date_trunc(group_by, func.timezone(tz, Transaction.timestamp))

    query = select(
        bucket.label("bucketStart"),
        func.count(Transaction.id).label("txCount"),
        func.coalesce(func.sum(Transaction.amount), 0).label("gmv"),
        func.count(Transaction.id).filter(func.upper(Transaction.status) == "APPROVED").label("ok"),
        func.count(Transaction.id).filter(func.upper(Transaction.status) == "DECLINED").label("fail")
    ).where(Transaction.timestamp >= from_date, Transaction.timestamp < to_date)

    if channel:
        query = query.where(Transaction.channel == channel)

    res = await db.execute(query.group_by("bucketStart").order_by("bucketStart"))

    points = []
    for r in res.all():
        points.append({
            "bucketStart": r.bucketStart.isoformat().replace("+00:00", "Z"),
            "txCount": r.txCount,
            "gmv": float(r.gmv),
            "approvalRate": round(r.ok / r.txCount, 2) if r.txCount > 0 else 0,
            "declineRate": round(r.fail / r.txCount, 2) if r.txCount > 0 else 0
        })
    return {"points": points}
