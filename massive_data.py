"""
Massive (formerly Polygon.io) API integration for institutional signals.
Rate-limit aware: uses 1-2 calls per cycle for free-plan compatibility.
"""
import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY", "").strip()
POLYGON_BASE = "https://api.polygon.io"

COMMODITY_SYMBOLS = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "CL=F": "Crude Oil",
    "BZ=F": "Brent Crude",
    "NG=F": "Natural Gas",
    "HG=F": "Copper",
}

US_MARKET_SYMBOLS = {
    "^TNX": "US10Y (10-Year Treasury)",
    "^DJI": "Dow Jones (US30)",
    "^IXIC": "NASDAQ (US100)",
    "^GSPC": "S&P 500",
    "DX-Y.NYB": "DXY (US Dollar Index)",
}

_last_req = 0.0


def _req(path: str, params: dict[str, Any] | None = None) -> dict | None:
    global _last_req
    if not MASSIVE_API_KEY:
        return None
    try:
        p = dict(params or {})
        p["apikey"] = MASSIVE_API_KEY
        url = f"{POLYGON_BASE}{path}?{urlencode(p)}"

        now = time.time()
        elapsed = now - _last_req
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)
        _last_req = time.time()

        with urlopen(url, timeout=15) as r:
            return json.load(r)
    except Exception as e:
        print(f"[POLYGON] {path}: {e}")
        return None


def fetch_market_news(limit: int = 15) -> list[dict]:
    data = _req("/v2/reference/news", {"limit": limit})
    if data:
        return data.get("results", [])
    return []


_BULLISH_KW = frozenset({
    "buy", "bullish", "upgrade", "outperform", "positive", "growth",
    "surge", "rally", "beat", "strong", "profit", "gain", "rise",
    "breakout", "momentum", "boom", "recovery", "rebound",
})

_BEARISH_KW = frozenset({
    "sell", "bearish", "downgrade", "underperform", "negative",
    "decline", "drop", "fall", "miss", "weak", "loss", "cut",
    "crash", "plunge", "slump", "recession", "slowdown", "risk",
})


def _score_article(article: dict) -> int:
    text = ((article.get("title") or "") + " " + (article.get("description") or "")).lower()
    score = sum(1 for kw in _BULLISH_KW if kw in text)
    score -= sum(1 for kw in _BEARISH_KW if kw in text)
    return score


def format_institutional_signal_block() -> str | None:
    articles = fetch_market_news(limit=15)
    if not articles:
        return None

    ticker_signals: dict[str, dict] = {}
    for art in articles:
        score = _score_article(art)
        tickers = art.get("tickers") or []
        title = art.get("title", "")
        for t in tickers:
            t = t.upper()
            if t not in ticker_signals:
                ticker_signals[t] = {"score": 0, "count": 0, "top_headline": title}
            ticker_signals[t]["score"] += score
            ticker_signals[t]["count"] += 1

    if not ticker_signals:
        return None

    scored = [(t, d["score"], d["count"], d["top_headline"]) for t, d in ticker_signals.items()]
    scored.sort(key=lambda x: x[1], reverse=True)

    top_bullish = [(t, s, c, h) for t, s, c, h in scored if s > 0][:4]
    top_bearish = [(t, s, c, h) for t, s, c, h in scored if s < 0][-4:]
    top_bearish.reverse()

    lines = [
        "\U0001f3db *INSTITUTIONAL SIGNALS*",
        "_Sentiment from Polygon.io News_",
        "\u2500" * 30,
        "",
    ]

    if top_bullish:
        lines.append("\U0001f7e2 *BULLISH (Institutional Buying)*")
        for t, s, c, h in top_bullish:
            hl = h[:90] if h else ""
            lines.append(f"\U0001f4c8 *{t}* [+{s}] x{c} articles")
            if hl:
                lines.append(f"  _{hl}_")
            lines.append("")

    if top_bearish:
        lines.append("\U0001f534 *BEARISH (Institutional Selling)*")
        for t, s, c, h in top_bearish:
            hl = h[:90] if h else ""
            lines.append(f"\U0001f4c9 *{t}* [{s}] x{c} articles")
            if hl:
                lines.append(f"  _{hl}_")
            lines.append("")

    if not top_bullish and not top_bearish:
        lines.append("_Market sentiment is mixed/neutral._")
        lines.append("")

    lines.append("\u2500" * 30)
    lines.append(f"\U0001f4e1 Updated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
    lines.append("\U0001f516 #institutional #signals #USstocks")
    return "\n".join(lines)


def format_commodity_signal_block() -> str | None:
    import yfinance as yf

    lines = ["\U0001f6e2 *COMMODITY WATCH*", "\u2500" * 30]
    has_data = False

    for symbol, name in COMMODITY_SYMBOLS.items():
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(period="3d")
            if hist.empty or len(hist) < 2:
                continue
            close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])
            change = close - prev_close
            pct = (change / prev_close) * 100
            sign = "+" if change >= 0 else ""
            emoji = "\U0001f7e2" if change >= 0 else "\U0001f534"
            lines.append(f"{emoji} *{name}*: ${close:.2f} ({sign}{pct:.2f}%)")
            has_data = True
        except Exception:
            pass

    if not has_data:
        return None

    lines.append("")
    lines.append("\U0001f516 #commodities #futures")
    return "\n".join(lines)


def format_us_market_block() -> str | None:
    import yfinance as yf
    lines = ["\U0001f1fa\U0001f1f8 *US MARKET DATA*", "\u2500" * 30]
    has_data = False
    for symbol, name in US_MARKET_SYMBOLS.items():
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(period="3d")
            if hist.empty or len(hist) < 2:
                continue
            close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])
            change = close - prev_close
            pct = (change / prev_close) * 100
            sign = "+" if change >= 0 else ""
            emoji = "\U0001f7e2" if change >= 0 else "\U0001f534"
            val = f"{close:.2f}" if "TNX" in symbol else f"{close:,.2f}"
            lines.append(f"{emoji} *{name}*: ${val} ({sign}{pct:.2f}%)")
            has_data = True
        except Exception:
            pass
    if not has_data:
        return None
    lines.append("")
    lines.append("\U0001f516 #US  #stocks #indices #economy")
    return "\n".join(lines)
