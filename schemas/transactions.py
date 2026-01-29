from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone, timedelta
from uuid import UUID

class LocationSchema(BaseModel):
    country: Optional[str] = Field(None, min_length=2, max_length=2) # Важно для ValidationLocationInvalidCountryCode
    city: Optional[str] = Field(None, max_length=128)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode='after')
    def validate_coordinates(self) -> 'LocationSchema':
        lat = self.latitude
        lon = self.longitude
        if (lat is not None and lon is None) or (lon is not None and lat is None):
            raise ValueError("Both latitude and longitude must be provided")
        return self

class TransactionCreate(BaseModel):
    userId: Optional[UUID] = None
    amount: float = Field(..., ge=0.01, le=999999999.99)
    currency: str = Field(..., min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    timestamp: datetime
    merchantId: Optional[str] = Field(None, max_length=64)
    merchantCategoryCode: Optional[str] = Field(None, pattern="^[0-9]{4}$")
    ipAddress: Optional[str] = Field(None, max_length=64)
    deviceId: Optional[str] = Field(None, max_length=128)
    channel: Optional[str] = None
    location: Optional[LocationSchema] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v):
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v > now + timedelta(minutes=5):
            raise ValueError("Timestamp too far in future")
        return v

class BatchTransactionRequest(BaseModel):
    items: List[Any] = Field(..., min_length=1, max_length=500)