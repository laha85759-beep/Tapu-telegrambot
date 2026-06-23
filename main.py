import asyncio
import json
import os
from datetime import datetime, timezone
from html import escape
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from telegram import Bot

BOT_TOKEN = "8710452375:AAG-pqR8amkjx772hAYiLC_0WymUcoruVqE"
TELEGRAM_CHAT_ID = "6207722743"
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "").strip()
NEWS_API_KEY = "f1f7db9dc3354374a5f03aa7652fd49b"
NEWSDATA_API_URL = "https://newsdata.io/api/1/latest"
NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWS_PROVIDER = os.getenv("NEWS_PROVIDER", "auto").strip().lower()
NEWS_QUERY = os.getenv(
    "NEWS_QUERY",
    'forex OR "foreign exchange" OR (dollar AND fed) OR (euro AND ecb) OR (pound AND boe) OR (yen AND boj) OR (gold AND fed) OR (rupee AND rbi) OR (sensex AND market) OR (nifty AND market)',
)
FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", "900"))
MAX_ARTICLES_PER_CYCLE = int(os.getenv("MAX_ARTICLES_PER_CYCLE", "5"))

FOREX_TERMS = {
    "forex",
    "currency",
    "currencies",
    "fx",
    "usd",
    "dollar",
    "eur",
    "euro",
    "gbp",
    "pound",
    "jpy",
    "yen",
    "xau",
    "gold",
    "fed",
    "ecb",
    "boe",
    "boj",
    "rate hike",
    "rate cut",
    "inflation",
    "cpi",
    "nonfarm payrolls",
    "inr",
    "rupee",
    "rbi",
    "sensex",
    "nifty",
    "india market",
    "bse",
    "nse",
}

CURRENCY_HINTS = {
    "USD": ("usd", "dollar", "fed", "treasury"),
    "EUR": ("eur", "euro", "ecb"),
    "GBP": ("gbp", "pound", "boe", "bank of england"),
    "JPY": ("jpy", "yen", "boj", "bank of japan"),
    "XAU": ("xau", "gold", "bullion"),
    "INR": ("inr", "rupee", "rbi", "india", "sensex", "nifty"),
}

TRADE_PAIRS = {
    "USD": [("EUR/USD", -1, 0.0001), ("USD/JPY", 1, 0.01), ("GBP/USD", -1, 0.0001), ("USD/CAD", 1, 0.0001)],
    "EUR": [("EUR/USD", 1, 0.0001), ("EUR/GBP", 1, 0.0001)],
    "GBP": [("GBP/USD", 1, 0.0001), ("EUR/GBP", -1, 0.0001)],
    "JPY": [("USD/JPY", -1, 0.01)],
    "XAU": [("XAU/USD", 1, 0.1)],
    "INR": [("USD/INR", 1, 0.01)],
}

FOREX_PRICE_API = "https://api.exchangerate-api.com/v4/latest/USD"

POSITIVE_KEYWORDS = {
    "rises",
    "rise",
    "gains",
    "gain",
    "surges",
    "surge",
    "strengthens",
    "strong",
    "hawkish",
    "beats",
    "beat",
    "higher",
    "upside",
}

NEGATIVE_KEYWORDS = {
    "falls",
    "fall",
    "drops",
    "drop",
    "slides",
    "slide",
    "weakens",
    "weak",
    "dovish",
    "misses",
    "miss",
    "lower",
    "downside",
    "cut",
}


def get_active_provider() -> str:
    if NEWS_PROVIDER in {"newsdata", "newsapi"}:
        return NEWS_PROVIDER
    if NEWS_API_KEY:
        return "newsapi"
    return "newsdata"


def build_newsdata_url() -> str:
    params = {
        "apikey": NEWSDATA_API_KEY,
        "q": NEWS_QUERY,
        "language": "en",
        "category": "business",
    }
    return f"{NEWSDATA_API_URL}?{urlencode(params)}"


def build_newsapi_url() -> str:
    params = {
        "apiKey": NEWS_API_KEY,
        "q": NEWS_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": "25",
    }
    return f"{NEWSAPI_URL}?{urlencode(params)}"


def normalize_newsdata_article(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "article_id": article.get("article_id") or article.get("link") or article.get("title"),
        "title": article.get("title"),
        "description": article.get("description"),
        "link": article.get("link"),
        "pubDate": article.get("pubDate"),
        "source_name": article.get("source_name"),
        "keywords": article.get("keywords") or [],
    }


def normalize_newsapi_article(article: dict[str, Any]) -> dict[str, Any]:
    source = article.get("source") or {}
    return {
        "article_id": article.get("url") or article.get("title") or article.get("publishedAt"),
        "title": article.get("title"),
        "description": article.get("description") or article.get("content"),
        "link": article.get("url"),
        "pubDate": article.get("publishedAt"),
        "source_name": source.get("name") or "Unknown source",
        "keywords": [],
    }


def article_key(article: dict[str, Any]) -> str:
    return str(
        article.get("article_id")
        or article.get("link")
        or article.get("title")
        or article.get("pubDate")
        or ""
    )


def normalize_text(article: dict[str, Any]) -> str:
    parts = [
        article.get("title") or "",
        article.get("description") or "",
        " ".join(article.get("keywords") or []),
        article.get("source_name") or "",
    ]
    return " ".join(parts).lower()


def is_forex_relevant(article: dict[str, Any]) -> bool:
    text = normalize_text(article)
    return any(term in text for term in FOREX_TERMS)


def infer_bias_signal(article: dict[str, Any]) -> str | None:
    text = normalize_text(article)

    subject = None
    for symbol, hints in CURRENCY_HINTS.items():
        if any(hint in text for hint in hints):
            subject = symbol
            break

    if not subject:
        return None

    score = sum(1 for word in POSITIVE_KEYWORDS if word in text)
    score -= sum(1 for word in NEGATIVE_KEYWORDS if word in text)

    if score == 0:
        return None

    direction = "Bullish" if score > 0 else "Bearish"
    return f"{direction} {subject}"


def fetch_current_prices() -> dict[str, float]:
    rates: dict[str, float] = {}
    try:
        with urlopen(FOREX_PRICE_API, timeout=10) as r:
            data = json.load(r)
        base_rates = data.get("rates", {})
        usd_base = {"USD": 1.0} | base_rates
        for pair, _, pip in TRADE_PAIRS.get("USD", []):
            base, quote = pair.split("/")
            b_rate = usd_base.get(base)
            q_rate = usd_base.get(quote)
            if b_rate and q_rate:
                rates[pair] = q_rate / b_rate
        for asset, pairs in TRADE_PAIRS.items():
            for pair, _, _ in pairs:
                if pair in rates:
                    continue
                base, quote = pair.split("/")
                b_rate = usd_base.get(base)
                q_rate = usd_base.get(quote)
                if b_rate and q_rate:
                    rates[pair] = q_rate / b_rate
    except Exception:
        pass
    return rates


def generate_trade_suggestion(bias: str) -> str | None:
    parts = bias.split()
    if len(parts) != 2:
        return None
    direction, asset = parts[0], parts[1]
    pairs = TRADE_PAIRS.get(asset)
    if not pairs:
        return None
    is_bullish = direction == "Bullish"
    prices = fetch_current_prices()
    suggestions = []
    for pair, multiplier, pip_size in pairs:
        action = "BUY" if (is_bullish == (multiplier > 0)) else "SELL"
        price = prices.get(pair)
        if price:
            entry = round(price, 4)
            tp = round(price + (50 * pip_size) if action == "BUY" else price - (50 * pip_size), 4)
            sl = round(price - (20 * pip_size) if action == "BUY" else price + (20 * pip_size), 4)
            suggestions.append(f"{action} {pair} @ {entry} | TP: {tp} | SL: {sl}")
        else:
            suggestions.append(f"{action} {pair}")
    signal_icon = "BULLISH" if is_bullish else "BEARISH"
    return f"<b>Trade Ideas [{signal_icon}]:</b> {', '.join(suggestions)}"


def format_article_message(article: dict[str, Any]) -> str:
    title = escape(article.get("title") or "Untitled update")
    source = escape(article.get("source_name") or "Unknown source")
    published = escape(article.get("pubDate") or "Unknown time")
    summary = escape((article.get("description") or "No description available.")[:400])
    link = article.get("link") or ""
    bias = infer_bias_signal(article)

    lines = [
        "<b>Forex News Alert</b>",
        f"<b>Headline:</b> {title}",
        f"<b>Source:</b> {source}",
        f"<b>Published:</b> {published}",
        f"<b>Summary:</b> {summary}",
    ]

    if bias:
        lines.append(f"<b>News Bias:</b> {escape(bias)}")
        trade_suggestion = generate_trade_suggestion(bias)
        if trade_suggestion:
            lines.append(trade_suggestion)

    if link:
        lines.append(link)

    return "\n".join(lines)


def load_newsdata_articles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("status") not in {None, "success"}:
        raise RuntimeError(f"Newsdata API returned status {payload.get('status')!r}")
    results = payload.get("results") or []
    if not isinstance(results, list):
        raise RuntimeError("Newsdata API payload did not contain a list of results")
    return [normalize_newsdata_article(item) for item in results if isinstance(item, dict)]


def load_newsapi_articles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("status") != "ok":
        raise RuntimeError(
            f"News API returned status {payload.get('status')!r}: {payload.get('message', 'unknown error')}"
        )
    articles = payload.get("articles") or []
    if not isinstance(articles, list):
        raise RuntimeError("News API payload did not contain a list of articles")
    return [normalize_newsapi_article(item) for item in articles if isinstance(item, dict)]


def fetch_latest_articles() -> list[dict[str, Any]]:
    provider = get_active_provider()
    url = build_newsapi_url() if provider == "newsapi" else build_newsdata_url()
    with urlopen(url, timeout=30) as response:
        payload = json.load(response)

    if provider == "newsapi":
        return load_newsapi_articles(payload)
    return load_newsdata_articles(payload)


def is_recent(article: dict[str, Any], max_age_hours: int = 2) -> bool:
    pub_date = article.get("pubDate") or ""
    if not pub_date:
        return False
    try:
        dt_str = pub_date.replace("Z", "+00:00")
        if "+" not in dt_str and dt_str.count("-") == 2:
            dt_str += "+00:00"
        pub = datetime.fromisoformat(dt_str)
        delta = datetime.now(timezone.utc) - pub
        return delta.total_seconds() < max_age_hours * 3600
    except Exception:
        return True


async def send_articles(bot: Bot, chat_id: str, articles: list[dict[str, Any]], seen_keys: set[str]) -> int:
    sent_count = 0
    for article in articles:
        key = article_key(article)
        if not key or key in seen_keys or not is_forex_relevant(article) or not is_recent(article):
            continue

        await bot.send_message(
            chat_id=chat_id,
            text=format_article_message(article),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        seen_keys.add(key)
        sent_count += 1

        if sent_count >= MAX_ARTICLES_PER_CYCLE:
            break

    return sent_count


async def run_worker_cycle(bot: Bot, chat_id: str, seen_keys: set[str]) -> int:
    articles = fetch_latest_articles()
    return await send_articles(bot, chat_id, articles, seen_keys)


def validate_config() -> list[str]:
    missing = []
    if BOT_TOKEN == "PLACEHOLDER_TOKEN_REVOKED":
        missing.append("BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")

    provider = get_active_provider()
    if provider == "newsapi":
        if not NEWS_API_KEY:
            missing.append("NEWS_API_KEY")
    elif not NEWSDATA_API_KEY:
        missing.append("NEWSDATA_API_KEY")

    return missing


async def worker_loop() -> None:
    bot = Bot(BOT_TOKEN)
    seen_keys: set[str] = set()
    provider = get_active_provider()

    print("LiveForexSignalsAI worker started.")
    print(f"Polling {provider} every {FETCH_INTERVAL_SECONDS} seconds.")

    while True:
        try:
            sent_count = await run_worker_cycle(bot, TELEGRAM_CHAT_ID, seen_keys)
            print(f"Worker cycle complete. Sent {sent_count} article(s).")
        except Exception as exc:
            print(f"[ERROR] Worker cycle failed: {exc}")

        await asyncio.sleep(FETCH_INTERVAL_SECONDS)


def main() -> int:
    print("Launching LiveForexSignalsAI Bot Engine...")
    missing = validate_config()
    if missing:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing)}")
        return 1

    asyncio.run(worker_loop())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
