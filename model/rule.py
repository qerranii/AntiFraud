import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from db.session import Base
#!!!! meow

class FraudRule(Base):
    __tablename__ = "fraud_rules"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = sa.Column(sa.String(120), nullable=False, unique=True, index=True)
    description = sa.Column(sa.String(500), nullable=True)
    dsl_expression = sa.Column(sa.String(2000), nullable=False)
    enabled = sa.Column(sa.Boolean, default=True, nullable=False)
    priority = sa.Column(sa.Integer, default=100, nullable=False)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "dslExpression": self.dsl_expression,
            "enabled": self.enabled,
            "priority": self.priority,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }