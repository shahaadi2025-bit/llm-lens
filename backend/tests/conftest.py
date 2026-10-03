import os

# Must be set before app modules import settings.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["MODEL_PROVIDER"] = "mock"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.api.deps import get_adapter, get_engine  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.experiments.engine import ExperimentEngine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.adapters.mock import MockAdapter  # noqa: E402


@pytest.fixture
async def engine(tmp_path):
    # File-backed SQLite: every session gets its own connection, like PostgreSQL. A single shared in-memory
    # connection would let concurrent sessions roll back each other's transactions (a test artifact).
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite'}", connect_args={"timeout": 30})
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s


@pytest.fixture
async def client(engine):
    app = create_app()
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def override() -> AsyncSession:  # type: ignore[misc]
        async with maker() as s:
            yield s

    adapter = MockAdapter()
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_adapter] = lambda: adapter
    app.state.engine = ExperimentEngine(maker, lambda slug: MockAdapter(slug), retry_backoff_s=0.0)
    app.dependency_overrides[get_engine] = lambda: app.state.engine
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.app_engine = app.state.engine  # type: ignore[attr-defined]
        yield c
