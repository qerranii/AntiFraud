from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, distinct, cast, Float
from typing import Optional
from datetime import datetime, timezone as dt_timezone, timedelta
from uuid import UUID, uuid4

from db.session import get_async_session
from model.transactions import Transaction, RuleResult
from model.rule import FraudRule
from model.user import User
from schemas.stats import (
    StatsOverviewResponse,
    TimeSeriesResponse,
    RuleStatsResponse,
    MerchantRiskResponse,
    UserRiskProfileResponse,
    TimeSeriesResolution
)
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


@router.get("/overview", response_model=StatsOverviewResponse)
async def get_stats_overview(
        request: Request,
        from_date: Optional[datetime] = Query(None, alias="from"),
        to_date: Optional[datetime] = Query(None, alias="to"),
        tz: str = Query("UTC", alias="timezone"),
        db: AsyncSession = Depends(get_async_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise get_error_response(403, "ACCESS_DENIED", "Admin access required", request)

    if not to_date: to_date = datetime.now(dt_timezone.utc)
    if not from_date: from_date = to_date - timedelta(days=30)

    if from_date >= to_date:
        raise get_error_response(400, "INVALID_PERIOD", "from < to", request)

    ts_field = func.coalesce(Transaction.timestamp, Transaction.created_at)

    stats_q = select(
        func.count(Transaction.id).label("volume"),
        func.coalesce(func.sum(Transaction.amount), 0).label("gmv"),
        func.count(Transaction.id).filter(func.upper(Transaction.status) == "APPROVED").label("approved"),
        func.count(Transaction.id).filter(func.upper(Transaction.status) == "DECLINED").label("declined"),
    ).where(ts_field >= from_date, ts_field < to_date)

    res = await db.execute(stats_q)
    s = res.one()

    if s.volume == 0:
        return {
            "from": from_date, "to": to_date, "volume": 0, "gmv": 0.0,
            "approvalRate": 0.0, "declineRate": 0.0, "topRiskMerchants": []
        }

    merch_q = select(
        Transaction.merchant_id.label("merchantId"),
        Transaction.mcc.label("merchantCategoryCode"),
        func.count(Transaction.id).label("txCount"),
        func.sum(Transaction.amount).label("gmv"),
        (cast(func.count(Transaction.id).filter(func.upper(Transaction.status) == "DECLINED"), Float) /
         func.count(Transaction.id)).label("declineRate")
    ).where(ts_field >= from_date, ts_field < to_date, Transaction.merchant_id.is_not(None)) \
        .group_by(Transaction.merchant_id, Transaction.mcc) \
        .order_by(desc("declineRate"), desc("txCount")).limit(10)

    m_res = await db.execute(merch_q)

    return {
        "from": from_date,
        "to": to_date,
        "volume": s.volume,
        "gmv": float(s.gmv),
        "approvalRate": round(s.approved / s.volume, 2),
        "declineRate": round(s.declined / s.volume, 2),
        "topRiskMerchants": [
            {
                "merchantId": r.merchantId,
                "merchantCategoryCode": r.merchantCategoryCode,
                "txCount": r.txCount,
                "gmv": float(r.gmv or 0),
                "declineRate": round(float(r.declineRate or 0), 2)
            } for r in m_res.all()
        ]
    }