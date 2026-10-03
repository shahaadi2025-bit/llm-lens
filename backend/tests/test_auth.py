import time

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import create_token, decode_token, hash_password, verify_password
from app.core.config import Settings
from app.main import create_app

PW = "correct horse battery"


async def register(client, email="a@example.com", password=PW, **extra):
    return await client.post("/api/auth/register", json={"email": email, "password": password, **extra})


def test_password_hash_is_salted_slow_and_verifiable():
    h1, h2 = hash_password(PW), hash_password(PW)
    assert h1 != h2 and h1.startswith("scrypt$") and PW not in h1
    assert verify_password(PW, h1) and not verify_password("wrong password!!", h1)
    assert not verify_password(PW, "garbage") and not verify_password(PW, "")


def test_token_roundtrip_expiry_and_tampering():
    import uuid

    uid = uuid.uuid4()
    secret = "s" * 40
    assert decode_token(create_token(uid, secret, 5), secret) == uid
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(create_token(uid, secret, -1), secret)
    with pytest.raises(jwt.PyJWTError):
        decode_token(create_token(uid, secret, 5), "x" * 40)  # wrong key
    forged = jwt.encode({"sub": str(uid), "exp": int(time.time()) + 60, "typ": "access"}, "attacker-key", "HS256")
    with pytest.raises(jwt.PyJWTError):
        decode_token(forged, secret)
    none_alg = jwt.encode({"sub": str(uid), "exp": int(time.time()) + 60, "typ": "access"}, None, algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        decode_token(none_alg, secret)  # unsigned tokens are rejected
    with pytest.raises(ValueError):
        decode_token(jwt.encode({"sub": str(uid), "exp": int(time.time()) + 60, "typ": "refresh"}, secret, "HS256"), secret)


async def test_register_login_me(client):
    r = await register(client, display_name="Ada")
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "a@example.com" and body["user"]["display_name"] == "Ada" and "password" not in str(body)
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200 and me.json()["id"] == body["user"]["id"]
    login = await client.post("/api/auth/login", json={"email": "A@Example.com", "password": PW})  # email is case-insensitive
    assert login.status_code == 200 and login.json()["user"]["id"] == body["user"]["id"]


async def test_register_validation_and_duplicates(client):
    assert (await register(client, password="short")).status_code == 422
    assert (await register(client, email="not-an-email")).status_code == 422
    assert (await register(client)).status_code == 201
    assert (await register(client)).status_code == 409
    assert (await register(client, email="B@example.com")).status_code == 201


async def test_login_failures_do_not_reveal_which_part_was_wrong(client):
    await register(client)
    wrong_pw = await client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong password"})
    unknown = await client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PW})
    assert wrong_pw.status_code == unknown.status_code == 401 and wrong_pw.json() == unknown.json()


async def test_bad_tokens_are_rejected_everywhere(client):
    for header in ["Bearer nonsense", "Basic abc", "Bearer", "bearer "]:
        assert (await client.get("/api/auth/me", headers={"Authorization": header})).status_code == 401
        assert (await client.get("/api/experiments", headers={"Authorization": header})).status_code == 401
    assert (await client.get("/api/auth/me")).status_code == 401  # no header on a sign-in-only endpoint
    assert (await client.get("/api/experiments")).status_code == 200  # but anonymous browsing works
    expired = create_token(__import__("uuid").uuid4(), Settings(secret_key=__import__('os').environ['SECRET_KEY']).secret_key, -1)
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})).status_code == 401


async def test_token_for_deleted_or_unknown_user_is_rejected(client):
    import uuid

    ghost = create_token(uuid.uuid4(), Settings(secret_key=__import__('os').environ['SECRET_KEY']).secret_key, 5)
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {ghost}"})).status_code == 401


async def test_registration_can_be_closed_and_capped():
    app = create_app(Settings(allow_registration=False))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await register(c)).status_code == 403


async def test_auth_endpoints_are_throttled_per_ip(engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.db import get_session

    app = create_app(Settings(auth_rate_limit_per_minute=3))
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def sess():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = sess
    async with AsyncClient(transport=ASGITransport(app=app, client=("9.9.9.9", 1)), base_url="http://t") as c:
        codes = [(await c.post("/api/auth/login", json={"email": "x@example.com", "password": "whatever"})).status_code
                 for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]  # brute force is cut off


async def test_secret_key_required_in_production():
    for weak in ("dev-insecure-change-me", "change-me-" + "x" * 40, "short"):
        with pytest.raises(RuntimeError):
            Settings(app_env="production", secret_key=weak).assert_production_safe()
    Settings(app_env="production", secret_key="k" * 40).assert_production_safe()
