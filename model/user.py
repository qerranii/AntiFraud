import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from db.session import Base

class User(Base):
    __tablename__ = "users"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = sa.Column(sa.String(254), nullable=False, unique=True, index=True)
    hashed_password = sa.Column(sa.String, nullable=False)
    full_name = sa.Column(sa.String(200), nullable=False)
    age = sa.Column(sa.Integer, nullable=True)
    region = sa.Column(sa.String(32), nullable=True)
    gender = sa.Column(sa.String, nullable=True)
    marital_status = sa.Column(sa.String, nullable=True)
    role = sa.Column(sa.String, nullable=False, default="USER")
    is_active = sa.Column(sa.Boolean, default=True)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())

    def to_dict(self):
        return {
            "id": str(self.id),
            "email": self.email,
            "fullName": self.full_name,
            "age": self.age,
            "region": self.region,
            "gender": self.gender,
            "maritalStatus": self.marital_status,
            "role": self.role,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }