# LiveForexSignalsAI App Engine

This worker fetches forex-relevant headlines from Newsdata and forwards them to a Telegram channel on a continuous loop.

## What it does
- Polls `https://newsdata.io/api/1/latest`
- Filters for forex and macro headlines
- Adds a lightweight news-bias label such as `Bullish USD` when the headline language is directional
- Sends fresh items to your Telegram channel
- Runs as a 24/7 Render worker

## Required environment variables
- `BOT_TOKEN`: your Telegram bot token
- `TELEGRAM_CHAT_ID`: your target Telegram channel or chat id, for example `@your_channel_name`
- `NEWSDATA_API_KEY`: your Newsdata API key

## Optional environment variables
- `FETCH_INTERVAL_SECONDS`: polling interval in seconds, default `900`
- `MAX_ARTICLES_PER_CYCLE`: max Telegram posts per poll, default `5`
- `NEWS_QUERY`: Newsdata query string, default `forex OR usd OR eur OR gbp OR jpy OR xauusd OR gold OR fed OR ecb`

## Local run
1. Install dependencies: `pip install -r requirements.txt`
2. Set the required environment variables
3. Run: `python main.py`

## Render worker
The included `render.yaml` already starts the worker with:
- build command: `pip install -r requirements.txt`
- start command: `python main.py`
