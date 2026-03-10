"""Ticker normalization and sector lookup using Finnhub API."""

import re
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from thefuzz import fuzz, process

from analyzer.config import settings

logger = structlog.get_logger()

# Common company name patterns to clean
CLEAN_PATTERNS = [
    (r"\b(Inc\.?|Incorporated)\b", ""),
    (r"\b(Corp\.?|Corporation)\b", ""),
    (r"\b(Ltd\.?|Limited)\b", ""),
    (r"\b(LLC|L\.L\.C\.)\b", ""),
    (r"\b(PLC|Public Limited Company)\b", ""),
    (r"\b(Holdings?|Holding)\b", ""),
    (r"\b(Group|Co\.?|Company)\b", ""),
    (r"\b(Class [A-Z])\b", ""),
    (r"\s+", " "),  # Normalize whitespace
]

# Manual mappings for common edge cases
MANUAL_MAPPINGS = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "nvidia": "NVDA",
    "berkshire hathaway": "BRK.B",
    "berkshire": "BRK.B",
    "jpmorgan": "JPM",
    "johnson & johnson": "JNJ",
    "jnj": "JNJ",
    "visa": "V",
    "procter & gamble": "PG",
    "unitedhealth": "UNH",
    "home depot": "HD",
    "mastercard": "MA",
    "exxon mobil": "XOM",
    "exxon": "XOM",
    "chevron": "CVX",
    "coca-cola": "KO",
    "coca cola": "KO",
    "pfizer": "PFE",
    "walt disney": "DIS",
    "disney": "DIS",
    "bank of america": "BAC",
    "comcast": "CMCSA",
    "verizon": "VZ",
    "intel": "INTC",
    "cisco": "CSCO",
    "merck": "MRK",
    "pepsico": "PEP",
    "pepsi": "PEP",
    "adobe": "ADBE",
    "salesforce": "CRM",
    "mcdonalds": "MCD",
    "mcdonald's": "MCD",
    "amgen": "AMGN",
    "boeing": "BA",
    "ibm": "IBM",
    "goldman sachs": "GS",
    "3m": "MMM",
    "nike": "NKE",
    "tjx": "TJX",
    "s&p 500": "SPY",
    "sp500": "SPY",
    "spy": "SPY",
    "total market": "VTI",
    "vanguard total": "VTI",
}


@dataclass
class TickerInfo:
    """Normalized ticker information."""

    ticker: str | None
    name: str
    sector: str | None
    industry: str | None
    confidence: float  # 0-100
    source: str  # "manual", "finnhub", "fuzzy", "none"


class TickerNormalizer:
    """Normalize asset names to ticker symbols."""

    def __init__(self, finnhub_api_key: str | None = None) -> None:
        """Initialize the normalizer.

        Args:
            finnhub_api_key: Optional Finnhub API key for lookups
        """
        self.finnhub_api_key = finnhub_api_key
        self.logger = structlog.get_logger()
        self._cache: dict[str, TickerInfo] = {}
        self._us_stocks: list[dict[str, Any]] | None = None

    def _clean_name(self, name: str) -> str:
        """Clean company name for matching.

        Args:
            name: Raw company name

        Returns:
            Cleaned name
        """
        cleaned = name.lower().strip()
        for pattern, replacement in CLEAN_PATTERNS:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    async def _load_us_stocks(self) -> list[dict[str, Any]]:
        """Load US stock symbols from Finnhub.

        Returns:
            List of stock symbols with names
        """
        if self._us_stocks is not None:
            return self._us_stocks

        if not self.finnhub_api_key:
            self._us_stocks = []
            return []

        url = "https://finnhub.io/api/v1/stock/symbol"
        params = {
            "exchange": "US",
            "token": self.finnhub_api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                self._us_stocks = response.json()
                self.logger.info("Loaded US stocks", count=len(self._us_stocks))
                return self._us_stocks
        except Exception as e:
            self.logger.error("Failed to load US stocks", error=str(e))
            self._us_stocks = []
            return []

    async def _lookup_finnhub(self, name: str) -> TickerInfo | None:
        """Look up ticker via Finnhub API.

        Args:
            name: Company name to look up

        Returns:
            TickerInfo if found, None otherwise
        """
        if not self.finnhub_api_key:
            return None

        # Try symbol lookup endpoint first
        url = "https://finnhub.io/api/v1/search"
        params = {
            "q": name,
            "token": self.finnhub_api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                results = data.get("result", [])
                if results:
                    # Get first US equity result
                    for result in results:
                        if result.get("symbol") and result.get("type") == "Common Stock":
                            # Get company profile for sector info
                            profile = await self._get_company_profile(result["symbol"])
                            return TickerInfo(
                                ticker=result["symbol"],
                                name=result.get("description", name),
                                sector=profile.get("sector"),
                                industry=profile.get("industry"),
                                confidence=80.0,
                                source="finnhub",
                            )
        except Exception as e:
            self.logger.debug("Finnhub lookup failed", name=name, error=str(e))

        return None

    async def _get_company_profile(self, symbol: str) -> dict[str, Any]:
        """Get company profile for sector info.

        Args:
            symbol: Stock symbol

        Returns:
            Company profile dict
        """
        if not self.finnhub_api_key:
            return {}

        url = "https://finnhub.io/api/v1/stock/profile2"
        params = {
            "symbol": symbol,
            "token": self.finnhub_api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                return response.json()
        except Exception:
            return {}

    async def _fuzzy_match(self, name: str) -> TickerInfo | None:
        """Fuzzy match against US stock list.

        Args:
            name: Cleaned company name

        Returns:
            TickerInfo if good match found
        """
        stocks = await self._load_us_stocks()
        if not stocks:
            return None

        # Build list of (name, symbol) tuples
        choices = [(s.get("description", ""), s.get("symbol", "")) for s in stocks if s.get("description")]

        # Find best match
        match = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio)

        if match and match[1] >= 85:  # 85% confidence threshold
            symbol = match[0][1]
            profile = await self._get_company_profile(symbol)
            return TickerInfo(
                ticker=symbol,
                name=match[0][0],
                sector=profile.get("sector"),
                industry=profile.get("industry"),
                confidence=float(match[1]),
                source="fuzzy",
            )

        return None

    async def normalize(self, name: str) -> TickerInfo:
        """Normalize an asset name to ticker symbol.

        Tries in order:
        1. Cache lookup
        2. Manual mappings
        3. Finnhub API search
        4. Fuzzy matching against US stock list

        Args:
            name: Asset name from disclosure

        Returns:
            TickerInfo with ticker, sector, etc.
        """
        # Check cache
        if name in self._cache:
            return self._cache[name]

        cleaned = self._clean_name(name)

        # Try manual mappings
        if cleaned in MANUAL_MAPPINGS:
            result = TickerInfo(
                ticker=MANUAL_MAPPINGS[cleaned],
                name=name,
                sector=None,  # Could look this up
                industry=None,
                confidence=100.0,
                source="manual",
            )
            self._cache[name] = result
            return result

        # Try Finnhub API
        result = await self._lookup_finnhub(name)
        if result:
            self._cache[name] = result
            return result

        # Try fuzzy matching
        result = await self._fuzzy_match(cleaned)
        if result:
            self._cache[name] = result
            return result

        # No match found
        result = TickerInfo(
            ticker=None,
            name=name,
            sector=None,
            industry=None,
            confidence=0.0,
            source="none",
        )
        self._cache[name] = result
        return result

    def normalize_sync(self, name: str) -> TickerInfo:
        """Synchronous version of normalize (no API calls).

        Only uses manual mappings and cache.

        Args:
            name: Asset name

        Returns:
            TickerInfo (may have no ticker if not in manual mappings)
        """
        if name in self._cache:
            return self._cache[name]

        cleaned = self._clean_name(name)

        if cleaned in MANUAL_MAPPINGS:
            result = TickerInfo(
                ticker=MANUAL_MAPPINGS[cleaned],
                name=name,
                sector=None,
                industry=None,
                confidence=100.0,
                source="manual",
            )
            self._cache[name] = result
            return result

        result = TickerInfo(
            ticker=None,
            name=name,
            sector=None,
            industry=None,
            confidence=0.0,
            source="none",
        )
        self._cache[name] = result
        return result
