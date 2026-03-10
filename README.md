# Capital Watch Analyzer

A Python service that analyzes Senate financial disclosure data and generates weekly reports.

## Overview

Queries the Capitol Watch Scraper API, calculates trading heuristics, and generates PDF reports for distribution.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Capitol Watch  │────▶│     Analyzer     │────▶│  Weekly PDF     │
│  Scraper API    │     │  (this service)  │     │  Reports        │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Email/Discord   │
                        │  Distribution    │
                        └──────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Access to Capitol Watch Scraper API

### 1. Install dependencies

```bash
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Run analysis

```bash
# Generate weekly report
capital-watch-analyzer generate-report --week 2026-03-03

# Run full analysis
capital-watch-analyzer analyze
```

## Project Structure

```
src/
  analyzer/
    __init__.py
    api_client.py      # Scraper API client
    heuristics.py      # Trading pattern analysis
    report_generator.py # PDF report generation
    distributor.py     # Email/Discord distribution
    config.py          # Settings
  cli.py               # Typer CLI entry point

tests/                 # Test suite
reports/               # Generated PDF output
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPER_API_URL` | `http://localhost:8000` | Scraper API base URL |
| `SCRAPER_API_KEY` | - | Shared API key |
| `REPORTS_DIR` | `./reports` | PDF output directory |
| `LOG_LEVEL` | `INFO` | Logging level |

## License

MIT
