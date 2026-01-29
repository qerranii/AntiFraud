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

@router.get("/users/{id}/risk-profile")
async def get_user_risk_profile(
        id: UUID,
        request: Request,
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN" and current_user.id != id:
        raise get_error_response(403, "ACCESS_DENIED", "Forbidden", request)

    now = datetime.now(dt_timezone.utc)

    q24 = select(
        func.count(Transaction.id).label("cnt"),
        func.coalesce(func.sum(Transaction.amount), 0).label("gmv"),
        func.count(distinct(Transaction.device_id)).label("devs"),
        func.count(distinct(Transaction.ip_address)).label("ips"),
        func.count(distinct(Transaction.location['city'].astext)).label("cities"),
        func.max(Transaction.timestamp).label("last")
    ).where(Transaction.user_id == id, Transaction.timestamp >= now - timedelta(hours=24))

    q30 = select(
        func.count(Transaction.id).label("total"),
        func.count(Transaction.id).filter(func.upper(Transaction.status) == "DECLINED").label("decs")
    ).where(Transaction.user_id == id, Transaction.timestamp >= now - timedelta(days=30))

    r24 = (await db.execute(q24)).one()
    r30 = (await db.execute(q30)).one()

    return {
        "userId": str(id),
        "txCount_24h": r24.cnt,
        "gmv_24h": float(r24.gmv),
        "distinctDevices_24h": r24.devs,
        "distinctIps_24h": r24.ips,
        "distinctCities_24h": r24.cities,
        "declineRate_30d": round(r30.decs / r30.total, 2) if r30.total > 0 else 0,
        "lastSeenAt": r24.last.isoformat().replace("+00:00", "Z") if r24.last else None
    }