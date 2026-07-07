"""Quick high-impact news check — runs every 5 min via GitHub Actions."""
import asyncio
import os
import sys

from telegram import Bot

from main import (
    BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    FOREX_QUERY,
    article_key,
    fetch_latest_articles,
    format_high_impact_alert,
    identify_asset,
    infer_bias_signal,
    compute_confidence,
    _confidence_pct,
    ai_analyze_news,
    is_high_impact,
    is_recent,
    load_seen_keys,
    save_seen_keys,
    load_subscribers,
)

SENT_KEYS_FILE = "sent_articles.json"


async def run_once() -> int:
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN not set")
        return 1

    # Load state
    seen_keys = load_seen_keys()
    subscribers = load_subscribers()
    bot = Bot(BOT_TOKEN)

    sent = 0
    articles = fetch_latest_articles(FOREX_QUERY)

    for article in articles:
        if not is_recent(article, max_age_hours=6):
            continue
        if not is_high_impact(article):
            continue

        key = article_key(article)
        if not key:
            continue
        full_key = f"forex:{key}"
        if full_key in seen_keys:
            continue

        # Send high-impact alert
        asset = identify_asset(article)
        text = (article.get("title") or "") + " " + (article.get("description") or "")
        bias = infer_bias_signal(article)
        direction, confidence = "Neutral", "Low"
        if bias:
            direction, confidence = compute_confidence(text)
        ai_analysis = ai_analyze_news(article) or ""
        conf_pct = _confidence_pct(confidence)

        alert = format_high_impact_alert(
            title=article.get("title", "Breaking News"),
            asset=asset,
            direction=direction,
            confidence_pct=conf_pct,
            analysis=ai_analysis or "Significant market-moving event detected.",
        )

        cid = int(TELEGRAM_CHAT_ID) if TELEGRAM_CHAT_ID else None
        targets = list(subscribers)
        if cid and cid not in targets:
            targets.insert(0, cid)

        for cid_target in targets:
            try:
                await bot.send_message(
                    chat_id=cid_target,
                    text=alert,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                sent += 1
            except Exception as e:
                print(f"[ERROR] Send to {cid_target}: {e}")

        seen_keys.add(full_key)
        save_seen_keys(seen_keys)
        title = (article.get("title") or "")[:80]
        print(f"[HIGH IMPACT] Sent: {title}")

    print(f"[HIGH IMPACT] Check complete. Sent {sent} alert(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_once()))
