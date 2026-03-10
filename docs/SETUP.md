# Setup Guide

## Prerequisites

- Python 3.11+
- Access to Capitol Watch Scraper API
- (Optional) Brevo account for email distribution
- (Optional) Finnhub API key for ticker lookup

## Installation

```bash
# Clone the repository
git clone https://github.com/jackfurr/capital-watch-analyzer.git
cd capital-watch-analyzer

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

## Configuration

### Required Settings

```env
SCRAPER_API_URL=http://localhost:8000
SCRAPER_API_KEY=your-shared-api-key
```

### Optional: Email Distribution (Brevo)

1. Sign up at https://brevo.com (free tier: 300 emails/day)
2. Get API key from https://app.brevo.com/settings/keys/api
3. Add to `.env`:

```env
BREVO_API_KEY=your-brevo-api-key
EMAIL_FROM=reports@capitolwatch.dev
EMAIL_TO=your-email@example.com
```

### Optional: Discord Notifications

1. Create a webhook in your Discord server
2. Add to `.env`:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Optional: Ticker Lookup (Finnhub)

1. Sign up at https://finnhub.io (free tier: 60 calls/minute)
2. Add to `.env`:

```env
FINNHUB_API_KEY=your-finnhub-api-key
```

## Usage

### Check API Health

```bash
capital-watch-analyzer health
```

### Analyze Recent Trades

```bash
# Analyze last 7 days
capital-watch-analyzer analyze

# Analyze specific period
capital-watch-analyzer analyze --days 14

# Save results to JSON
capital-watch-analyzer analyze --days 7 --output analysis.json
```

### Generate Weekly Report

```bash
# Generate report for current week
capital-watch-analyzer generate-report

# Generate report for specific week
capital-watch-analyzer generate-report --week 2026-03-03
```

### Test Email Distribution

```bash
capital-watch-analyzer send-test-email --to your-email@example.com
```

### Test Ticker Normalization

```bash
capital-watch-analyzer normalize "Apple Inc."
capital-watch-analyzer normalize "Microsoft Corporation"
```

### Run Scheduled Weekly Report

```bash
# Calculate and generate report for the appropriate week
capital-watch-analyzer schedule

# Dry run (calculate week but don't generate)
capital-watch-analyzer schedule --dry-run
```

## Cron Setup

To run weekly reports automatically, add to your crontab:

```bash
# Run every Wednesday at 9 AM
0 9 * * 3 cd /path/to/capital-watch-analyzer && python -m src.cli schedule
```

Or use the provided script:

```bash
# Edit crontab
crontab -e

# Add this line
0 9 * * 3 /path/to/capital-watch-analyzer/scripts/run-weekly.sh
```

## Development

```bash
# Run tests
make test

# Run linter
make lint

# Run type checker
make typecheck

# Run all checks
make check
```

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

## Troubleshooting

### API Connection Issues

- Verify `SCRAPER_API_URL` is correct
- Check that `SCRAPER_API_KEY` matches the scraper's key
- Ensure the scraper API is running

### Email Not Sending

- Verify `BREVO_API_KEY` is set correctly
- Check that `EMAIL_TO` is a valid email
- Test with `send-test-email` command

### PDF Generation Fails

- Ensure WeasyPrint dependencies are installed:
  - macOS: `brew install pango libffi`
  - Ubuntu: `sudo apt-get install libpango-1.0-0 libffi-dev`

## License

MIT
