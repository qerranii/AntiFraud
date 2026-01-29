from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID
from enum import Enum

class TimeSeriesResolution(str, Enum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"

class MerchantRiskItem(BaseModel):
    merchantId: Optional[str]
    merchantCategoryCode: Optional[str]
    txCount: int
    gmv: float
    declineRate: float

class TimeSeriesPoint(BaseModel):
    bucketStart: datetime
    txCount: int
    gmv: float
    approvalRate: float
    declineRate: float

class RuleStatItem(BaseModel):
    ruleId: UUID
    ruleName: str
    matches: int
    uniqueUsers: int
    uniqueMerchants: int
    shareOfDeclines: float

class StatsOverviewResponse(BaseModel):
    from_date: datetime = Field(..., alias="from")
    to_date: datetime = Field(..., alias="to")
    volume: int
    gmv: float
    approvalRate: float
    declineRate: float
    topRiskMerchants: List[MerchantRiskItem]

    class Config:
        populate_by_name = True

class TimeSeriesResponse(BaseModel):
    points: List[TimeSeriesPoint]

class RuleStatsResponse(BaseModel):
    items: List[RuleStatItem]

class MerchantRiskResponse(BaseModel):
    items: List[MerchantRiskItem]

class UserRiskProfileResponse(BaseModel):
    userId: UUID
    txCount_24h: int
    gmv_24h: float
    distinctDevices_24h: int
    distinctIps_24h: int
    distinctCities_24h: int
    declineRate_30d: float
    lastSeenAt: Optional[datetime]