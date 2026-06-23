# LiveForexSignalsAI App Engine

This package contains the complete production-ready Python backend engine for your Telegram trading signal aggregator bot.

## Files Included:
1. `main.py` - The core application listening to Telegram events and extracting data fields with high-speed regex.
2. `requirements.txt` - Required environment library specifications (`python-telegram-bot`).
3. `render.yaml` - Zero-config deployment file designed to launch automatically on Render as a 24/7 background worker.

## How to use locally:
1. Extract files.
2. Install dependencies: `pip install -r requirements.txt`
3. Set your token as an environment variable or configure it securely in your deployment dashboard.
4. Run: `python main.py`
