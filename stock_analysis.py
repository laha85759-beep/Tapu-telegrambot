"""
stock_analysis.py — Comprehensive US stock analysis module.
Combines multi-timeframe technical data, fundamental metrics,
news sentiment analysis, and AI-powered dual recommendations
(short-term day trading + long-term investing).

Maps the n8n-based stock-analysis-telegram-bot workflow into Python.
"""

import os
from typing import Any

import requests
import yfinance as yf

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "").strip()

# Maps internal asset symbols to yfinance tickers (reuses main.py mapping)
YF_TICKER_MAP: dict[str, str] = {
    "AAPL": "AAPL", "MSFT": "MSFT", "GOOGL": "GOOGL",
    "AMZN": "AMZN", "NVDA": "NVDA", "META": "META",
    "TSLA": "TSLA", "JPM": "JPM", "V": "V",
    "WMT": "WMT", "JNJ": "JNJ", "PG": "PG",
    "XOM": "XOM", "UNH": "UNH", "HD": "HD",
    "BAC": "BAC", "DIS": "DIS", "NFLX": "NFLX",
    "ADBE": "ADBE", "CRM": "CRM", "INTC": "INTC",
    "AMD": "AMD", "PYPL": "PYPL", "UBER": "UBER",
    "NKE": "NKE", "BA": "BA", "COIN": "COIN",
    "SNAP": "SNAP", "SQ": "SQ", "PLTR": "PLTR",
    "RBLX": "RBLX", "MCD": "MCD", "SBUX": "SBUX",
    "NIO": "NIO", "RIVN": "RIVN",
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS", "INFY": "INFY.NS",
    "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "BHARTI": "BHARTIARTL.NS", "WIPRO": "WIPRO.NS",
    "ITC": "ITC.NS", "LT": "LT.NS",
    "AXISBANK": "AXISBANK.NS", "KOTAKBANK": "KOTAKBANK.NS",
    "MARUTI": "MARUTI.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "ASIANPAINT": "ASIANPAINT.NS", "HCLTECH": "HCLTECH.NS",
    "SUNPHARMA": "SUNPHARMA.NS", "BAJFINANCE": "BAJFINANCE.NS",
    "TITAN": "TITAN.NS", "NTPC": "NTPC.NS",
    "ONGC": "ONGC.NS", "POWERGRID": "POWERGRID.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS", "TATASTEEL": "TATASTEEL.NS",
    "JSWSTEEL": "JSWSTEEL.NS", "HINDALCO": "HINDALCO.NS",
    "TECHM": "TECHM.NS", "COALINDIA": "COALINDIA.NS",
    "HINDUNILVR": "HINDUNILVR.NS", "BRITANNIA": "BRITANNIA.NS",
    "NESTLEIND": "NESTLEIND.NS", "M&M": "M&M.NS",
    "EICHERMOT": "EICHERMOT.NS", "HEROMOTOCO": "HEROMOTOCO.NS",
    "TATACONSUM": "TATACONSUM.NS", "DABUR": "DABUR.NS",
    "MARICO": "MARICO.NS", "HDFC": "HDFC.NS",
    "ICICIPRUDI": "ICICIPRUDI.NS", "HDFCLIFE": "HDFCLIFE.NS",
    "SBILIFE": "SBILIFE.NS", "TRENT": "TRENT.NS",
    "AVENUE": "AVENUE.NS", "PIDILITIND": "PIDILITIND.NS",
    "HAVELLS": "HAVELLS.NS", "SIEMENS": "SIEMENS.NS",
    "BEL": "BEL.NS", "BHEL": "BHEL.NS",
    "HAL": "HAL.NS", "IRFC": "IRFC.NS",
    "IREDA": "IREDA.NS", "SUZLON": "SUZLON.NS",
    "ADANIENT": "ADANIENT.NS", "ADANIPORTS": "ADANIPORTS.NS",
    "ADANIGREEN": "ADANIGREEN.NS", "ADANITRANS": "ADANITRANS.NS",
    "ADANIPOWER": "ADANIPOWER.NS",
    "HINDZINC": "HINDZINC.NS", "VEDL": "VEDL.NS",
    "IOC": "IOC.NS", "BPCL": "BPCL.NS",
    "GAIL": "GAIL.NS", "NATIONALUM": "NATIONALUM.NS",
    "ZOMATO": "ZOMATO.NS", "SWIGGY": "SWIGGY.NS",
    "PAYTM": "PAYTM.NS", "POLICYBZR": "POLICYBZR.NS",
    "NYKAA": "NYKAA.NS", "HDFCAMC": "HDFCAMC.NS",
    "GRASIM": "GRASIM.NS", "DIVISLAB": "DIVISLAB.NS",
    "CIPLA": "CIPLA.NS", "DRREDDY": "DRREDDY.NS",
    "APOLLOHOSP": "APOLLOHOSP.NS", "AUROPHARMA": "AUROPHARMA.NS",
    "TVSMOTOR": "TVSMOTOR.NS",
}

# Known US stock symbols for quick detection
US_STOCKS = frozenset({
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META",
    "TSLA", "JPM", "V", "WMT", "JNJ", "PG", "XOM", "UNH",
    "HD", "BAC", "DIS", "NFLX", "ADBE", "CRM", "INTC", "AMD",
    "PYPL", "UBER", "NKE", "BA", "COIN", "SNAP", "SQ", "PLTR",
    "RBLX", "MCD", "SBUX", "NIO", "RIVN", "ORCL", "IBM",
    "CSCO", "QCOM", "TXN", "AVGO", "NOW", "SPGI", "BLK",
    "SCHW", "GS", "MS", "C", "AXP", "MA", "PYPL", "AMAT",
    "MU", "ABNB", "DASH", "SNAP", "UBER", "LYFT", "PINS",
})

# Symbols known to exist as company tickers (not forex/commodity)
STOCK_SYMBOLS = frozenset(list(YF_TICKER_MAP.keys()) + list(US_STOCKS))


def _yf_ticker(symbol: str) -> str:
    """Resolve internal symbol to yfinance ticker."""
    return YF_TICKER_MAP.get(symbol.upper(), symbol.upper())


def _call_ai(prompt: str, system_prompt: str | None = None) -> str | None:
    """Try OpenAI first, fall back to Groq."""
    result = _openai_chat(prompt, system_prompt)
    if result:
        return result
    return _groq_chat(prompt, system_prompt)


def _openai_chat(prompt: str, system_prompt: str | None = None) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "max_tokens": 1200,
            },
            timeout=25,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _groq_chat(prompt: str, system_prompt: str | None = None) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
            },
            timeout=25,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def fetch_stock_info(symbol: str) -> dict[str, Any]:
    """Fetch company profile, current price, and fundamental metrics."""
    ticker = _yf_ticker(symbol)
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
    change = (price - prev_close) if price and prev_close else None
    change_pct = ((price - prev_close) / prev_close * 100) if price and prev_close else None

    dy = info.get("dividendYield")
    return {
        "name": info.get("longName", symbol),
        "short_name": info.get("shortName", symbol),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "price": price,
        "prev_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "market_cap": info.get("marketCap"),
        "beta": info.get("beta"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "peg_ratio": info.get("pegRatio"),
        "dividend_yield": dy * 100 if dy else None,
        "dividend_rate": info.get("dividendRate"),
        "eps": info.get("trailingEps"),
        "eps_growth": info.get("earningsGrowth"),
        "revenue_growth": info.get("revenueGrowth"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "debt_to_equity": info.get("debtToEquity"),
        "fifty_two_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_low": info.get("fiftyTwoWeekLow"),
        "description": (info.get("longBusinessSummary") or "")[:400],
        "website": info.get("website", ""),
        "exchange": info.get("exchange", ""),
    }


def fetch_multi_timeframe_candles(symbol: str) -> dict[str, dict[str, Any]]:
    """Fetch candle data across 1min, 15min, and 1h timeframes (100 candles each)."""
    ticker = _yf_ticker(symbol)
    stock = yf.Ticker(ticker)
    result: dict[str, dict[str, Any]] = {}

    periods = [
        ("1m", "5d", "1min"),
        ("15m", "1mo", "15min"),
        ("1h", "3mo", "1hour"),
    ]

    for interval, period, label in periods:
        try:
            hist = stock.history(interval=interval, period=period)
            if not hist.empty:
                recent = hist.tail(100)
                close = float(recent["Close"].iloc[-1])
                open_ = float(recent["Open"].iloc[-1])
                high = float(recent["High"].max())
                low = float(recent["Low"].min())
                chg_pct = ((close - open_) / open_ * 100) if open_ else 0
                result[label] = {
                    "current": close,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "volume_avg": float(recent["Volume"].mean()),
                    "change_pct": chg_pct,
                }
        except Exception:
            pass

    return result


def fetch_news_sentiment(symbol: str) -> dict[str, Any]:
    """Fetch recent news and analyze sentiment using AI."""
    try:
        ticker = _yf_ticker(symbol)
        stock = yf.Ticker(ticker)
        news_items = stock.news[:5]

        if not news_items:
            return {
                "sentiment": "Neutral",
                "score": 0.0,
                "articles": [],
                "rationale": "No recent news found.",
            }

        articles: list[dict[str, str]] = []
        headlines: list[str] = []
        for item in news_items:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            publisher = (item.get("publisher") or "").strip()
            link = (item.get("link") or "").strip()
            articles.append({"title": title, "publisher": publisher, "link": link})
            headlines.append(f"- {title}")

        if not headlines:
            return {
                "sentiment": "Neutral",
                "score": 0.0,
                "articles": [],
                "rationale": "No recent news found.",
            }

        headlines_text = "\n".join(headlines)

        prompt = f"""Analyze the sentiment of these news headlines for stock ${symbol}:

{headlines_text}

Provide:
SENTIMENT: Positive/Neutral/Negative
SCORE: -1.0 to 1.0
RATIONALE: Brief explanation (1-2 sentences)"""

        result = _call_ai(
            prompt,
            "You are a financial news sentiment analyst. Be objective and data-driven.",
        )

        sentiment = "Neutral"
        score = 0.0
        rationale = "Could not determine sentiment."

        if result:
            for line in result.strip().split("\n"):
                line = line.strip()
                if line.upper().startswith("SENTIMENT:"):
                    sentiment = line.split(":", 1)[-1].strip()
                elif line.upper().startswith("SCORE:"):
                    try:
                        score = float(line.split(":", 1)[-1].strip())
                    except ValueError:
                        pass
                elif line.upper().startswith("RATIONALE:"):
                    rationale = line.split(":", 1)[-1].strip()

        return {
            "sentiment": sentiment,
            "score": score,
            "articles": articles[:3],
            "rationale": rationale,
        }

    except Exception as exc:
        print(f"[STOCK SENTIMENT] Error for {symbol}: {exc}")
        return {
            "sentiment": "Neutral",
            "score": 0.0,
            "articles": [],
            "rationale": "Could not fetch news.",
        }


def fetch_twelvedata_candles(symbol: str) -> dict[str, Any]:
    """Optional TwelveData fetch for multi-timeframe data (replaces yfinance if key set)."""
    if not TWELVEDATA_API_KEY:
        return {}
    result: dict[str, Any] = {}
    intervals = {"1min": "1min", "15min": "15min", "1hour": "1h"}
    for label, interval in intervals.items():
        try:
            from urllib.parse import urlencode
            from urllib.request import urlopen
            import json

            params = urlencode({
                "symbol": symbol,
                "interval": interval,
                "outputsize": "100",
                "apikey": TWELVEDATA_API_KEY,
            })
            url = f"https://api.twelvedata.com/time_series?{params}"
            with urlopen(url, timeout=10) as r:
                data = json.load(r)
            values = data.get("values", [])
            if values:
                closes = [float(v["close"]) for v in values if "close" in v]
                highs = [float(v["high"]) for v in values if "high" in v]
                lows = [float(v["low"]) for v in values if "low" in v]
                volumes = [float(v.get("volume", 0)) for v in values if "volume" in v]
                if closes:
                    result[label] = {
                        "current": closes[-1],
                        "open": float(values[-1].get("open", 0)),
                        "high": max(highs),
                        "low": min(lows),
                        "volume_avg": sum(volumes) / len(volumes) if volumes else 0,
                        "change_pct": ((closes[-1] - closes[0]) / closes[0] * 100),
                    }
        except Exception:
            pass
    return result


def _fmt_price(val: float | None) -> str:
    if val is None:
        return "N/A"
    if abs(val) >= 1000:
        return f"${val:,.2f}"
    if abs(val) >= 1:
        return f"${val:.2f}"
    return f"${val:.4f}"


def _fmt_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"


def _fmt_billions(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"${val / 1_000_000_000:,.2f}B"


def comprehensive_analysis(symbol: str, question: str = "") -> str | None:
    """Full comprehensive stock analysis combining technical, fundamental, and sentiment data.

    Produces HTML-formatted output ready for Telegram.
    """
    try:
        symbol = symbol.upper().strip()
        info = fetch_stock_info(symbol)

        if not info.get("price"):
            return (
                f"<b>Could not fetch data for {symbol}.</b>\n"
                f"Please check the ticker symbol and try again.\n"
                f"Examples: AAPL, MSFT, GOOGL, TSLA, RELIANCE"
            )

        candles = fetch_multi_timeframe_candles(symbol)
        sentiment_data = fetch_news_sentiment(symbol)

        price = info["price"]
        change_str = ""
        if info.get("change_pct") is not None:
            sign = "+" if info["change_pct"] >= 0 else ""
            change_str = f" ({sign}{info['change_pct']:.2f}%)"

        dy_str = f"{info['dividend_yield']:.2f}%" if info.get("dividend_yield") else "N/A"
        pe = info.get("pe_ratio")
        fpe = info.get("forward_pe")
        pb = info.get("pb_ratio")
        eps = info.get("eps")
        mcap = info.get("market_cap")
        beta = info.get("beta")
        roe_str = f"{info['roe'] * 100:.2f}%" if info.get("roe") else "N/A"
        high52 = info.get("fifty_two_high")
        low52 = info.get("fifty_two_low")

        # Build context for AI
        context_parts = [
            f"Company: {info['name']} ({symbol})",
            f"Sector: {info['sector']} | Industry: {info['industry']}",
            f"Current Price: ${price:.2f}{change_str}",
            f"Market Cap: {_fmt_billions(mcap)}",
        ]
        if pe:
            context_parts.append(f"P/E Ratio: {pe:.2f}")
        if fpe:
            context_parts.append(f"Forward P/E: {fpe:.2f}")
        if pb:
            context_parts.append(f"P/B Ratio: {pb:.2f}")
        if dy_str != "N/A":
            context_parts.append(f"Dividend Yield: {dy_str}")
        if eps:
            context_parts.append(f"EPS: ${eps:.2f}")
        if beta:
            context_parts.append(f"Beta: {beta:.2f}")
        if roe_str != "N/A":
            context_parts.append(f"ROE: {roe_str}")
        if low52 and high52:
            context_parts.append(f"52-Week Range: {_fmt_price(low52)} - {_fmt_price(high52)}")

        for tf, data in candles.items():
            context_parts.append(
                f"{tf}: ${data['current']:.2f} "
                f"(H: ${data['high']:.2f}, L: ${data['low']:.2f}, "
                f"Chg: {_fmt_pct(data['change_pct'])}, "
                f"Vol Avg: {data.get('volume_avg', 0):,.0f})"
            )

        sent_icon_map = {"Positive": "🟢", "Neutral": "🟡", "Negative": "🔴"}
        sent_icon = sent_icon_map.get(sentiment_data["sentiment"], "🟡")
        context_parts.append(
            f"\nNews Sentiment: {sentiment_data['sentiment']} "
            f"({sentiment_data['score']:.2f})"
        )
        context_parts.append(f"Sentiment Rationale: {sentiment_data['rationale']}")

        if sentiment_data["articles"]:
            context_parts.append("\nRecent Headlines:")
            for a in sentiment_data["articles"]:
                context_parts.append(f"  - {a['title']}")

        if question:
            context_parts.append(f"\nUser Question: {question}")

        context = "\n".join(p for p in context_parts if p)

        # AI analysis prompt — replicates the n8n workflow's DeepSeek analysis
        prompt = f"""You are a professional financial analyst. Analyze {symbol} based on the data below.

Provide a comprehensive analysis with these exact sections:

── SHORT-TERM TRADING (Day Trading) ──
Recommendation: BUY/SELL/HOLD
Entry Price: $X.XX
Stop-Loss: $X.XX
Target Price: $X.XX
Rationale: 1-2 sentence explanation

── LONG-TERM INVESTMENT ──
Recommendation: BUY/HOLD/AVOID
Dividend Yield: X.XX%
Expected Annual Return: X.X%
P/E Ratio: X.XX
Key Strengths:
  - Point 1
  - Point 2
Key Risks:
  - Point 1
  - Point 2
Rationale: 1-2 sentence explanation

── OVERALL ASSESSMENT ──
Risk Level: LOW/MEDIUM/HIGH
Summary: 1-2 sentence conclusion

DATA:
{context}"""

        analysis = _call_ai(
            prompt,
            "You are a professional financial analyst. Be factual, specific with price levels, and data-driven. Never give financial advice — only data-backed analysis.",
        )

        if not analysis:
            return (
                f"📈 <b>{info['name']} ({symbol})</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>Price:</b> {_fmt_price(price)}{change_str}\n"
                f"<b>P/E:</b> {pe or 'N/A'} | <b>M Cap:</b> {_fmt_billions(mcap)}\n\n"
                f"AI analysis unavailable. Check your API keys (OPENAI_API_KEY / GROQ_API_KEY)."
            )

        sent_icon = sent_icon_map.get(sentiment_data["sentiment"], "🟡")

        lines = [
            f"📈 <b>{info['name']} ({symbol})</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"<b>Price:</b> {_fmt_price(price)}{change_str}",
            f"<b>Sector:</b> {info['sector']} | {info['industry']}",
            f"<b>M Cap:</b> {_fmt_billions(mcap)} | <b>P/E:</b> {pe or 'N/A'} | "
            f"<b>Beta:</b> {beta or 'N/A'}",
        ]

        if dy_str != "N/A" or eps:
            extra_fund = []
            if dy_str != "N/A":
                extra_fund.append(f"<b>Div Yield:</b> {dy_str}")
            if eps:
                extra_fund.append(f"<b>EPS:</b> ${eps:.2f}")
            if extra_fund:
                lines.append(" | ".join(extra_fund))

        if low52 and high52:
            lines.append(f"<b>52W Range:</b> {_fmt_price(low52)} - {_fmt_price(high52)}")

        lines.append("")
        lines.append(
            f"<b>News Sentiment:</b> {sent_icon} {sentiment_data['sentiment']} "
            f"({sentiment_data['score']:.2f})"
        )
        lines.append(f"<i>{sentiment_data['rationale']}</i>")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(analysis)
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(
            "<i>⚠️ Not financial advice. Always do your own research before trading.</i>"
        )

        return "\n".join(lines)

    except Exception as exc:
        print(f"[STOCK ANALYSIS] Critical error for {symbol}: {exc}")
        return None


def quick_fundamentals(symbol: str) -> str | None:
    """Quick snapshot of fundamental metrics for a stock."""
    try:
        symbol = symbol.upper().strip()
        info = fetch_stock_info(symbol)

        if not info.get("price"):
            return f"<b>Could not fetch data for {symbol}.</b>"

        price = info["price"]
        change_str = ""
        if info.get("change_pct") is not None:
            sign = "+" if info["change_pct"] >= 0 else ""
            change_str = f" ({sign}{info['change_pct']:.2f}%)"

        dy_str = f"{info['dividend_yield']:.2f}%" if info.get("dividend_yield") else "No dividend"
        pe = info.get("pe_ratio")
        fpe = info.get("forward_pe")
        pb = info.get("pb_ratio")
        eps = info.get("eps")
        mcap = info.get("market_cap")
        beta = info.get("beta")
        roe_val = info.get("roe")
        roe_str = f"{roe_val * 100:.1f}%" if roe_val is not None else "N/A"
        high52 = info.get("fifty_two_high")
        low52 = info.get("fifty_two_low")

        eps_str = f"${eps:.2f}" if isinstance(eps, (int, float)) else "N/A"
        return (
            f"📊 <b>{info['name']} ({symbol}) — Fundamentals</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Price:</b> {_fmt_price(price)}{change_str}\n"
            f"<b>Sector:</b> {info['sector']} | {info['industry']}\n"
            f"<b>Market Cap:</b> {_fmt_billions(mcap)}\n"
            f"<b>P/E (TTM):</b> {pe or 'N/A'} | <b>Forward P/E:</b> {fpe or 'N/A'}\n"
            f"<b>P/B Ratio:</b> {pb or 'N/A'} | <b>EPS:</b> {eps_str}\n"
            f"<b>Dividend Yield:</b> {dy_str}\n"
            f"<b>Beta:</b> {beta or 'N/A'} | <b>ROE:</b> {roe_str}\n"
            f"<b>52W Range:</b> {_fmt_price(low52)} - {_fmt_price(high52)}\n"
            f"<b>Exchange:</b> {info.get('exchange', 'N/A')}"
        )

    except Exception as exc:
        print(f"[QUICK FUNDAMENTALS] Error for {symbol}: {exc}")
        return None


def is_stock_symbol(text: str) -> str | None:
    """Check if text contains a known stock symbol. Returns the symbol or None."""
    text_upper = text.upper().strip()
    # Direct match
    if text_upper in STOCK_SYMBOLS:
        return text_upper
    # Try to find stock symbols in text
    for sym in STOCK_SYMBOLS:
        if sym in text_upper.split():
            return sym
    return None


def format_company_name(symbol: str) -> str:
    """Get company name for a symbol, or return symbol if not found."""
    ticker = _yf_ticker(symbol)
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        return info.get("longName") or info.get("shortName") or symbol
    except Exception:
        return symbol
