# India Market Sentiment Trader

24/7 real-time **market sentiment analyzer and trading bot** for Indian NSE/BSE markets.

- **Broker:** Angel One SmartAPI (primary), with `MockBroker` for paper/dev and a swappable `KiteBroker` stub for later
- **Sentiment:** VADER (default) or optional FinBERT on Indian financial news + Reddit
- **Markets:** NSE cash equity watchlist (Nifty-heavy), IST session-aware execution

## Features

- RSS ingestion from Moneycontrol, Economic Times, Business Standard
- Reddit polling from r/IndiaInvestments and r/IndianStreetBets
- Rolling time-decayed sentiment aggregation per symbol
- Signal engine combining sentiment + price momentum + volume filter
- Risk controls: max position %, daily loss limit, cooldown, market-hours gate
- Prometheus metrics at `/metrics`, health at `/health`
- Docker Compose stack: bot + Redis + TimescaleDB

## Quick start (mock / paper mode)

No broker credentials required for development:

```bash
cd india-market-sentiment-trader
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# broker.provider is already `mock` in config/settings.yaml

pytest -q
sentiment-trader
```

The bot runs a **mock quote feed** and paper broker. Sentiment is scored from live RSS feeds.

## Angel One live mode

1. Create a SmartAPI app at [smartapi.angelbroking.com](https://smartapi.angelbroking.com/)
2. Fill `.env`:

```env
ANGEL_API_KEY=...
ANGEL_CLIENT_CODE=...
ANGEL_PIN=...
ANGEL_TOTP_SECRET=...
```

3. Set `broker.provider: angel_one` in `config/settings.yaml`
4. Install Angel SDK manually: `pip install git+https://github.com/angel-one/smartapi-python.git`
5. Register a **static IP** with Angel One before placing live orders (required from Oct 2025)

Daily session: Angel `jwtToken` and `feedToken` expire each trading day. Run morning login via `AngelAuthSession.login()` before market open.

## Configuration

| File | Purpose |
|------|---------|
| `config/settings.yaml` | Broker, market hours, sentiment, signals, risk |
| `config/watchlist.yaml` | NSE symbols + text aliases for ticker linking |

## Architecture

```
RSS / Reddit → Preprocess → VADER/FinBERT → Ticker Linker → Aggregator
                                                              ↓
Mock quotes / Angel WS → Quote cache → Signal Engine → Risk Manager → Broker
```

## Docker

```bash
docker compose up --build
```

## Switching brokers later

Implement `KiteBroker` in `src/sentiment_trader/execution/brokers/kite.py` and set:

```yaml
broker:
  provider: kite
```

All sentiment and signal logic stays unchanged.

## Disclaimer

Educational software only. Live trading in Indian markets requires compliance with SEBI regulations, tax reporting, and acceptance of financial risk. No profitability is guaranteed.

## License

MIT
