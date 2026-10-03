"""Password hashing (scrypt, standard library) and signed access tokens (HS256 JWT). No third-party auth service,
so it works on any free host."""
import asyncio
import base64
import hashlib
import hmac
import os
import re
import time
import uuid

import jwt

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1  # ~16 MB per hash: fine for a 512 MB container
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 10
ALGORITHM = "HS256"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


_DUMMY = hash_password("not-a-real-password")  # verified against when the email is unknown, so timing does not leak existence


async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, stored: str | None) -> bool:
    ok = await asyncio.to_thread(verify_password, password, stored or _DUMMY)
    return ok and stored is not None


def create_token(user_id: uuid.UUID, secret: str, ttl_minutes: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + ttl_minutes * 60, "typ": "access"}, secret, ALGORITHM)


def decode_token(token: str, secret: str) -> uuid.UUID:
    """Raises jwt.PyJWTError or ValueError for any invalid/expired/tampered token."""
    claims = jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    if claims.get("typ") != "access":
        raise ValueError("wrong token type")
    return uuid.UUID(claims["sub"])
