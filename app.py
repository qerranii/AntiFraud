from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
import os
from sqlalchemy.future import select

from db.session import create_tables, async_session_factory
from model.user import User
from endpoints.auth import router as auth_router
from endpoints.user import router as users_router
from endpoints.rule import router as rule_router
from endpoints.metrics.overview import router as overview_router
from endpoints.metrics.transaction import router as tm_router
from endpoints.metrics.user import router as um_router
from endpoints.metrics.rule import router as rm_router

from fastapi.exceptions import RequestValidationError
from fastapi import Request, status
from fastapi.responses import JSONResponse
from uuid import uuid4
from datetime import datetime, timezone

from endpoints.transaction import router as trans_router
from utils.security import hash_password
from prometheus_fastapi_instrumentator import Instrumentator

#!!!! meow

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()

    async with async_session_factory() as session:
        admin_email = os.getenv("ADMIN_EMAIL")
        if admin_email:
            result = await session.execute(select(User).where(User.email == admin_email))
            admin = result.scalar_one_or_none()

            if not admin:
                new_admin = User(
                    email=admin_email,
                    full_name=os.getenv("ADMIN_FULLNAME", "Admin"),
                    hashed_password=hash_password(os.getenv("ADMIN_PASSWORD", "admin123")),
                    role="ADMIN",
                    is_active=True
                )
                session.add(new_admin)
                await session.commit()
    yield

app = FastAPI(lifespan=lifespan)
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    field_errors = []
    for error in exc.errors():
        field_name = ".".join([str(x) for x in error["loc"][1:]])
        field_errors.append({
            "field": field_name,
            "message": error["msg"],
            "rejectedValue": error.get("input")
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_FAILED",
            "message": "Validation failed",
            "traceId": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "path": request.url.path,
            "fieldErrors": field_errors
        }
    )

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "NOT_FOUND" if exc.status_code == 404 else "FORBIDDEN",
            "message": str(exc.detail),
            "traceId": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "path": request.url.path
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    content = {
        "code": "NOT_FOUND" if exc.status_code == 404 else "FORBIDDEN",
        "message": "",
        "traceId": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "path": request.url.path
    }

    if isinstance(exc.detail, dict):
        content["message"] = exc.detail.pop("message", "Error occurred")
        content["details"] = exc.detail
    else:
        content["message"] = exc.detail

    return JSONResponse(status_code=exc.status_code, content=content)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rule_router)
app.include_router(trans_router)
app.include_router(overview_router)
app.include_router(tm_router)
app.include_router(um_router)
app.include_router(rm_router)


@app.get("/api/v1/ping")
async def ping():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
