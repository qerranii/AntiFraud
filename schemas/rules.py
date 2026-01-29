from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime


class DslValidateRequest(BaseModel):
    dslExpression: str = Field(..., alias="dslExpression")
    model_config = ConfigDict(populate_by_name=True)

class DslValidateResponse(BaseModel):
    isValid: bool
    errors: list[str] = []
    normalizedExpression: Optional[str] = None

class FraudRuleBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    dslExpression: str = Field(..., min_length=3, max_length=2000)
    enabled: bool = True
    priority: int = Field(default=100, ge=1)


class FraudRuleCreate(FraudRuleBase):
    pass


class FraudRuleUpdate(FraudRuleBase):
    pass


class FraudRuleResponse(FraudRuleBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_orm_model(cls, obj):
        return cls(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            dslExpression=obj.dsl_expression,
            enabled=obj.enabled,
            priority=obj.priority,
            createdAt=obj.created_at,
            updatedAt=obj.updated_at
        )