"""Tests for the ticker normalizer."""

import pytest

from analyzer.ticker_normalizer import TickerInfo, TickerNormalizer


@pytest.fixture
def normalizer():
    """Create a test normalizer without API key."""
    return TickerNormalizer(finnhub_api_key=None)


def test_clean_name(normalizer):
    """Test name cleaning."""
    assert normalizer._clean_name("Apple Inc.") == "apple"
    assert normalizer._clean_name("Microsoft Corporation") == "microsoft"
    assert normalizer._clean_name("Berkshire Hathaway Inc.") == "berkshire hathaway"


def test_manual_mapping(normalizer):
    """Test manual ticker mappings."""
    result = normalizer.normalize_sync("Apple Inc.")
    assert result.ticker == "AAPL"
    assert result.source == "manual"
    assert result.confidence == 100.0


def test_manual_mapping_variations(normalizer):
    """Test various name formats for same company."""
    variations = ["Apple", "Apple Inc", "Apple Inc.", "APPLE INC"]
    for name in variations:
        result = normalizer.normalize_sync(name)
        assert result.ticker == "AAPL", f"Failed for: {name}"


def test_unknown_company(normalizer):
    """Test handling of unknown companies."""
    result = normalizer.normalize_sync("Some Unknown Company XYZ")
    assert result.ticker is None
    assert result.source == "none"
    assert result.confidence == 0.0


def test_caching(normalizer):
    """Test that results are cached."""
    # First call
    result1 = normalizer.normalize_sync("Apple Inc.")
    # Second call should return cached result
    result2 = normalizer.normalize_sync("Apple Inc.")
    assert result1 is result2


@pytest.mark.asyncio
async def test_normalize_with_finnhub_disabled(normalizer):
    """Test async normalize without Finnhub."""
    result = await normalizer.normalize("Apple Inc.")
    assert result.ticker == "AAPL"
    assert result.source == "manual"
