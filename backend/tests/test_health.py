async def test_health_ok_and_labels_mock_mode(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["mock_mode"] is True
    assert "MOCK" in body["notice"] and "experimental evidence" in body["notice"]


async def test_security_headers_present(client):
    r = await client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


async def test_health_degrades_when_db_unreachable(client):
    from httpx import ASGITransport, AsyncClient

    from app.core.db import get_session
    from app.main import create_app  # fresh app with a broken session

    class Broken:
        async def execute(self, *_a, **_k):
            raise ConnectionError("db down")

    async def broken():
        yield Broken()

    app = create_app()
    app.dependency_overrides[get_session] = broken
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"
    assert r.json()["database"] == "unreachable"


async def test_unknown_route_404(client):
    assert (await client.get("/api/nope")).status_code == 404
