import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    EMAIL_RE,
    MIN_PASSWORD,
    create_token,
    decode_token,
    hash_password_async,
    verify_password_async,
)
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import User

router = APIRouter(tags=["auth"])


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("enter a valid email address")
        return v


class RegisterRequest(Credentials):
    display_name: str = Field(default="", max_length=120)

    @field_validator("password")
    @classmethod
    def _strong_enough(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD:
            raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
        return v


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str


class TokenOut(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


def _out(u: User) -> UserOut:
    return UserOut(id=str(u.id), email=u.email, display_name=u.display_name)


async def optional_user(authorization: str | None = Header(default=None), session: AsyncSession = Depends(get_session),
                        settings: Settings = Depends(get_settings)) -> User | None:
    """No Authorization header -> anonymous (None). A present but invalid/expired token -> 401, so clients can log out."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "invalid authorization header", headers={"WWW-Authenticate": "Bearer"})
    try:
        uid = decode_token(token, settings.secret_key)
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(401, "invalid or expired token", headers={"WWW-Authenticate": "Bearer"}) from exc
    user = await session.get(User, uid)
    if user is None or not user.is_active:
        raise HTTPException(401, "invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    return user


async def required_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})
    return user


@router.post("/auth/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session),
                   settings: Settings = Depends(get_settings)) -> TokenOut:
    if not settings.allow_registration:
        raise HTTPException(403, "registration is closed on this deployment")
    if settings.public_demo_mode:
        n = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        if n >= settings.public_max_users:
            raise HTTPException(403, "the public demo has reached its account limit")
    if (await session.execute(select(User.id).where(User.email == body.email))).first():
        raise HTTPException(409, "an account with this email already exists")
    user = User(email=body.email, password_hash=await hash_password_async(body.password),
                display_name=body.display_name.strip() or body.email.split("@")[0])
    session.add(user)
    await session.commit()
    return TokenOut(token=create_token(user.id, settings.secret_key, settings.access_token_ttl_minutes), user=_out(user))


@router.post("/auth/login", response_model=TokenOut)
async def login(body: Credentials, session: AsyncSession = Depends(get_session),
                settings: Settings = Depends(get_settings)) -> TokenOut:
    user = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    ok = await verify_password_async(body.password, user.password_hash if user else None)
    if not ok or user is None or not user.is_active:
        raise HTTPException(401, "incorrect email or password")  # same message for unknown email and wrong password
    return TokenOut(token=create_token(user.id, settings.secret_key, settings.access_token_ttl_minutes), user=_out(user))


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(required_user)) -> UserOut:
    return _out(user)
