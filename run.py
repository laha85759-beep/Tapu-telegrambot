"""Run a single fetch-and-send cycle (used by GitHub Actions / 24/7 worker)."""

import asyncio
import json
import os
import sys

from telegram import Bot

import ai_agent
import main as _main
from main import (
    _price_str,
    broadcast,
    fetch_current_prices,
    load_seen_keys,
    load_signal_log,
    run_worker_cycle,
    save_seen_keys,
    validate_config,
)

# Resolve bot token directly from env (bypass module-level import)
BOT_TOKEN = (os.environ.get("BOT_TOKEN") or os.environ.get("BOT_TOKEN3") or "").strip()

_AI_COUNTER_FILE = os.path.join(os.path.dirname(__file__), ".ai_cycle_counter")
_DEDICATED_SIGNALS_FILE = os.path.join(os.path.dirname(__file__), ".dedicated_signals_sent")


def _read_counter() -> int:
    try:
        with open(_AI_COUNTER_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def _write_counter(n: int) -> None:
    with open(_AI_COUNTER_FILE, "w") as f:
        f.write(str(n))


def _read_dedicated_signal_keys() -> set[str]:
    try:
        with open(_DEDICATED_SIGNALS_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_dedicated_signal_keys(keys: set[str]) -> None:
    with open(_DEDICATED_SIGNALS_FILE, "w") as f:
        json.dump(sorted(keys), f)


async def send_major_pair_signal(
    bot: Bot,
    signal_type: str,
    icon: str,
    pair_label: str,
    pair_key: str,
    generate_fn,
    seen_signals: set[str],
    prices: dict,
    news_ctx: str = "",
) -> int:
    """Generate and send a dedicated signal for a major trading pair."""
    today = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y-%m-%d")
    signal_key = f"{pair_key}:{today}"

    if signal_key in seen_signals:
        return 0

    current_price = prices.get(pair_key)
    ai_output = generate_fn(current_price=current_price, news_context=news_ctx)
    if not ai_output:
        return 0

    block = ai_agent.format_ai_signal_block(
        signal_type=signal_type,
        icon=icon,
        pair_label=pair_label,
        ai_output=ai_output,
        current_price=current_price,
    )
    if not block:
        return 0

    try:
        await broadcast(bot, block)
        seen_signals.add(signal_key)
        _save_dedicated_signal_keys(seen_signals)
        print(f"[DEDICATED SIGNAL] {signal_type} sent.")
        return 1
    except Exception as e:
        print(f"[DEDICATED SIGNAL] {signal_type} failed: {e}")
        return 0


async def send_dedicated_ai_signals(bot: Bot, seen_signals: set[str]) -> int:
    """Send AI-powered signals for XAUUSD, Bitcoin, Nasdaq, US30, and major forex pairs."""
    prices = fetch_current_prices()
    total_sent = 0

    # XAU/USD (Gold) signal
    total_sent += await send_major_pair_signal(
        bot, "XAU/USD GOLD", "🥇", "XAU/USD · Gold vs USD",
        "XAU/USD", ai_agent.generate_xauusd_signal, seen_signals, prices,
    )

    # BTC/USD (Bitcoin) signal
    total_sent += await send_major_pair_signal(
        bot, "BTC/USD BITCOIN", "₿", "BTC/USD · Bitcoin vs USD",
        "BTC/USD", ai_agent.generate_btc_trade_suggestion, seen_signals, prices,
    )

    # US100 (NASDAQ) signal
    total_sent += await send_major_pair_signal(
        bot, "US100 NASDAQ", "📈", "US100 · NASDAQ Index",
        "US100", ai_agent.generate_nasdaq_signal, seen_signals, prices,
    )

    # US30 (Dow Jones) signal
    total_sent += await send_major_pair_signal(
        bot, "US30 DOW JONES", "📊", "US30 · Dow Jones Index",
        "US30", ai_agent.generate_us30_signal, seen_signals, prices,
    )

    # EUR/USD signal
    total_sent += await send_major_pair_signal(
        bot, "EUR/USD", "💶", "EUR/USD · Euro vs US Dollar",
        "EUR/USD", ai_agent.generate_forex_pair_signal, seen_signals, prices,
    )

    # GBP/USD signal
    total_sent += await send_major_pair_signal(
        bot, "GBP/USD", "💷", "GBP/USD · British Pound vs US Dollar",
        "GBP/USD", ai_agent.generate_forex_pair_signal, seen_signals, prices,
    )

    return total_sent


async def run_ai_cycle(bot: Bot) -> None:
    cycle = _read_counter() + 1
    _write_counter(cycle)

    now_utc = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
    time_str = now_utc.strftime("%H:%M UTC")

    # ── Dedicated AI Signals for XAUUSD, BTC, NASDAQ, US Pairs ──
    seen_signals = _read_dedicated_signal_keys()
    ded_sent = await send_dedicated_ai_signals(bot, seen_signals)
    if ded_sent:
        print(f"[AI] Sent {ded_sent} dedicated signal(s) at {time_str}")

    # BTC market update every cycle
    try:
        btc_update = ai_agent.generate_btc_market_update()
        if btc_update:
            block = ai_agent.format_btc_market_update(btc_update)
            await broadcast(bot, block)
            print(f"[AI] BTC market update sent at {time_str}")
    except Exception as e:
        print(f"[AI] BTC update failed: {e}")

    # BTC trade suggestion every 2nd cycle
    if cycle % 2 == 0:
        try:
            btc_sug = ai_agent.generate_btc_trade_suggestion()
            if btc_sug:
                block = ai_agent.format_btc_signal_block(btc_sug)
                await broadcast(bot, block)
                print(f"[AI] BTC trade suggestion sent at {time_str}")
        except Exception as e:
            print(f"[AI] BTC suggestion failed: {e}")

    # Educational tip every 6 cycles
    if cycle % 6 == 0:
        try:
            signals_data = load_signal_log()[-20:]
            tip = ai_agent.generate_market_education_tip(signals_data)
            if tip:
                await broadcast(bot, f"🧠 *AI Education Tip*\n\n{tip}")
                print(f"[AI] Education tip sent at {time_str}")
        except Exception as e:
            print(f"[AI] Education tip failed: {e}")

    # Market snapshot every 4 cycles
    if cycle % 4 == 0:
        try:
            prices = fetch_current_prices()
            snapshot_lines = [
                f"📸 *AI Market Snapshot* — {time_str}",
                f"━━━━━━━━━━━━━━━━━━",
            ]
            for pair in ["XAU/USD", "EUR/USD", "GBP/USD", "BTC/USD", "ETH/USD",
                         "US100", "US30", "DXY", "NIFTY", "WTI", "US10Y"]:
                p = prices.get(pair)
                if p:
                    snapshot_lines.append(f"  {pair}: {_price_str(p, pair)}")
            snapshot_lines.append("")
            enh = ai_agent.enhance_message_for_trader_levels(
                "\n".join(snapshot_lines), "intermediate",
            )
            snapshot_lines.append(f"💡 {enh}")
            await broadcast(bot, "\n".join(snapshot_lines))
            print(f"[AI] Market snapshot sent at {time_str}")
        except Exception as e:
            print(f"[AI] Market snapshot failed: {e}")

    print(f"[AI] Cycle {cycle} completed at {time_str}")


async def run_once() -> int:
    missing = validate_config()
    if missing:
        print(f"[ERROR] Missing: {', '.join(missing)}")
        return 1

    bot = Bot(BOT_TOKEN)
    seen_keys = load_seen_keys()
    _main._subscribers = _main.load_subscribers()
    _main._backfill_subscribers_from_updates()
    print(f"Loaded {len(seen_keys)} previously sent article keys.")
    print(f"Loaded {len(_main._subscribers)} subscriber(s).")

    sent = await run_worker_cycle(bot, seen_keys)
    save_seen_keys(seen_keys)
    print(f"News cycle complete. Sent {sent} message(s).")

    await run_ai_cycle(bot)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_once()))
