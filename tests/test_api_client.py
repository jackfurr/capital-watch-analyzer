"""Tests for the API client."""

import pytest
import respx
from httpx import Response

from analyzer.api_client import ScraperAPIError, ScraperClient


@pytest.fixture
def client():
    """Create a test client."""
    return ScraperClient(base_url="http://test.api", api_key="test-key")


@respx.mock
async def test_health_check_success(client):
    """Test successful health check."""
    route = respx.get("http://test.api/health").mock(return_value=Response(200, json={"status": "ok"}))

    result = await client.health_check()

    assert result["status"] == "ok"
    assert route.called


@respx.mock
async def test_health_check_failure(client):
    """Test failed health check raises error."""
    respx.get("http://test.api/health").mock(return_value=Response(500, text="Server error"))

    with pytest.raises(ScraperAPIError):
        await client.health_check()


@respx.mock
async def test_get_politicians(client):
    """Test fetching politicians."""
    mock_data = {
        "items": [{"id": "1", "first_name": "John", "last_name": "Doe"}],
        "total": 1,
        "page": 1,
        "pages": 1,
    }
    route = respx.get("http://test.api/api/v1/politicians").mock(return_value=Response(200, json=mock_data))

    result = await client.get_politicians()

    assert result["items"][0]["first_name"] == "John"
    assert route.called


@respx.mock
async def test_get_trades_with_filters(client):
    """Test fetching trades with filters."""
    mock_data = {"items": [], "total": 0, "page": 1, "pages": 1}
    route = respx.get("http://test.api/api/v1/trades").mock(return_value=Response(200, json=mock_data))

    from datetime import date
    result = await client.get_trades(
        ticker="AAPL",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
    )

    assert result["total"] == 0
    assert route.called
    # Check query params
    request = route.calls[0].request
    assert "ticker=AAPL" in str(request.url)


@respx.mock
async def test_api_headers_include_key():
    """Test that API key is included in headers."""
    client = ScraperClient(base_url="http://test.api", api_key="secret123")
    route = respx.get("http://test.api/health").mock(return_value=Response(200, json={}))

    await client.health_check()

    assert route.called
    assert route.calls[0].request.headers["X-API-Key"] == "secret123"
