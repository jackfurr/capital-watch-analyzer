"""HTTP client for the Capitol Watch Scraper API."""

from datetime import date
from typing import Any

import httpx
import structlog

from analyzer.config import settings

logger = structlog.get_logger()


class ScraperAPIError(Exception):
    """Raised when the scraper API returns an error."""

    pass


class ScraperClient:
    """Client for interacting with the Capitol Watch Scraper API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        """Initialize the client.

        Args:
            base_url: Override the default API URL
            api_key: Override the default API key
        """
        self.base_url = (base_url or settings.scraper_api_url).rstrip("/")
        self.api_key = api_key or settings.scraper_api_key
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an HTTP request to the API."""
        url = f"{self.base_url}{path}"
        headers = {**self.headers, **kwargs.pop("headers", {})}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "API request failed",
                    status_code=e.response.status_code,
                    url=url,
                    response=e.response.text,
                )
                raise ScraperAPIError(f"API error {e.response.status_code}: {e.response.text}") from e
            except httpx.RequestError as e:
                logger.error("API request failed", error=str(e), url=url)
                raise ScraperAPIError(f"Request failed: {e}") from e

    async def health_check(self) -> dict[str, Any]:
        """Check if the API is healthy."""
        return await self._request("GET", "/health")

    async def get_politicians(
        self, state: str | None = None, page: int = 1, page_size: int = 100
    ) -> dict[str, Any]:
        """Get list of politicians.

        Args:
            state: Filter by state code (e.g., "CA")
            page: Page number
            page_size: Items per page
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if state:
            params["state"] = state
        return await self._request("GET", "/api/v1/politicians", params=params)

    async def get_trades(
        self,
        politician_id: str | None = None,
        ticker: str | None = None,
        transaction_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Get list of trades/transactions.

        Args:
            politician_id: Filter by politician UUID
            ticker: Filter by asset ticker symbol
            transaction_type: Filter by type (purchase, sale, etc.)
            start_date: Filter trades from this date
            end_date: Filter trades until this date
            page: Page number
            page_size: Items per page
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if politician_id:
            params["politician_id"] = politician_id
        if ticker:
            params["ticker"] = ticker
        if transaction_type:
            params["transaction_type"] = transaction_type
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        return await self._request("GET", "/api/v1/trades", params=params)

    async def get_assets(
        self, ticker: str | None = None, sector: str | None = None, page: int = 1, page_size: int = 100
    ) -> dict[str, Any]:
        """Get list of assets.

        Args:
            ticker: Filter by ticker symbol
            sector: Filter by sector
            page: Page number
            page_size: Items per page
        """
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if ticker:
            params["ticker"] = ticker
        if sector:
            params["sector"] = sector
        return await self._request("GET", "/api/v1/assets", params=params)

    async def get_stats(self) -> dict[str, Any]:
        """Get overall statistics."""
        return await self._request("GET", "/api/v1/stats")

    async def get_all_trades_for_period(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Get all trades for a date period (handles pagination).

        Args:
            start_date: Start of period
            end_date: End of period

        Returns:
            List of all trade records
        """
        all_trades: list[dict[str, Any]] = []
        page = 1

        while True:
            result = await self.get_trades(
                start_date=start_date,
                end_date=end_date,
                page=page,
                page_size=100,
            )

            trades = result.get("items", [])
            if not trades:
                break

            all_trades.extend(trades)

            # Check if we've reached the end
            total_pages = result.get("pages", 1)
            if page >= total_pages:
                break

            page += 1

        logger.info(
            "Fetched trades for period",
            start_date=start_date,
            end_date=end_date,
            count=len(all_trades),
        )

        return all_trades
