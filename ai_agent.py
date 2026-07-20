import json
import os
from datetime import datetime, timezone, timedelta
from html import escape

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

TRADER_LEVEL_PROMPT = (
    "You are a multi-level trading educator. A trade signal is provided below. "
    "You must explain it for THREE trader experience levels.\n\n"
    "Structure your response EXACTLY like this:\n"
    "BEGINNER|<text>\n"
    "INTERMEDIATE|<text>\n"
    "EXPERIENCED|<text>\n\n"
    "BEGINNER: Explain in simplest terms. Define any jargon (pip, stop loss, take profit, leverage, etc.). "
    "Use analogies. Max 3 sentences.\n\n"
    "INTERMEDIATE: Add technical reasoning. Mention support/resistance, trend context, "
    "why the entry/TP/SL levels make sense. Max 3 sentences.\n\n"
    "EXPERIENCED: Advanced context only. Note order flow, liquidity zones, institutional levels, "
    "correlation insights, or market structure implications. Max 3 sentences.\n\n"
    "Signal to explain:\n"
)


def _openai_chat(prompt: str, system_prompt: str | None = None) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        import requests
        messages = []
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
                "max_tokens": 800,
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
        import requests
        messages = []
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
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _best_ai(prompt: str, system_prompt: str | None = None) -> str | None:
    result = _openai_chat(prompt, system_prompt)
    if result:
        return result
    return _groq_chat(prompt, system_prompt)


def enhance_message_for_trader_levels(
    signal_text: str,
    pair: str,
    direction: str,
    entry: str,
    tp1: str,
    tp2: str,
    sl: str,
) -> dict[str, str]:
    """Generate beginner/intermediate/experienced explanations for a trade signal."""
    context = (
        f"Pair: {pair}\n"
        f"Direction: {direction}\n"
        f"Entry: {entry}\n"
        f"TP1: {tp1}\n"
        f"TP2: {tp2}\n"
        f"SL: {sl}\n"
        f"Full Signal:\n{signal_text[:500]}"
    )
    prompt = TRADER_LEVEL_PROMPT + context
    result = _best_ai(prompt, "You are a professional trading educator. Be accurate and helpful.")
    levels = {"beginner": "", "intermediate": "", "experienced": ""}
    if result:
        for line in result.split("\n"):
            line = line.strip()
            if line.upper().startswith("BEGINNER|"):
                levels["beginner"] = line.split("|", 1)[-1].strip()
            elif line.upper().startswith("INTERMEDIATE|"):
                levels["intermediate"] = line.split("|", 1)[-1].strip()
            elif line.upper().startswith("EXPERIENCED|"):
                levels["experienced"] = line.split("|", 1)[-1].strip()
    return levels


def format_trader_level_block(levels: dict[str, str]) -> str:
    """Format the trader level explanations into a message block."""
    parts = []
    if levels.get("beginner"):
        parts.append(f"📘 *For Beginners:* {levels['beginner']}")
    if levels.get("intermediate"):
        parts.append(f"📙 *For Intermediate:* {levels['intermediate']}")
    if levels.get("experienced"):
        parts.append(f"📈 *For Experienced:* {levels['experienced']}")
    if parts:
        return "\n\n" + "\n\n".join(parts)
    return ""


def enhance_forex_message_with_ai(original_message: str, pair: str, direction: str,
                                   entry: str, tp1: str, tp2: str, sl: str) -> str:
    """Add trader-level learning annotations to a forex/crypto signal message."""
    levels = enhance_message_for_trader_levels(
        original_message, pair, direction, entry, tp1, tp2, sl
    )
    level_block = format_trader_level_block(levels)
    if level_block:
        separator = "\n\n━━━━━━━━━━━━━━━━━━"
        educational_tag = "\n\n🧠 *AI Learning Assistant* — _Tailored for your experience level_"
        return original_message + separator + educational_tag + level_block
    return original_message


def generate_btc_trade_suggestion(current_price: float | None = None) -> str | None:
    """Generate a standalone BTC/USD trade suggestion using AI."""
    price_context = ""
    if current_price:
        price_context = f"Current BTC/USD price: ${current_price:,.2f}"

    prompt = (
        "You are a crypto trading analyst. Generate a BTC/USD trade suggestion.\n\n"
        f"{price_context}\n\n"
        "Based on recent Bitcoin market conditions, provide:\n"
        "1. Direction (LONG or SHORT)\n"
        "2. Rationale (1 sentence)\n"
        "3. Key support and resistance levels\n"
        "4. Risk management advice\n\n"
        "Format:\n"
        "DIRECTION: <LONG/SHORT>\n"
        "RATIONALE: <1 sentence>\n"
        "SUPPORT: <level>\n"
        "RESISTANCE: <level>\n"
        "ADVICE: <1 sentence>\n\n"
        "Be factual and data-driven. Never give financial advice."
    )
    result = _best_ai(prompt, "You are a professional crypto trading analyst.")
    if not result:
        return None
    return result.strip()


def format_btc_signal_block(ai_suggestion: str, price: float | None = None) -> str:
    """Format a BTC analysis block for inclusion in broadcasts."""
    price_line = ""
    if price:
        price_line = f"💰 *Live Price:* ${price:,.2f}\n"

    lines = [
        "₿ *BTC/USD CRYPTO SIGNAL*",
        "━━━━━━━━━━━━━━━━━━",
        f"{price_line}",
        f"🤖 *AI Analysis:*\n{ai_suggestion}",
        "",
        "📘 *Beginner Note:* Bitcoin trades 24/7 on crypto exchanges. "
        "A LONG position means you buy expecting the price to rise. "
        "Always use stop-losses to protect your capital.",
        "",
        "━━━━━━━━━━━━━━━━━━",
        "🔖 #BTC  #crypto  #Bitcoin  #signal",
        "⚠️ _Not financial advice. Trade at your own risk._",
    ]
    return "\n".join(lines)


def generate_market_education_tip(topic: str = "general") -> str:
    """Generate an educational trading tip using AI."""
    topics = {
        "position_sizing": "position sizing and risk management",
        "support_resistance": "support and resistance levels",
        "trend_following": "trend following strategies",
        "btc_basics": "Bitcoin trading basics and crypto market dynamics",
        "forex_basics": "forex trading basics including pips, lots, and leverage",
        "risk_management": "risk management and stop-loss placement",
        "general": "a general trading tip for beginners",
    }
    selected = topics.get(topic, topics["general"])

    prompt = (
        f"Generate a short educational trading tip about {selected}. "
        "Write it at three levels:\n"
        "BEGINNER: Simple explanation (1 sentence)\n"
        "INTERMEDIATE: Slightly deeper (1 sentence)\n"
        "EXPERIENCED: Advanced insight (1 sentence)\n\n"
        "Format each line as: BEGINNER|<text>"
    )
    result = _best_ai(prompt, "You are a trading educator. Be accurate and clear.")
    if not result:
        return ""

    lines = result.strip().split("\n")
    beginner = ""
    intermediate = ""
    experienced = ""
    for line in lines:
        line = line.strip()
        if line.upper().startswith("BEGINNER|"):
            beginner = line.split("|", 1)[-1].strip()
        elif line.upper().startswith("INTERMEDIATE|"):
            intermediate = line.split("|", 1)[-1].strip()
        elif line.upper().startswith("EXPERIENCED|"):
            experienced = line.split("|", 1)[-1].strip()

    parts = ["🧠 *Daily Trading Tip*"]
    if beginner:
        parts.append(f"📘 *Beginner:* {beginner}")
    if intermediate:
        parts.append(f"📙 *Intermediate:* {intermediate}")
    if experienced:
        parts.append(f"📈 *Experienced:* {experienced}")
    return "\n\n".join(parts)


def analyze_recent_signals_for_improvement(signal_log: list[dict]) -> str | None:
    """Analyze recent trade signals and suggest improvements to the system."""
    if not signal_log:
        return None

    recent = signal_log[-20:]
    summary_lines = []
    for s in recent:
        summary_lines.append(
            f"{s.get('pair', '?')} {s.get('direction', '?')} @ {s.get('entry', '?')} "
            f"[TP1: {s.get('tp1', '?')} TP2: {s.get('tp2', '?')} SL: {s.get('sl', '?')}]"
        )
    summary = "\n".join(summary_lines)

    from datetime import datetime, timezone, timedelta
    today_name = datetime.now(timezone.utc).strftime("%A")
    prompt = (
        "You are an AI trading system optimizer. Review these recent trade signals:\n\n"
        f"{summary}\n\n"
        f"Today is {today_name}. Analyze:\n"
        "1. Are the TP/SL levels appropriately placed?\n"
        "2. Is there good variety across assets (forex, crypto, stocks)?\n"
        "3. Are BTC signals frequent enough?\n"
        "4. How can the signal quality be improved?\n"
        "5. Suggest ONE creative improvement to the Telegram message format/style/design "
        "(emoji usage, layout, structure, colors via unicode, etc.) to make it more "
        "engaging and professional. Be specific.\n\n"
        "Provide 3-4 specific, actionable suggestions. Be concise."
    )
    return _best_ai(prompt, "You are an expert trading system architect.")


def generate_btc_market_update(prices: dict | None = None) -> str | None:
    """Generate a dedicated BTC market update with multi-level education."""
    btc_price = None
    if prices:
        btc_price = prices.get("BTC/USD")

    price_ctx = ""
    if btc_price:
        price_ctx = f"Bitcoin is currently at ${btc_price:,.2f}."

    prompt = (
        "You are a crypto market analyst. Generate a Bitcoin market update.\n\n"
        f"{price_ctx}\n\n"
        "Structure your response EXACTLY like this:\n"
        "SIGNAL|<direction (BULLISH/BEARISH/NEUTRAL)>\n"
        "ANALYSIS|<1-2 sentences on market conditions>\n"
        "KEY_LEVEL|<key price level to watch>\n"
        "BTC_DOMINANCE|<mention if relevant>\n"
        "BEGINNER|<simple explanation for new traders>\n"
        "INTERMEDIATE|<technical context>\n"
        "EXPERIENCED|<advanced insight>\n\n"
        "Be factual and data-driven."
    )
    return _best_ai(prompt, "You are a professional crypto market analyst.")


def format_btc_market_update(ai_output: str, btc_price: float | None = None) -> str | None:
    """Format BTC market update into a Telegram message."""
    if not ai_output:
        return None

    lines = ai_output.strip().split("\n")
    signal = ""
    analysis = ""
    key_level = ""
    beginner = ""
    intermediate = ""
    experienced = ""

    for line in lines:
        line = line.strip()
        if line.upper().startswith("SIGNAL|"):
            signal = line.split("|", 1)[-1].strip()
        elif line.upper().startswith("ANALYSIS|"):
            analysis = line.split("|", 1)[-1].strip()
        elif line.upper().startswith("KEY_LEVEL|"):
            key_level = line.split("|", 1)[-1].strip()
        elif line.upper().startswith("BEGINNER|"):
            beginner = line.split("|", 1)[-1].strip()
        elif line.upper().startswith("INTERMEDIATE|"):
            intermediate = line.split("|", 1)[-1].strip()
        elif line.upper().startswith("EXPERIENCED|"):
            experienced = line.split("|", 1)[-1].strip()

    if not signal and not analysis:
        return None

    signal_icon = {
        "BULLISH": "🟢",
        "BEARISH": "🔴",
        "NEUTRAL": "🟡",
    }.get(signal.upper(), "🟡")

    price_line = ""
    if btc_price:
        price_line = f"💰 *Price:* ${btc_price:,.2f}"

    parts = [
        "₿ *BTC/USD — AI Market Update*",
        "━━━━━━━━━━━━━━━━━━",
    ]
    if signal:
        parts.append(f"{signal_icon} *Signal:* {signal}")
    if price_line:
        parts.append(price_line)
    if analysis:
        parts.append(f"\n📊 *Analysis:* {analysis}")
    if key_level:
        parts.append(f"🎯 *Key Level:* {key_level}")

    parts.append("\n━━━━━━━━━━━━━━━━━━")
    parts.append("🧠 *AI Learning Assistant*")

    if beginner:
        parts.append(f"\n📘 *For Beginners:* {beginner}")
    if intermediate:
        parts.append(f"📙 *For Intermediate:* {intermediate}")
    if experienced:
        parts.append(f"📈 *For Experienced:* {experienced}")

    parts.extend([
        "",
        "🔖 #BTC  #crypto  #Bitcoin  #AIanalysis",
        "⚠️ _Not financial advice. Trade at your own risk._",
    ])
    return "\n".join(parts)


# ── Dedicated Signal Generators for XAUUSD, Bitcoin, Nasdaq, US Pairs ──────

def generate_xauusd_signal(current_price: float | None = None, news_context: str = "") -> str | None:
    """Generate XAU/USD (Gold) trade signal with entry, TP, and SL using AI + live data."""
    price_ctx = ""
    if current_price:
        price_ctx = f"Current XAU/USD price: ${current_price:,.2f}"
    news_ctx = ""
    if news_context:
        news_ctx = f"\nRecent news: {news_context[:300]}"

    prompt = (
        "You are a professional gold (XAU/USD) trading analyst. Generate a precise trade signal.\n\n"
        f"{price_ctx}{news_ctx}\n\n"
        "Based on current gold market conditions and news, provide:\n"
        "1. Direction (LONG or SHORT)\n"
        "2. Entry price (within 1-2$ of current price)\n"
        "3. TP1 (first take profit, within 10-15$ range)\n"
        "4. TP2 (second take profit, within 20-30$ range)\n"
        "5. SL (stop loss, within 5-8$ range)\n"
        "6. Key reason (1 sentence)\n\n"
        "Format EXACTLY:\n"
        "DIRECTION: LONG/SHORT\n"
        "ENTRY: $XXXX.X\n"
        "TP1: $XXXX.X\n"
        "TP2: $XXXX.X\n"
        "SL: $XXXX.X\n"
        "REASON: <1 sentence>\n\n"
        "Be precise with price levels. Consider current gold volatility."
    )
    result = _best_ai(prompt, "You are a professional XAU/USD trading analyst. Be precise and data-driven.")
    if not result:
        return None
    return result.strip()


def generate_nasdaq_signal(current_price: float | None = None, news_context: str = "") -> str | None:
    """Generate NASDAQ (US100) trade signal with entry, TP, and SL using AI + live data."""
    price_ctx = ""
    if current_price:
        price_ctx = f"Current NASDAQ (US100) price: ${current_price:,.2f}"
    news_ctx = ""
    if news_context:
        news_ctx = f"\nRecent news: {news_context[:300]}"

    prompt = (
        "You are a professional US stock index trading analyst. Generate a NASDAQ (US100) trade signal.\n\n"
        f"{price_ctx}{news_ctx}\n\n"
        "Based on current market conditions and news, provide:\n"
        "1. Direction (LONG or SHORT)\n"
        "2. Entry price (within 10-20 points of current price)\n"
        "3. TP1 (within 50-100 points range)\n"
        "4. TP2 (within 100-200 points range)\n"
        "5. SL (within 25-50 points range)\n"
        "6. Key reason (1 sentence)\n\n"
        "Format EXACTLY:\n"
        "DIRECTION: LONG/SHORT\n"
        "ENTRY: $XXXXX.X\n"
        "TP1: $XXXXX.X\n"
        "TP2: $XXXXX.X\n"
        "SL: $XXXXX.X\n"
        "REASON: <1 sentence>\n\n"
        "Be precise. NASDAQ moves fast so give reasonable ranges."
    )
    result = _best_ai(prompt, "You are a professional NASDAQ trading analyst. Be precise and data-driven.")
    if not result:
        return None
    return result.strip()


def generate_forex_pair_signal(pair: str, current_price: float | None = None, news_context: str = "") -> str | None:
    """Generate a major forex pair (EUR/USD, GBP/USD, USD/JPY) trade signal with entry, TP, and SL."""
    price_ctx = ""
    if current_price:
        price_ctx = f"Current {pair} price: {current_price:.5f}"
    news_ctx = ""
    if news_context:
        news_ctx = f"\nRecent news: {news_context[:300]}"

    prompt = (
        f"You are a professional forex trading analyst. Generate a {pair} trade signal.\n\n"
        f"{price_ctx}{news_ctx}\n\n"
        "Based on current forex market conditions and news, provide:\n"
        "1. Direction (LONG or SHORT)\n"
        "2. Entry price (within 5-10 pips of current price)\n"
        "3. TP1 (within 15-25 pips range)\n"
        "4. TP2 (within 30-50 pips range)\n"
        "5. SL (within 10-15 pips range)\n"
        "6. Key reason (1 sentence)\n\n"
        "Format EXACTLY:\n"
        "DIRECTION: LONG/SHORT\n"
        "ENTRY: X.XXXXX\n"
        "TP1: X.XXXXX\n"
        "TP2: X.XXXXX\n"
        "SL: X.XXXXX\n"
        "REASON: <1 sentence>\n\n"
        "Be precise with pip levels."
    )
    result = _best_ai(prompt, f"You are a professional {pair} forex trading analyst. Be precise and data-driven.")
    if not result:
        return None
    return result.strip()


def generate_us30_signal(current_price: float | None = None, news_context: str = "") -> str | None:
    """Generate US30 (Dow Jones) trade signal with entry, TP, and SL."""
    price_ctx = ""
    if current_price:
        price_ctx = f"Current US30 (Dow Jones) price: ${current_price:,.2f}"
    news_ctx = ""
    if news_context:
        news_ctx = f"\nRecent news: {news_context[:300]}"

    prompt = (
        "You are a professional Dow Jones (US30) trading analyst. Generate a trade signal.\n\n"
        f"{price_ctx}{news_ctx}\n\n"
        "Based on current market conditions and news, provide:\n"
        "1. Direction (LONG or SHORT)\n"
        "2. Entry price (within 20-30 points of current)\n"
        "3. TP1 (within 100-150 points range)\n"
        "4. TP2 (within 200-300 points range)\n"
        "5. SL (within 50-80 points range)\n"
        "6. Key reason (1 sentence)\n\n"
        "Format EXACTLY:\n"
        "DIRECTION: LONG/SHORT\n"
        "ENTRY: $XXXXX.X\n"
        "TP1: $XXXXX.X\n"
        "TP2: $XXXXX.X\n"
        "SL: $XXXXX.X\n"
        "REASON: <1 sentence>"
    )
    result = _best_ai(prompt, "You are a professional Dow Jones trading analyst. Be precise and data-driven.")
    if not result:
        return None
    return result.strip()


def format_ai_signal_block(
    signal_type: str,
    icon: str,
    pair_label: str,
    ai_output: str,
    current_price: float | None = None,
) -> str:
    """Format any AI-generated signal into a consistent Telegram message block."""
    if not ai_output:
        return ""

    lines = ai_output.strip().split("\n")
    direction = ""
    entry = ""
    tp1 = ""
    tp2 = ""
    sl = ""
    reason = ""

    for line in lines:
        line = line.strip()
        if line.upper().startswith("DIRECTION:"):
            direction = line.split(":", 1)[-1].strip()
        elif line.upper().startswith("ENTRY:"):
            entry = line.split(":", 1)[-1].strip()
        elif line.upper().startswith("TP1:"):
            tp1 = line.split(":", 1)[-1].strip()
        elif line.upper().startswith("TP2:"):
            tp2 = line.split(":", 1)[-1].strip()
        elif line.upper().startswith("SL:"):
            sl = line.split(":", 1)[-1].strip()
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[-1].strip()

    dir_icon = "🟢 LONG" if direction.upper() == "LONG" else "🔴 SHORT"
    price_line = ""
    if current_price:
        price_line = f"💰 *Live Price:* ${current_price:,.2f}\n" if current_price >= 1000 else f"💰 *Live Price:* ${current_price:.2f}\n"

    lines_out = [
        f"{icon} *{signal_type}* | AI-Powered Signal",
        "━━━━━━━━━━━━━━━━━━",
        f"*{pair_label}*  ·  {dir_icon}  ·  H1",
        f"_{ai_agent.__name__} Real-Time Analysis_",
        "",
        "━━━━━━━━━━━━━━━━━━",
    ]
    if price_line.strip():
        lines_out.append(price_line.strip())
    if entry:
        lines_out.append(f"📌 *Entry:*      {entry}")
    if sl:
        lines_out.append(f"🛑 *Stop Loss:*  {sl}")
    if tp1:
        lines_out.append(f"🎯 *TP 1:*       {tp1}")
    if tp2:
        lines_out.append(f"🎯 *TP 2:*       {tp2}")
    if reason:
        lines_out.extend([
            "━━━━━━━━━━━━━━━━━━",
            f"📊 *Analysis:* {reason}",
        ])

    lines_out.extend([
        "",
        "━━━━━━━━━━━━━━━━━━",
        "🧠 *AI Learning Assistant*",
        "",
        f"📘 *Beginner:* {dir_icon} means we expect the price to {'rise' if direction.upper() == 'LONG' else 'fall'}. "
        f"Entry at {entry} opens the trade. SL at {sl} caps losses. TP1/TP2 lock in profits.",
        "",
        f"📙 *Intermediate:* Entry {entry} with {'bullish' if direction.upper() == 'LONG' else 'bearish'} bias. "
        f"Risk defined by SL at {sl}. First target TP1 at {tp1}, second target TP2 at {tp2}.",
        "",
        f"📈 *Experienced:* Key level at {entry}. "
        f"{'Resistance' if direction.upper() == 'SHORT' else 'Support'} near targets. "
        "Monitor volume and price action for confirmation.",
        "",
        f"🔖 #{signal_type.replace(' ', '').replace('/', '')}  #forex  #signal  #{'long' if direction.upper() == 'LONG' else 'short'}",
        "⚠️ _Not financial advice. Trade at your own risk._",
    ])

    return "\n".join(lines_out)


if __name__ == "__main__":
    print("AI Agent module loaded. Used by main.py for message enhancement.")
