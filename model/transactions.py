import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from db.session import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False)
    amount = sa.Column(sa.Numeric(15, 2), nullable=False)
    currency = sa.Column(sa.String(3), nullable=False)
    status = sa.Column(sa.String(20), nullable=False)
    is_fraud = sa.Column(sa.Boolean, default=False)

    timestamp = sa.Column(sa.DateTime(timezone=True), nullable=False)
    merchant_id = sa.Column(sa.String(64), nullable=True)
    mcc = sa.Column(sa.String(4), nullable=True)
    ip_address = sa.Column(sa.String(64), nullable=True)
    device_id = sa.Column(sa.String(128), nullable=True)
    channel = sa.Column(sa.String(20), nullable=True)

    location = sa.Column(JSONB, nullable=True)  # {country, city, latitude, longitude}
    metadata_json = sa.Column("metadata", JSONB, nullable=True)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())

    rule_results = relationship("RuleResult", back_populates="transaction", cascade="all, delete-orphan")


class RuleResult(Base):
    __tablename__ = "rule_results"

    id = sa.Column(sa.Integer, primary_key=True)
    transaction_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("transactions.id"))
    rule_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("fraud_rules.id"))
    rule_name = sa.Column(sa.String(120), nullable=False)
    priority = sa.Column(sa.Integer, nullable=False)
    matched = sa.Column(sa.Boolean, nullable=False)
    description = sa.Column(sa.String(500), nullable=False)

    transaction = relationship("Transaction", back_populates="rule_results")