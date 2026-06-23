import os
import re
from typing import Any

# --- SECURE CREDENTIALS ---
# The bot reads the token securely from the hosting environment.
# Set this locally via terminal: export BOT_TOKEN="your_token_here"
BOT_TOKEN = os.getenv("BOT_TOKEN", "PLACEHOLDER_TOKEN_REVOKED")

# --- REGEX PARSING ENGINE ---
# Matches common signal patterns: "BUY EURUSD @ 1.0850 SL: 1.0800 TP: 1.0950"
SIGNAL_PATTERN = re.compile(
    r'(?P<action>BUY|SELL)\s+'
    r'(?P<asset>[A-Z0-9_/]+)\s+'
    r'(?:@|AT|ENTRY:?)\s*(?P<entry>[\d\.]+)\s*'
    r'.*?(?:SL|STOP\s*LOSS)[:=\s]+(?P<sl>[\d\.]+)'
    r'.*?(?:TP|TAKE\s*PROFIT)[:=\s]+(?P<tp>[\d\.]+)',
    re.IGNORECASE | re.DOTALL,
)


def extract_signal(raw_text: str) -> dict[str, str] | None:
    match = SIGNAL_PATTERN.search(raw_text)
    if not match:
        return None
    return {
        key: value.upper() if key in {"action", "asset"} else value
        for key, value in match.groupdict().items()
    }


def get_message_text(update: Any) -> str:
    channel_post = getattr(update, "channel_post", None)
    if channel_post and getattr(channel_post, "text", None):
        return channel_post.text

    message = getattr(update, "message", None)
    if message and getattr(message, "text", None):
        return message.text

    return ""


async def parse_channel_signal(update: Any, context: Any):
    """
    Triggers automatically when the bot receives a message in a
    channel or group where it has appropriate reading permissions.
    """
    del context
    raw_text = get_message_text(update)
    if not raw_text:
        return

    print("\n--- [New Message Intercepted] ---")
    print(f"Raw Text:\n{raw_text.strip()}\n")

    data = extract_signal(raw_text)
    if data:
        print("[OK] Trade signal parsed successfully.")
        print(f"Asset      : {data['asset']}")
        print(f"Action     : {data['action']}")
        print(f"Entry Price: {data['entry']}")
        print(f"Stop Loss  : {data['sl']}")
        print(f"Take Profit: {data['tp']}\n")

        # Connect this data dictionary to a database or forwarding workflow here.
    else:
        print("[INFO] Standard update or non-signal message received. Skipping parser.")


def build_application(bot_token: str):
    try:
        from telegram.ext import Application, MessageHandler, filters
    except ImportError as exc:
        raise RuntimeError(
            "python-telegram-bot is not installed. Run `pip install -r requirements.txt` first."
        ) from exc

    app = Application.builder().token(bot_token).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), parse_channel_signal))
    return app


def main() -> int:
    print("Launching LiveForexSignalsAI Bot Engine...")

    if BOT_TOKEN == "PLACEHOLDER_TOKEN_REVOKED":
        print("[ERROR] Please set your secure BOT_TOKEN environment variable.")
        return 1

    app = build_application(BOT_TOKEN)
    print("Bot is live and listening on the cloud server...")
    app.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
