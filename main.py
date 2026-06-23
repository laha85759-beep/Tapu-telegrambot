import asyncio
import json
import os
from html import escape
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN", "PLACEHOLDER_TOKEN_REVOKED")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "").strip()
NEWSDATA_API_URL = "https://newsdata.io/api/1/latest"
NEWS_QUERY = os.getenv(
    "NEWS_QUERY",
    "forex OR usd OR eur OR gbp OR jpy OR xauusd OR gold OR fed OR ecb",
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
}

CURRENCY_HINTS = {
    "USD": ("usd", "dollar", "fed", "treasury"),
    "EUR": ("eur", "euro", "ecb"),
    "GBP": ("gbp", "pound", "boe", "bank of england"),
    "JPY": ("jpy", "yen", "boj", "bank of japan"),
    "XAU": ("xau", "gold", "bullion"),
}

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


def build_newsdata_url() -> str:
    params = {
        "apikey": NEWSDATA_API_KEY,
        "q": NEWS_QUERY,
        "language": "en",
        "category": "business",
    }
    return f"{NEWSDATA_API_URL}?{urlencode(params)}"


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

    if link:
        lines.append(link)

    return "\n".join(lines)


def load_articles_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("status") not in {None, "success"}:
        raise RuntimeError(f"Newsdata API returned status {payload.get('status')!r}")
    results = payload.get("results") or []
    if not isinstance(results, list):
        raise RuntimeError("Newsdata API payload did not contain a list of results")
    return [item for item in results if isinstance(item, dict)]


def fetch_latest_articles() -> list[dict[str, Any]]:
    url = build_newsdata_url()
    with urlopen(url, timeout=30) as response:
        payload = json.load(response)
    return load_articles_from_payload(payload)


async def send_articles(bot: Bot, chat_id: str, articles: list[dict[str, Any]], seen_keys: set[str]) -> int:
    sent_count = 0
    for article in articles:
        key = article_key(article)
        if not key or key in seen_keys or not is_forex_relevant(article):
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
    if not NEWSDATA_API_KEY:
        missing.append("NEWSDATA_API_KEY")
    return missing


async def worker_loop() -> None:
    bot = Bot(BOT_TOKEN)
    seen_keys: set[str] = set()

    print("LiveForexSignalsAI worker started.")
    print(f"Polling Newsdata every {FETCH_INTERVAL_SECONDS} seconds.")

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
