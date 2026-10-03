import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_adapter
from app.core.config import Settings, normalize_database_url
from app.core.db import get_session
from app.main import create_app
from app.services.adapters.mock import MockAdapter

BODY = {"name": "x", "task_type": "arithmetic_representation", "config": {"pairs": [[37, 84]]}}


@pytest.mark.parametrize("raw,expected", [
    ("postgresql://u:p@ep-1.neon.tech/db?sslmode=require&channel_binding=require",
     "postgresql+asyncpg://u:p@ep-1.neon.tech/db?ssl=require"),
    ("postgres://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
    ("postgresql+asyncpg://u:p@host/db?ssl=require", "postgresql+asyncpg://u:p@host/db?ssl=require"),
    ("sqlite+aiosqlite:///./x.sqlite", "sqlite+aiosqlite:///./x.sqlite"),
])
def test_database_url_normalization(raw, expected):
    assert normalize_database_url(raw) == expected
    assert Settings(database_url=raw).database_url == expected


def test_production_refuses_placeholder_secret():
    with pytest.raises(RuntimeError):
        Settings(app_env="production", secret_key="change-me-please").assert_production_safe()
    Settings(app_env="production", secret_key="x" * 40).assert_production_safe()


async def public_client(engine, **overrides):
    settings = Settings(public_demo_mode=True, model_provider="mock", **overrides)
    app = create_app(settings)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def sess():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = sess
    app.dependency_overrides[get_adapter] = lambda: MockAdapter()
    return AsyncClient(transport=ASGITransport(app=app, client=("203.0.113.9", 1)), base_url="http://t")


async def test_rate_limit_applies_to_writes_only(engine):
    async with await public_client(engine, public_rate_limit_per_minute=3) as c:
        codes = [(await c.post("/api/experiments", json={**BODY, "seed": i})).status_code for i in range(5)]
        assert codes == [201, 201, 201, 429, 429]
        r = await c.post("/api/experiments", json=BODY)
        assert r.headers["retry-after"].isdigit()
        assert (await c.get("/api/health")).status_code == 200  # reads are never limited


async def test_rate_limit_is_per_client_ip(engine):
    settings = Settings(public_demo_mode=True, public_rate_limit_per_minute=1)
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app, client=("1.1.1.1", 1)), base_url="http://t") as a:
        assert (await a.post("/api/nope")).status_code == 404
        assert (await a.post("/api/nope")).status_code == 429
    async with AsyncClient(transport=ASGITransport(app=app, client=("2.2.2.2", 1)), base_url="http://t") as b:
        assert (await b.post("/api/nope")).status_code == 404


async def test_public_mode_caps_total_experiments_and_run_size(engine):
    async with await public_client(engine, public_max_total_experiments=2, public_rate_limit_per_minute=100) as c:
        assert (await c.post("/api/experiments", json={**BODY, "seed": 1})).status_code == 201
        assert (await c.post("/api/experiments", json={**BODY, "seed": 2})).status_code == 201
        r = await c.post("/api/experiments", json={**BODY, "seed": 3})
        assert r.status_code == 429 and "storage limit" in r.json()["detail"]
    async with await public_client(engine, public_rate_limit_per_minute=100) as c:
        big = {**BODY, "config": {"n_random_pairs": 10}}  # 66 runs > public limit of 40
        assert (await c.post("/api/experiments", json=big)).status_code == 422


async def test_frontend_is_served_with_spa_fallback_and_api_stays_json(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root>LLM Lens</div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("nope")
    app = create_app(Settings(frontend_dist=str(dist)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert "LLM Lens" in (await c.get("/")).text
        assert "LLM Lens" in (await c.get("/experiments/123")).text  # client-side route
        js = await c.get("/assets/app.js")
        assert js.text == "console.log(1)" and "immutable" in js.headers["cache-control"]
        assert (await c.get("/api/nope")).headers["content-type"] == "application/json"
        assert (await c.get("/api/nope")).status_code == 404
        assert "nope" not in (await c.get("/..%2Fsecret.txt")).text  # no path traversal
        assert "nope" not in (await c.get("/assets/..%2F..%2Fsecret.txt")).text


async def test_no_frontend_dist_means_api_only(client):
    assert (await client.get("/")).status_code == 404
