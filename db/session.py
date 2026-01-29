from sqlalchemy.orm import declarative_base
import os
from typing import AsyncGenerator
from asyncio import current_task

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_scoped_session,
)

try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:
    from sqlalchemy.ext.asyncio import async_session as async_sessionmaker


DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "antifraud")
DB_USER = os.getenv("DB_USER", "testuser")
DB_PASS = os.getenv("DB_PASSWORD", "testpass")

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

async_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True
)

async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )
    try:
        yield redis_client
    finally:
        await redis_client.close()


async def create_tables():
    from model.user import User
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)