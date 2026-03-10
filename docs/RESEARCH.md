# Research Summary: Distribution & Data Sources

## Email Distribution Options

### Recommended: Brevo (formerly Sendinblue)

**Why Brevo:**
- **Free tier**: 300 emails/day (9,000/month) - plenty for weekly reports
- **Pricing**: $0 for free tier, then starts at ~$9/month for 10k emails
- **API**: Clean REST API with Python SDK
- **Deliverability**: Good reputation, built for transactional email

**Comparison:**

| Service | Free Tier | Paid Cost | Notes |
|---------|-----------|-----------|-------|
| **Brevo** | 300/day | $9/mo starter | ✅ Best free option |
| AWS SES | None | $0.10/1k emails | Cheapest at scale, complex setup |
| SendGrid | None | $19.95/mo | Removed free tier in 2025 |
| Mailgun | None | $2/1k emails | Pricing doubled Dec 2025 |

**Implementation:**
- API key from https://app.brevo.com/settings/keys/api
- Already implemented in `analyzer/distributor.py`

---

## Ticker & Sector Data Sources

### Recommended: Finnhub

**Why Finnhub:**
- **Free tier**: 60 API calls/minute, no daily limit
- **Coverage**: US stocks, ETFs, international
- **Data**: Tickers, company profiles, sectors, industries
- **API**: Clean REST API, good Python client

**Alternative: Alpha Vantage**
- **Free tier**: 25 API calls/day (very limited)
- **Pricing**: $50/month for 75 calls/minute
- Better for historical data, worse for our use case

**Comparison:**

| Service | Free Tier | Rate Limit | Best For |
|---------|-----------|------------|----------|
| **Finnhub** | 60/min | No daily cap | ✅ Ticker lookup, real-time |
| Alpha Vantage | 25/day | 5/min | Historical data |
| Yahoo Finance | Unofficial | N/A | Scraping (unreliable) |
| IEX Cloud | Limited | Varies | US stocks only |

**Implementation:**
- API key from https://finnhub.io/register
- Already implemented in `analyzer/ticker_normalizer.py`
- Falls back to fuzzy matching + manual mappings

---

## Manual Ticker Mappings

For common companies, we have hardcoded mappings (no API needed):

- Apple → AAPL
- Microsoft → MSFT
- Google/Alphabet → GOOGL
- Amazon → AMZN
- Tesla → TSLA
- Meta/Facebook → META
- Netflix → NFLX
- NVIDIA → NVDA
- Berkshire Hathaway → BRK.B
- And 30+ more...

This covers most S&P 500 companies without API calls.

---

## Architecture Decisions

1. **Brevo for email**: Best free tier, simple API, good deliverability
2. **Finnhub for tickers**: Generous free tier, comprehensive data
3. **Fuzzy matching fallback**: Thefuzz library for name similarity
4. **Caching**: Results cached to minimize API calls
5. **Async everywhere**: All I/O is async for efficiency

---

## Cost Estimate

**Monthly (weekly reports, ~100 subscribers):**

| Component | Cost |
|-----------|------|
| Brevo (300/day free) | $0 |
| Finnhub (60/min free) | $0 |
| Hosting (your macMini) | $0 |
| **Total** | **$0** |

If you exceed free tiers:
- Brevo: $9/month for 10k emails
- Finnhub: $15/month for higher limits

---

## Next Steps

1. Sign up for Brevo and get API key
2. Sign up for Finnhub and get API key (optional)
3. Configure `.env` file
4. Test with `capital-watch-analyzer send-test-email`
5. Set up cron job for weekly execution
