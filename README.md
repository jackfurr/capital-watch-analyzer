# Capital Watch Analyzer

A Python service that analyzes U.S. Senate financial disclosure data and generates weekly reports.

## Overview

Queries the [Capitol Watch Scraper](https://github.com/jackfurr/capitol-watch-scraper) API, calculates trading heuristics, and generates PDF reports for distribution via email or Discord.

## Features

- **Automated Analysis**: Detects unusual trading patterns, sector concentrations, and high-activity politicians
- **PDF Reports**: Professional weekly reports with tables, charts, and alerts
- **Distribution**: Email via Brevo (free tier) or Discord webhooks
- **Ticker Normalization**: Maps company names to ticker symbols using Finnhub API
- **Scheduled Execution**: Cron-ready for automated weekly reports

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys

# Test connection
capital-watch-analyzer health

# Generate a report
capital-watch-analyzer generate-report
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `health` | Check API connectivity |
| `analyze` | Analyze recent trades |
| `generate-report` | Generate PDF report |
| `schedule` | Run scheduled weekly report |
| `normalize` | Test ticker normalization |
| `send-test-email` | Test email distribution |
| `version` | Show version |

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

## Documentation

- [Setup Guide](docs/SETUP.md) - Installation and configuration

## License

MIT
