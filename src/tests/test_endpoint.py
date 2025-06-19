import pytest
import pytest_asyncio
from httpx import AsyncClient
from src.main import app

API_PREFIX = "/api/v1"
TEST_API_KEY = "your-secret-api-key"  # Replace with your actual API key
BASE_WALLET = "0x41136b8f1d327AC618a686e6D9B270cdB0bA6178"
INVALID_WALLET = "invalid_wallet"

@pytest_asyncio.fixture
async def client():
    headers = {"Authorization": f"Bearer {TEST_API_KEY}"}
    async with AsyncClient(app=app, base_url="http://localhost:8000", headers=headers) as ac:
        yield ac

# ---------------------- TRANSACTIONS ----------------------

@pytest.mark.asyncio
async def test_get_transactions(client):
    r = await client.get(f"{API_PREFIX}/transactions/{BASE_WALLET}")
    assert r.status_code in [200, 404]

    r_invalid = await client.get(f"{API_PREFIX}/transactions/{INVALID_WALLET}")
    assert r_invalid.status_code in [400, 404]

@pytest.mark.asyncio
async def test_transaction_summary(client):
    r = await client.get(f"{API_PREFIX}/transactions/{BASE_WALLET}/summary")
    assert r.status_code in [200, 404]

# ---------------------- EXPORTS ----------------------

@pytest.mark.asyncio
async def test_export_csv(client):
    r = await client.get(f"{API_PREFIX}/exports/csv", params={"wallet_address": BASE_WALLET})
    assert r.status_code in [200, 404]
    if r.status_code == 200:
        assert r.headers["content-type"].startswith("text/csv")

# ---------------------- REPORTS ----------------------

@pytest.mark.asyncio
async def test_generate_report(client):
    r = await client.get(f"{API_PREFIX}/reports/generate/{BASE_WALLET}")
    assert r.status_code in [200, 202, 404]

@pytest.mark.asyncio
async def test_report_status(client):
    r = await client.get(f"{API_PREFIX}/reports/status/{BASE_WALLET}")
    assert r.status_code in [200, 404]

@pytest.mark.asyncio
async def test_report_download(client):
    r = await client.get(f"{API_PREFIX}/reports/download/{BASE_WALLET}")
    assert r.status_code in [200, 404]

@pytest.mark.asyncio
async def test_report_clear(client):
    r = await client.delete(f"{API_PREFIX}/reports/clear/{BASE_WALLET}")
    assert r.status_code in [200, 204, 404]

# ---------------------- ANALYTICS ----------------------

@pytest.mark.asyncio
async def test_analytics_overview(client):
    r = await client.get(f"{API_PREFIX}/analytics/overview", params={"wallet_address": BASE_WALLET})
    assert r.status_code in [200, 404]
    if r.status_code == 200:
        assert "summary" in r.json() or isinstance(r.json(), dict)

# ---------------------- CACHE ----------------------

@pytest.mark.asyncio
async def test_cache_clear(client):
    r = await client.delete(f"{API_PREFIX}/cache/clear")
    assert r.status_code in [200, 204]

# ---------------------- AUTH NEGATIVE TEST ----------------------

@pytest.mark.asyncio
async def test_missing_auth():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get(f"{API_PREFIX}/transactions/{BASE_WALLET}")
        assert r.status_code == 401
