import logging

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.core.db import get_session
from app.core.security import CSP, redact
from app.main import create_app

KEY = "k" * 40


def _client(app, **kw):
    return AsyncClient(transport=ASGITransport(app=app, **kw), base_url="http://t")


async def test_csp_on_pages_but_not_on_api_and_hsts_only_in_production(tmp_path):
    (tmp_path / "index.html").write_text("<div id=root></div>")
    dev = create_app(Settings(frontend_dist=str(tmp_path)))
    async with _client(dev) as c:
        page = await c.get("/")
        assert page.headers["content-security-policy"] == CSP and "script-src 'self'" in CSP and "frame-ancestors 'none'" in CSP
        assert "unsafe-inline" not in CSP.split("script-src")[1].split(";")[0]  # no inline script allowed
        assert "strict-transport-security" not in page.headers
        api = await c.get("/api/health")
        assert "content-security-policy" not in api.headers and api.headers["cache-control"] == "no-store"
    prod = create_app(Settings(app_env="production", secret_key=KEY, frontend_dist=str(tmp_path)))
    async with _client(prod) as c:
        r = await c.get("/")
        assert r.headers["strict-transport-security"].startswith("max-age=31536000")
        assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"


async def test_oversized_bodies_are_rejected_declared_or_streamed(engine):
    app = create_app(Settings(max_request_bytes=200))
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def sess():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = sess
    async with _client(app) as c:
        big = {"email": "a@example.com", "password": "x" * 500}
        r = await c.post("/api/auth/login", json=big)
        assert r.status_code == 413 and r.json() == {"detail": "request body too large"}

        async def chunks():  # no Content-Length: the stream itself must be counted
            for _ in range(10):
                yield b"x" * 100

        r2 = await c.post("/api/auth/login", content=chunks(), headers={"content-type": "application/json"})
        assert r2.status_code == 413
        ok = await c.post("/api/auth/login", json={"email": "a@example.com", "password": "short"})
        assert ok.status_code == 401  # small bodies still reach the handler


def test_redaction_scrubs_tokens_passwords_and_database_urls():
    out = redact("Authorization: Bearer abcdef1234567890xyz; password=hunter2 token: tok_123456 "
                 "postgresql+asyncpg://neondb_owner:npg_secret@ep.neon.tech/db api_key=ABC")
    for secret in ("abcdef1234567890xyz", "hunter2", "tok_123456", "npg_secret", "ABC"):
        assert secret not in out
    assert out.count("[REDACTED]") >= 5 and "neondb_owner" in out and "ep.neon.tech" in out  # keeps useful context
    assert redact("nothing sensitive here") == "nothing sensitive here"


async def test_secrets_never_reach_logs(engine, caplog):
    app = create_app(Settings())
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def sess():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = sess
    caplog.set_level(logging.DEBUG)
    async with _client(app) as c:
        await c.post("/api/auth/register", json={"email": "a@example.com", "password": "my-very-secret-password"})
        await c.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-password-attempt"})
        await c.get("/api/auth/me", headers={"Authorization": "Bearer forged.jwt.token-value-1234"})
    logging.getLogger("app").warning("login failed password=my-very-secret-password Bearer abcdefgh12345678")
    text = caplog.text
    for secret in ("my-very-secret-password", "wrong-password-attempt", "abcdefgh12345678"):
        assert secret not in text


def test_production_refuses_wildcard_cors_and_weak_secret():
    with pytest.raises(RuntimeError, match="CORS"):
        Settings(app_env="production", secret_key=KEY, cors_origins="*").assert_production_safe()
    Settings(app_env="production", secret_key=KEY, cors_origins="https://app.example.com").assert_production_safe()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(app_env="production", secret_key="short", cors_origins="https://a.example").assert_production_safe()


async def test_search_treats_percent_and_underscore_as_literals(client):
    base = {"task_type": "arithmetic_representation", "config": {"n_random_pairs": 1}}
    for i, name in enumerate(["100% sure", "plain name", "snake_case run", "snakeXcase run"]):
        assert (await client.post("/api/experiments", json={**base, "name": name, "seed": i})).status_code == 201
    r = (await client.get("/api/experiments", params={"q": "%"})).json()
    assert [e["name"] for e in r] == ["100% sure"]  # '%' did not match everything
    r = (await client.get("/api/experiments", params={"q": "snake_case"})).json()
    assert [e["name"] for e in r] == ["snake_case run"]  # '_' did not act as a wildcard for 'X'
    assert (await client.get("/api/experiments", params={"q": "'; DROP TABLE experiments; --"})).json() == []
    assert len((await client.get("/api/experiments")).json()) == 4  # table intact


async def test_hostile_ids_and_paths_are_rejected_cleanly(client):
    for path in ("/api/experiments/../../etc/passwd", "/api/experiments/%00", "/api/experiments/1;DROP", "/api/reports/%27%20OR%201=1"):
        assert (await client.get(path)).status_code in (404, 422)
    assert (await client.get("/api/experiments", params={"limit": "1; DROP TABLE x", "offset": "-1"})).status_code == 422
