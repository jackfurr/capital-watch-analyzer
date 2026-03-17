# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install-dev    # Install all dependencies (including dev)
make test           # Run tests with coverage
make lint           # Lint with ruff
make format         # Format with ruff
make typecheck      # Type check with mypy
make check          # Run lint + typecheck + test

# Run a single test file
pytest tests/test_api_client.py

# Run a specific test
pytest tests/test_api_client.py::TestScraperClient::test_get_trades

# CLI entry point (after install)
capital-watch-analyzer health
capital-watch-analyzer generate-report --week 2024-01-15
```

## Architecture

This is a Python service that fetches U.S. Senate financial disclosure data, analyzes trading patterns, generates PDF reports, and distributes them via email or Discord.

**Data flow:** `Capitol Watch Scraper API → api_client.py → heuristics.py → report_generator.py → distributor.py`

### Key modules (`src/analyzer/`)

- **`api_client.py`** — Async `httpx` client for the Capitol Watch Scraper API. Handles pagination automatically. Raises `ScraperAPIError` on failure.
- **`heuristics.py`** — Computes `PoliticianMetrics`, `AssetMetrics`, and `SectorMetrics` from trade data. Also detects anomalous patterns and generates alerts.
- **`report_generator.py`** — Renders Jinja2 HTML templates and converts to PDF via WeasyPrint.
- **`distributor.py`** — Sends reports via Brevo email API or Discord webhooks (async, PDF as base64 attachment).
- **`ticker_normalizer.py`** — Three-tier ticker lookup: hardcoded manual mappings → Finnhub API (60 req/min free) → fuzzy matching via `thefuzz`.
- **`scheduler.py`** — Calculates weekly date ranges and orchestrates the full pipeline; cron-ready.
- **`config.py`** — Pydantic Settings loaded from env vars or `.env`. Finnhub API key can also be read from `~/.config/finnhub/api_key`.

### CLI (`src/cli.py`)

Built with Typer + Rich. Entry point: `capital-watch-analyzer` (configured in `pyproject.toml`).

## Configuration

Copy `.env.example` to `.env` and fill in:
- `SCRAPER_API_URL` / `SCRAPER_API_KEY` — Capitol Watch Scraper API
- `BREVO_API_KEY` — Email distribution (free tier: 300/day)
- `DISCORD_WEBHOOK_URL` — Discord distribution
- `FINNHUB_API_KEY` or `~/.config/finnhub/api_key` — Ticker normalization

## Testing

Tests use `pytest-asyncio` (mode: auto) and `respx` for mocking async HTTP. All I/O is async throughout the codebase.

## Code Style

- Python 3.11+, line length 100, ruff rules: E, F, I, N, W, UP, B, C4, SIM
- Full MyPy strict type checking required
- Structured logging via `structlog`
