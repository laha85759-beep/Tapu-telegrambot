import asyncio
import json
import os
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from html import escape
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import yfinance as yf

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import massive_data
import realtime_alert
import ai_agent
import crypto_screener
import stock_analysis

def resolve_bot_settings(env: dict[str, str] | None = None) -> tuple[str, str]:
    values = os.environ if env is None else env
    token = (values.get("BOT_TOKEN") or values.get("BOT_TOKEN3") or "").strip()
    chat_id = (values.get("TELEGRAM_CHAT_ID") or values.get("TELEGRAM_CHAT_ID3") or "").strip()
    return token, chat_id


BOT_TOKEN, TELEGRAM_CHAT_ID = resolve_bot_settings()
BOT_TOKEN2 = ""
BOT_TOKEN3 = ""
TELEGRAM_CHAT_ID3 = ""
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "").strip()
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY", "").strip()
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
NEWSDATA_API_URL = "https://newsdata.io/api/1/latest"
NEWSAPI_URL = "https://newsapi.org/v2/everything"
FINNHUB_BASE = "https://finnhub.io/api/v1"
NEWS_PROVIDER = os.getenv("NEWS_PROVIDER", "auto").strip().lower()
FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", "900"))
HIGH_IMPACT_CHECK_INTERVAL = int(os.getenv("HIGH_IMPACT_CHECK_INTERVAL", "60"))

SENT_KEYS_FILE = "sent_articles.json"
SIGNAL_LOG_FILE = "signal_log.json"
SUBSCRIBERS_FILE = "subscribers.json"
_seen_keys: set[str] = set()
_signal_log: list[dict] = []
_subscribers: list[int] = []

FOREX_QUERY = os.getenv(
    "FOREX_QUERY",
    'forex OR "foreign exchange" OR (dollar AND fed) OR (euro AND ecb) OR '
    '(pound AND boe) OR (yen AND boj) OR (gold AND fed) OR (rupee AND rbi) OR '
    '(bitcoin OR btc OR ethereum OR eth OR crypto OR solana OR ripple OR cardano OR dogecoin) OR '
    '(crude oil OR brent OR wti) OR (silver) OR (nasdaq OR "dow jones" OR "s&p 500") OR '
    '(apple OR microsoft OR amazon OR nvidia OR meta OR tesla OR google OR netflix) OR '
    '(reliance OR tcs OR hdfc OR infosys OR icici OR sbi OR bharti OR zomato OR adani)',
)

INDIA_MARKET_QUERY = os.getenv(
    "INDIA_MARKET_QUERY",
    '(sensex OR nifty OR "indian market" OR "india stock" OR "bse" OR "nse" OR '
    '"rbi" OR "rupee" OR "sebi" OR "indian economy") AND (india OR mumbai)',
)

INTRADAY_STOCK_QUERY = os.getenv(
    "INTRADAY_STOCK_QUERY",
    '(reliance OR tcs OR hdfc OR infosys OR icici OR "hindustan unilever" OR sbi OR '
    'bharti OR "intraday" OR "stock market today" OR "opening bell" OR "closing bell" OR '
    'zomato OR adani OR "tata motors" OR "bajaj finance" OR wipro OR itc OR "asian paints" OR '
    'ntpc OR ongc OR "power grid" OR "ultratech cement" OR "tata steel" OR jsw OR hindalco OR '
    'walmart OR jpmorgan OR visa OR boeing OR disney OR netflix OR salesforce OR paypal OR uber) '
    'AND (india OR "bse" OR "nse" OR "bombay stock exchange")',
)

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
    "silver",
    "xag",
    "crude",
    "oil",
    "brent",
    "wti",
    "fed",
    "ecb",
    "boe",
    "boj",
    "rate hike",
    "rate cut",
    "inflation",
    "cpi",
    "nonfarm payrolls",
    "aud",
    "aussie",
    "nzd",
    "kiwi",
    "chf",
    "swiss franc",
    "cad",
    "loonie",
    "sek",
    "nok",
    "sgd",
    "hkd",
    "cny",
    "yuan",
    "mxn",
    "peso",
    "zar",
    "rand",
    "try",
    "lira",
    "inr",
    "rupee",
    "rbi",
    "sensex",
    "nifty",
    "bank nifty",
    "india market",
    "bse",
    "nse",
    "sp500",
    "ftse",
    "dax",
    "nikkei",
    "hang seng",
    "asx 200",
    "s&p 500",
    "apple",
    "microsoft",
    "amazon",
    "nvidia",
    "tesla",
    "meta",
    "google",
    "netflix",
    "adobe",
    "salesforce",
    "intel",
    "amd",
    "paypal",
    "uber",
    "nike",
    "boeing",
    "disney",
    "walmart",
    "jpmorgan",
    "visa",
    "reliance",
    "tcs",
    "hdfc",
    "infosys",
    "icici",
    "sbi",
    "bharti",
    "zomato",
    "adani",
    "bitcoin",
    "btc",
    "ethereum",
    "eth",
    "solana",
    "sol",
    "ripple",
    "xrp",
    "cardano",
    "ada",
    "dogecoin",
    "doge",
    "polkadot",
    "dot",
    "avalanche",
    "avax",
    "chainlink",
    "link",
    "polygon",
    "matic",
    "crypto",
    "cryptocurrency",
    "nasdaq",
    "dow jones",
    "s&p",
    "sp500",
    "wall street",
    "us30",
    "us100",
    "reliance",
    "tcs",
    "hdfc",
    "infosys",
    "icici",
    "sbi",
    "bharti",
    "nifty 50",
    "sensex",
    "bank nifty",
}

CURRENCY_HINTS = {
    "XAU": ("xau", "gold", "bullion"),
    "XAG": ("xag", "silver"),
    "OIL": ("crude", "oil", "brent", "wti"),
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "eth"),
    "SOL": ("solana", "sol"),
    "XRP": ("ripple", "xrp"),
    "ADA": ("cardano",),
    "DOGE": ("dogecoin", "doge"),
    "DOT": ("polkadot", "dot"),
    "AVAX": ("avalanche", "avax"),
    "LINK": ("chainlink", "link"),
    "LTC": ("litecoin", "ltc"),
    "AUD": ("aud", "australian dollar", "aussie", "reserve bank of australia", "rba"),
    "NZD": ("nzd", "new zealand dollar", "kiwi", "reserve bank of new zealand", "rbnz"),
    "CHF": ("chf", "swiss franc", "swiss national bank", "snb"),
    "CAD": ("cad", "canadian dollar", "loonie", "bank of canada", "boc"),
    "SEK": ("sek", "swedish krona", "riksbank", "swedish crown"),
    "NOK": ("nok", "norwegian krone", "norges bank"),
    "SGD": ("sgd", "singapore dollar", "monetary authority of singapore"),
    "HKD": ("hkd", "hong kong dollar", "hong kong monetary authority"),
    "CNY": ("cny", "yuan", "renminbi", "chinese yuan", "pboc", "people's bank of china"),
    "MXN": ("mxn", "mexican peso", "banxico", "bank of mexico"),
    "ZAR": ("zar", "south african rand", "sarb", "reserve bank of south africa"),
    "TRY": ("try", "turkish lira", "turkish lira", "central bank of turkey"),
    "JPY": ("jpy", "yen", "boj", "bank of japan"),
    "GBP": ("gbp", "pound", "boe", "bank of england"),
    "EUR": ("eur", "euro", "ecb"),
    "USD": ("usd", "dollar", "fed", "treasury"),
    "NIFTY": ("nifty", "nifty 50", "nse"),
    "SENSEX": ("sensex", "bse", "bombay stock exchange"),
    "BANKNIFTY": ("bank nifty", "banknifty"),
    "FINNIFTY": ("fin nifty", "finnifty"),
    "MIDCAPNIFTY": ("midcap nifty", "midcapnifty", "nifty midcap"),
    "VIXNIFTY": ("india vix", "vix", "fear index"),
    "INR": ("inr", "rupee", "rbi", "india"),
    "US30": ("dow jones", "us30", "djia"),
    "US100": ("nasdaq", "us100", "ixic"),
    "SP500": ("s&p 500", "sp500", "spx"),
    "UK100": ("ftse 100", "ftse", "uk100"),
    "GER40": ("dax", "ger40", "dax 40"),
    "JPN225": ("nikkei", "jpn225", "nikkei 225", "n225"),
    "HK50": ("hang seng", "hk50", "hsi"),
    "AUS200": ("asx 200", "aus200", "s&p/asx 200"),
    "ADANIENT": ("adani enterprises", "adanient", "adani group"),
    "ADANIPORTS": ("adani ports", "adaniports"),
    "ADANIGREEN": ("adani green", "adanigreen"),
    "ADANITRANS": ("adani transmission", "adanitrans"),
    "ADANIPOWER": ("adani power", "adanipower"),
    "RELIANCE": ("reliance", "ril"),
    "TCS": ("tcs", "tata consultancy"),
    "HDFCBANK": ("hdfc bank", "hdfcbank"),
    "INFY": ("infosys", "infy"),
    "ICICIBANK": ("icici bank", "icicibank"),
    "SBIN": ("sbi", "state bank"),
    "BHARTI": ("bharti", "airtel"),
    "WIPRO": ("wipro",),
    "ITC": ("itc",),
    "LT": ("larsen", "l&t", "larsen & toubro"),
    "AXISBANK": ("axis bank", "axis"),
    "KOTAKBANK": ("kotak", "kotak mahindra", "kotak bank"),
    "MARUTI": ("maruti", "maruti suzuki"),
    "TATAMOTORS": ("tata motors", "tata motor"),
    "ASIANPAINT": ("asian paints", "asian paint"),
    "HCLTECH": ("hcl", "hcl technologies", "hcl tech"),
    "SUNPHARMA": ("sun pharma", "sun pharmaceutical"),
    "BAJFINANCE": ("bajaj finance",),
    "TITAN": ("titan",),
    "NTPC": ("ntpc",),
    "ONGC": ("ongc",),
    "POWERGRID": ("power grid", "powergrid"),
    "ULTRACEMCO": ("ultratech", "ultratech cement", "ultracemco"),
    "TATASTEEL": ("tata steel", "tatasteel"),
    "JSWSTEEL": ("jsw steel", "jswsteel"),
    "HINDALCO": ("hindalco", "hindalco industries"),
    "TECHM": ("tech mahindra", "techm"),
    "COALINDIA": ("coal india", "coalindia"),
    "HINDUNILVR": ("hindustan unilever", "hul", "hindunilvr"),
    "BRITANNIA": ("britannia", "britannia industries"),
    "NESTLEIND": ("nestle india", "nestleind"),
    "M&M": ("mahindra", "m&m", "mahindra & mahindra"),
    "EICHERMOT": ("eicher motors", "eichermot", "royal enfield"),
    "HEROMOTOCO": ("hero motocorp", "heromotoco", "hero honda"),
    "BAJAJ-AUTO": ("bajaj auto", "bajajauto"),
    "TATACONSUM": ("tata consumer", "tataconsumer"),
    "DABUR": ("dabur",),
    "MARICO": ("marico",),
    "HDFC": ("hdfc", "hdfc ltd"),
    "ICICIPRUDI": ("icici prudential", "iciciprudential"),
    "HDFCLIFE": ("hdfc life", "hdFclife"),
    "SBILIFE": ("sbi life", "sbilife"),
    "TRENT": ("trent", "westside", "zudio"),
    "AVENUE": ("avenue supermarts", "dmart", "avenue"),
    "PIDILITIND": ("pidilite", "pidilitind", "fevicol"),
    "HAVELLS": ("havells", "havells india"),
    "SIEMENS": ("siemens india", "siemens"),
    "BEL": ("bharat electronics", "bel", "bharat electronics limited"),
    "BHEL": ("bhel", "bharat heavy electricals"),
    "HAL": ("hal", "hindustan aeronautics", "hindustan aeronautics limited"),
    "IRFC": ("irfc", "indian railway finance"),
    "IREDA": ("ireda", "indian renewable energy development"),
    "SUZLON": ("suzlon", "suzlon energy"),
    "HINDZINC": ("hindustan zinc", "hindzinc"),
    "VEDL": ("vedanta", "vedl"),
    "IOC": ("indian oil", "ioc", "indianoil"),
    "BPCL": ("bpcl", "bharat petroleum"),
    "GAIL": ("gail", "gail india"),
    "NATIONALUM": ("national aluminium", "nationalum", "nalco"),
    "ZOMATO": ("zomato", "blinkit"),
    "SWIGGY": ("swiggy",),
    "PAYTM": ("paytm", "one97 communications"),
    "POLICYBZR": ("policybazaar", "policybzr", "pb fintech"),
    "NYKAA": ("nykaa", "fsn ecommerce"),
    "HDFCAMC": ("hdfc asset management", "hdfcamc"),
    "GRASIM": ("grasim", "grasim industries"),
    "DIVISLAB": ("divi's laboratories", "divislab", "divi"),
    "CIPLA": ("cipla",),
    "DRREDDY": ("dr reddy", "drreddy", "dr. reddy"),
    "APOLLOHOSP": ("apollo hospitals", "apollohosp"),
    "AUROPHARMA": ("aurobinido pharma", "auropharma"),
    "TVSMOTOR": ("tvs motor", "tvsmotor"),
    "AAPL": ("apple", "aapl", "iphone"),
    "MSFT": ("microsoft", "msft", "windows", "azure"),
    "GOOGL": ("google", "alphabet", "googl", "goog"),
    "AMZN": ("amazon", "amzn", "aws"),
    "NVDA": ("nvidia", "nvda", "geforce"),
    "META": ("meta", "facebook", "meta platforms"),
    "TSLA": ("tesla", "tsla", "elon"),
    "JPM": ("jpmorgan", "jp morgan", "jpm", "chase"),
    "V": ("visa", "v"),
    "WMT": ("walmart", "wmt"),
    "JNJ": ("johnson & johnson", "jnj"),
    "PG": ("procter & gamble", "pg"),
    "XOM": ("exxon", "xom", "exxon mobil"),
    "UNH": ("unitedhealth", "unh", "united health"),
    "HD": ("home depot", "hd"),
    "BAC": ("bank of america", "bac"),
    "DIS": ("disney", "dis"),
    "NFLX": ("netflix", "nflx"),
    "ADBE": ("adobe", "adbe"),
    "CRM": ("salesforce", "crm"),
    "INTC": ("intel", "intc"),
    "AMD": ("amd", "advanced micro devices"),
    "PYPL": ("paypal", "pypl"),
    "UBER": ("uber", "uber technologies"),
    "NKE": ("nike", "nke"),
    "BA": ("boeing", "ba"),
    "COIN": ("coinbase", "coin"),
    "SNAP": ("snapchat", "snap"),
    "SQ": ("block", "square", "sq"),
    "PLTR": ("palantir", "pltr"),
    "RBLX": ("roblox", "rblx"),
    "MCD": ("mcdonald", "mcd", "mcdonald's"),
    "SBUX": ("starbucks", "sbux"),
    "NIO": ("nio",),
    "RIVN": ("rivian", "rivn"),
}

TRADE_PAIRS = {
    "USD": [("EUR/USD", -1, 0.0001), ("USD/JPY", 1, 0.01), ("GBP/USD", -1, 0.0001), ("USD/CAD", 1, 0.0001)],
    "EUR": [("EUR/USD", 1, 0.0001), ("EUR/GBP", 1, 0.0001)],
    "GBP": [("GBP/USD", 1, 0.0001), ("EUR/GBP", -1, 0.0001)],
    "JPY": [("USD/JPY", -1, 0.01)],
    "XAU": [("XAU/USD", 1, 0.1)],
    "XAG": [("XAG/USD", 1, 0.01)],
    "OIL": [("WTI", 1, 0.01), ("BRENT", 1, 0.01)],
    "BTC": [("BTC/USD", 1, 1.0)],
    "ETH": [("ETH/USD", 1, 1.0)],
    "SOL": [("SOL/USD", 1, 0.01)],
    "XRP": [("XRP/USD", 1, 0.0001)],
    "ADA": [("ADA/USD", 1, 0.0001)],
    "DOGE": [("DOGE/USD", 1, 0.0001)],
    "DOT": [("DOT/USD", 1, 0.001)],
    "AVAX": [("AVAX/USD", 1, 0.01)],
    "LINK": [("LINK/USD", 1, 0.01)],
    "LTC": [("LTC/USD", 1, 0.01)],
    "AUD": [("AUD/USD", -1, 0.0001), ("NZD/USD", -1, 0.0001)],
    "NZD": [("NZD/USD", -1, 0.0001), ("AUD/USD", -1, 0.0001)],
    "CHF": [("USD/CHF", 1, 0.0001)],
    "CAD": [("USD/CAD", 1, 0.0001)],
    "MXN": [("USD/MXN", 1, 0.001)],
    "ZAR": [("USD/ZAR", 1, 0.001)],
    "TRY": [("USD/TRY", 1, 0.001)],
    "SGD": [("USD/SGD", 1, 0.001)],
    "HKD": [("USD/HKD", 1, 0.001)],
    "CNY": [("USD/CNY", 1, 0.001)],
    "INR": [("USD/INR", 1, 0.01)],
    "US30": [("US30", 1, 1.0)],
    "US100": [("US100", 1, 1.0)],
    "SP500": [("SP500", 1, 1.0)],
    "UK100": [("UK100", 1, 1.0)],
    "GER40": [("GER40", 1, 1.0)],
    "JPN225": [("JPN225", 1, 1.0)],
    "HK50": [("HK50", 1, 1.0)],
    "AUS200": [("AUS200", 1, 1.0)],
    "NIFTY": [("NIFTY", 1, 1.0)],
    "SENSEX": [("SENSEX", 1, 1.0)],
    "BANKNIFTY": [("BANKNIFTY", 1, 1.0)],
    "FINNIFTY": [("FINNIFTY", 1, 1.0)],
    "MIDCAPNIFTY": [("MIDCAPNIFTY", 1, 1.0)],
    "VIXNIFTY": [("INDIAVIX", 1, 0.01)],
    "AAPL": [("AAPL", 1, 0.5)],
    "MSFT": [("MSFT", 1, 0.5)],
    "GOOGL": [("GOOGL", 1, 0.5)],
    "AMZN": [("AMZN", 1, 1.0)],
    "NVDA": [("NVDA", 1, 1.0)],
    "META": [("META", 1, 0.5)],
    "TSLA": [("TSLA", 1, 1.0)],
    "JPM": [("JPM", 1, 0.5)],
    "V": [("V", 1, 0.5)],
    "WMT": [("WMT", 1, 0.2)],
    "JNJ": [("JNJ", 1, 0.5)],
    "PG": [("PG", 1, 0.5)],
    "XOM": [("XOM", 1, 0.5)],
    "UNH": [("UNH", 1, 1.0)],
    "HD": [("HD", 1, 0.5)],
    "BAC": [("BAC", 1, 0.1)],
    "DIS": [("DIS", 1, 0.2)],
    "NFLX": [("NFLX", 1, 1.0)],
    "ADBE": [("ADBE", 1, 1.0)],
    "CRM": [("CRM", 1, 0.5)],
    "INTC": [("INTC", 1, 0.1)],
    "AMD": [("AMD", 1, 0.2)],
    "PYPL": [("PYPL", 1, 0.2)],
    "UBER": [("UBER", 1, 0.2)],
    "NKE": [("NKE", 1, 0.2)],
    "BA": [("BA", 1, 0.5)],
    "COIN": [("COIN", 1, 1.0)],
    "SNAP": [("SNAP", 1, 0.05)],
    "SQ": [("SQ", 1, 0.2)],
    "PLTR": [("PLTR", 1, 0.1)],
    "RBLX": [("RBLX", 1, 0.2)],
    "MCD": [("MCD", 1, 0.5)],
    "SBUX": [("SBUX", 1, 0.2)],
    "NIO": [("NIO", 1, 0.05)],
    "RIVN": [("RIVN", 1, 0.05)],
    "RELIANCE": [("RELIANCE", 1, 1.0)],
    "TCS": [("TCS", 1, 1.0)],
    "HDFCBANK": [("HDFCBANK", 1, 0.5)],
    "INFY": [("INFY", 1, 0.5)],
    "ICICIBANK": [("ICICIBANK", 1, 0.5)],
    "SBIN": [("SBIN", 1, 0.5)],
    "BHARTI": [("BHARTI", 1, 0.5)],
    "WIPRO": [("WIPRO", 1, 0.2)],
    "ITC": [("ITC", 1, 0.2)],
    "LT": [("LT", 1, 1.0)],
    "AXISBANK": [("AXISBANK", 1, 0.5)],
    "KOTAKBANK": [("KOTAKBANK", 1, 0.5)],
    "MARUTI": [("MARUTI", 1, 1.0)],
    "TATAMOTORS": [("TATAMOTORS", 1, 0.5)],
    "ASIANPAINT": [("ASIANPAINT", 1, 1.0)],
    "HCLTECH": [("HCLTECH", 1, 0.5)],
    "SUNPHARMA": [("SUNPHARMA", 1, 0.5)],
    "BAJFINANCE": [("BAJFINANCE", 1, 1.0)],
    "TITAN": [("TITAN", 1, 1.0)],
    "NTPC": [("NTPC", 1, 0.5)],
    "ONGC": [("ONGC", 1, 0.2)],
    "POWERGRID": [("POWERGRID", 1, 0.5)],
    "ULTRACEMCO": [("ULTRACEMCO", 1, 1.0)],
    "TATASTEEL": [("TATASTEEL", 1, 0.5)],
    "JSWSTEEL": [("JSWSTEEL", 1, 0.5)],
    "HINDALCO": [("HINDALCO", 1, 0.5)],
    "TECHM": [("TECHM", 1, 0.5)],
    "COALINDIA": [("COALINDIA", 1, 0.2)],
    "HINDUNILVR": [("HINDUNILVR", 1, 1.0)],
    "BRITANNIA": [("BRITANNIA", 1, 1.0)],
    "NESTLEIND": [("NESTLEIND", 1, 2.0)],
    "M&M": [("M&M", 1, 0.5)],
    "EICHERMOT": [("EICHERMOT", 1, 1.0)],
    "HEROMOTOCO": [("HEROMOTOCO", 1, 0.5)],
    "BAJAJ-AUTO": [("BAJAJ_AUTO", 1, 1.0)],
    "TATACONSUM": [("TATACONSUM", 1, 0.5)],
    "DABUR": [("DABUR", 1, 0.5)],
    "MARICO": [("MARICO", 1, 0.5)],
    "HDFC": [("HDFC", 1, 0.5)],
    "ICICIPRUDI": [("ICICIPRUDI", 1, 0.5)],
    "HDFCLIFE": [("HDFCLIFE", 1, 0.2)],
    "SBILIFE": [("SBILIFE", 1, 0.5)],
    "TRENT": [("TRENT", 1, 1.0)],
    "AVENUE": [("AVENUE", 1, 1.0)],
    "PIDILITIND": [("PIDILITIND", 1, 0.5)],
    "HAVELLS": [("HAVELLS", 1, 0.5)],
    "SIEMENS": [("SIEMENS", 1, 1.0)],
    "BEL": [("BEL", 1, 0.5)],
    "BHEL": [("BHEL", 1, 0.1)],
    "HAL": [("HAL", 1, 1.0)],
    "IRFC": [("IRFC", 1, 0.1)],
    "IREDA": [("IREDA", 1, 0.1)],
    "SUZLON": [("SUZLON", 1, 0.05)],
    "ADANIENT": [("ADANIENT", 1, 1.0)],
    "ADANIPORTS": [("ADANIPORTS", 1, 0.5)],
    "ADANIGREEN": [("ADANIGREEN", 1, 0.5)],
    "ADANITRANS": [("ADANITRANS", 1, 0.5)],
    "ADANIPOWER": [("ADANIPOWER", 1, 0.2)],
    "HINDZINC": [("HINDZINC", 1, 0.2)],
    "VEDL": [("VEDL", 1, 0.2)],
    "IOC": [("IOC", 1, 0.2)],
    "BPCL": [("BPCL", 1, 0.2)],
    "GAIL": [("GAIL", 1, 0.2)],
    "NATIONALUM": [("NATIONALUM", 1, 0.2)],
    "ZOMATO": [("ZOMATO", 1, 0.1)],
    "SWIGGY": [("SWIGGY", 1, 0.1)],
    "PAYTM": [("PAYTM", 1, 0.1)],
    "POLICYBZR": [("POLICYBZR", 1, 0.1)],
    "NYKAA": [("NYKAA", 1, 0.2)],
    "HDFCAMC": [("HDFCAMC", 1, 0.5)],
    "GRASIM": [("GRASIM", 1, 1.0)],
    "DIVISLAB": [("DIVISLAB", 1, 1.0)],
    "CIPLA": [("CIPLA", 1, 0.5)],
    "DRREDDY": [("DRREDDY", 1, 1.0)],
    "APOLLOHOSP": [("APOLLOHOSP", 1, 1.0)],
    "AUROPHARMA": [("AUROPHARMA", 1, 0.2)],
    "TVSMOTOR": [("TVSMOTOR", 1, 0.5)],
}

INSTRUMENT_NAMES: dict[str, str] = {
    "XAU/USD": "Gold vs US Dollar",
    "XAG/USD": "Silver vs US Dollar",
    "EUR/USD": "Euro vs US Dollar",
    "GBP/USD": "British Pound vs US Dollar",
    "USD/JPY": "US Dollar vs Japanese Yen",
    "USD/CAD": "US Dollar vs Canadian Dollar",
    "EUR/GBP": "Euro vs British Pound",
    "WTI": "Crude Oil WTI",
    "BRENT": "Brent Crude Oil",
    "BTC/USD": "Bitcoin vs US Dollar",
    "ETH/USD": "Ethereum vs US Dollar",
    "SOL/USD": "Solana vs US Dollar",
    "XRP/USD": "Ripple vs US Dollar",
    "ADA/USD": "Cardano vs US Dollar",
    "DOGE/USD": "Dogecoin vs US Dollar",
    "DOT/USD": "Polkadot vs US Dollar",
    "AVAX/USD": "Avalanche vs US Dollar",
    "LINK/USD": "Chainlink vs US Dollar",
    "LTC/USD": "Litecoin vs US Dollar",
    "AUD/USD": "Australian Dollar vs US Dollar",
    "NZD/USD": "New Zealand Dollar vs US Dollar",
    "USD/CHF": "US Dollar vs Swiss Franc",
    "USD/CAD": "US Dollar vs Canadian Dollar",
    "USD/MXN": "US Dollar vs Mexican Peso",
    "USD/ZAR": "US Dollar vs South African Rand",
    "USD/TRY": "US Dollar vs Turkish Lira",
    "USD/SGD": "US Dollar vs Singapore Dollar",
    "USD/HKD": "US Dollar vs Hong Kong Dollar",
    "USD/CNY": "US Dollar vs Chinese Yuan",
    "USD/INR": "US Dollar vs Indian Rupee",
    "US30": "Dow Jones Industrial Average",
    "US100": "NASDAQ 100",
    "SP500": "S&P 500 Index",
    "UK100": "FTSE 100 Index",
    "GER40": "DAX 40 Index",
    "JPN225": "Nikkei 225 Index",
    "HK50": "Hang Seng Index",
    "AUS200": "S&P/ASX 200 Index",
    "NIFTY": "Nifty 50",
    "SENSEX": "BSE Sensex",
    "BANKNIFTY": "Bank Nifty",
    "FINNIFTY": "Fin Nifty",
    "MIDCAPNIFTY": "Nifty Midcap 100",
    "VIXNIFTY": "India VIX",
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "GOOGL": "Alphabet Inc. (Google)",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corporation",
    "META": "Meta Platforms Inc. (Facebook)",
    "TSLA": "Tesla Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "WMT": "Walmart Inc.",
    "JNJ": "Johnson & Johnson",
    "PG": "Procter & Gamble Co.",
    "XOM": "Exxon Mobil Corporation",
    "UNH": "UnitedHealth Group Inc.",
    "HD": "The Home Depot Inc.",
    "BAC": "Bank of America Corporation",
    "DIS": "The Walt Disney Company",
    "NFLX": "Netflix Inc.",
    "ADBE": "Adobe Inc.",
    "CRM": "Salesforce Inc.",
    "INTC": "Intel Corporation",
    "AMD": "Advanced Micro Devices Inc.",
    "PYPL": "PayPal Holdings Inc.",
    "UBER": "Uber Technologies Inc.",
    "NKE": "Nike Inc.",
    "BA": "The Boeing Company",
    "COIN": "Coinbase Global Inc.",
    "SNAP": "Snap Inc. (Snapchat)",
    "SQ": "Block Inc. (Square)",
    "PLTR": "Palantir Technologies Inc.",
    "RBLX": "Roblox Corporation",
    "MCD": "McDonald's Corporation",
    "SBUX": "Starbucks Corporation",
    "NIO": "NIO Inc.",
    "RIVN": "Rivian Automotive Inc.",
    "RELIANCE": "Reliance Industries Ltd.",
    "TCS": "Tata Consultancy Services",
    "HDFCBANK": "HDFC Bank Ltd.",
    "INFY": "Infosys Ltd.",
    "ICICIBANK": "ICICI Bank Ltd.",
    "SBIN": "State Bank of India",
    "BHARTI": "Bharti Airtel Ltd.",
    "WIPRO": "Wipro Ltd.",
    "ITC": "ITC Ltd.",
    "LT": "Larsen & Toubro Ltd.",
    "AXISBANK": "Axis Bank Ltd.",
    "KOTAKBANK": "Kotak Mahindra Bank Ltd.",
    "MARUTI": "Maruti Suzuki India Ltd.",
    "TATAMOTORS": "Tata Motors Ltd.",
    "ASIANPAINT": "Asian Paints Ltd.",
    "HCLTECH": "HCL Technologies Ltd.",
    "SUNPHARMA": "Sun Pharmaceutical Industries Ltd.",
    "BAJFINANCE": "Bajaj Finance Ltd.",
    "TITAN": "Titan Company Ltd.",
    "NTPC": "NTPC Ltd.",
    "ONGC": "Oil & Natural Gas Corporation Ltd.",
    "POWERGRID": "Power Grid Corporation of India Ltd.",
    "ULTRACEMCO": "UltraTech Cement Ltd.",
    "TATASTEEL": "Tata Steel Ltd.",
    "JSWSTEEL": "JSW Steel Ltd.",
    "HINDALCO": "Hindalco Industries Ltd.",
    "TECHM": "Tech Mahindra Ltd.",
    "COALINDIA": "Coal India Ltd.",
    "HINDUNILVR": "Hindustan Unilever Ltd.",
    "BRITANNIA": "Britannia Industries Ltd.",
    "NESTLEIND": "Nestlé India Ltd.",
    "M&M": "Mahindra & Mahindra Ltd.",
    "EICHERMOT": "Eicher Motors Ltd.",
    "HEROMOTOCO": "Hero MotoCorp Ltd.",
    "BAJAJ_AUTO": "Bajaj Auto Ltd.",
    "TATACONSUM": "Tata Consumer Products Ltd.",
    "DABUR": "Dabur India Ltd.",
    "MARICO": "Marico Ltd.",
    "HDFC": "HDFC Ltd.",
    "ICICIPRUDI": "ICICI Prudential Life Insurance",
    "HDFCLIFE": "HDFC Life Insurance Company",
    "SBILIFE": "SBI Life Insurance Company",
    "TRENT": "Trent Ltd.",
    "AVENUE": "Avenue Supermarts Ltd. (DMart)",
    "PIDILITIND": "Pidilite Industries Ltd.",
    "HAVELLS": "Havells India Ltd.",
    "SIEMENS": "Siemens Ltd.",
    "BEL": "Bharat Electronics Ltd.",
    "BHEL": "Bharat Heavy Electricals Ltd.",
    "HAL": "Hindustan Aeronautics Ltd.",
    "IRFC": "Indian Railway Finance Corporation",
    "IREDA": "Indian Renewable Energy Development Agency",
    "SUZLON": "Suzlon Energy Ltd.",
    "ADANIENT": "Adani Enterprises Ltd.",
    "ADANIPORTS": "Adani Ports & SEZ Ltd.",
    "ADANIGREEN": "Adani Green Energy Ltd.",
    "ADANITRANS": "Adani Transmission Ltd.",
    "ADANIPOWER": "Adani Power Ltd.",
    "HINDZINC": "Hindustan Zinc Ltd.",
    "VEDL": "Vedanta Ltd.",
    "IOC": "Indian Oil Corporation Ltd.",
    "BPCL": "Bharat Petroleum Corporation Ltd.",
    "GAIL": "GAIL (India) Ltd.",
    "NATIONALUM": "National Aluminium Company Ltd.",
    "ZOMATO": "Zomato Ltd.",
    "SWIGGY": "Swiggy Ltd.",
    "PAYTM": "One97 Communications Ltd. (Paytm)",
    "POLICYBZR": "PB Fintech Ltd. (Policybazaar)",
    "NYKAA": "FSN E-Commerce Ventures Ltd. (Nykaa)",
    "HDFCAMC": "HDFC Asset Management Company",
    "GRASIM": "Grasim Industries Ltd.",
    "DIVISLAB": "Divi's Laboratories Ltd.",
    "CIPLA": "Cipla Ltd.",
    "DRREDDY": "Dr. Reddy's Laboratories Ltd.",
    "APOLLOHOSP": "Apollo Hospitals Enterprise Ltd.",
    "AUROPHARMA": "Aurobindo Pharma Ltd.",
    "TVSMOTOR": "TVS Motor Company Ltd.",
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
    "rally",
    "rallies",
    "breakout",
    "bullish",
    "recovery",
    "rebound",
    "upgrade",
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
    "crash",
    "plunge",
    "decline",
    "bearish",
    "selloff",
    "downgrade",
    "slump",
}

HIGH_IMPACT_KEYWORDS = {
    "breaking", "just in", "urgent", "emergency",
    "fed rate decision", "fomc", "interest rate decision",
    "nonfarm payrolls", "nfp", "jobs report",
    "cpi", "consumer price index", "inflation data",
    "gdp", "economic growth",
    "crash", "plunge", "selloff", "rout",
    "war", "invasion", "sanctions",
    "central bank", "rate hike", "rate cut",
    "recession", "depression",
    "bankruptcy", "bailout",
    "black swan", "flash crash",
    "market crash", "stock crash",
    "fed emergency", "emergency meeting",
}

TRADING_SYSTEM_PROMPT = (
    "You are a professional Telegram trading signal bot. "
    "You generate clear, actionable trade setups with entry, targets, and stop-loss levels. "
    "You are concise, factual, and never give financial advice — only data-driven setups. "
    "Always state the direction, pair, entry price, TP1, TP2, and SL. "
    "Keep financial terms in English. "
    "Use bullet points or numbered lists for readability."
)


def load_seen_keys() -> set[str]:
    try:
        with open(SENT_KEYS_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_keys(keys: set[str]) -> None:
    with open(SENT_KEYS_FILE, "w") as f:
        json.dump(sorted(keys), f)


def load_signal_log() -> list[dict]:
    try:
        with open(SIGNAL_LOG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_signal_log(log: list[dict]) -> None:
    with open(SIGNAL_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def load_subscribers() -> list[int]:
    try:
        with open(SUBSCRIBERS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_subscribers(subs: list[int]) -> None:
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subs, f)


def _backfill_subscribers_from_updates() -> None:
    global _subscribers
    try:
        from urllib.request import urlopen
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        resp = urlopen(url, timeout=10)
        data = json.loads(resp.read().decode())
        added = 0
        for upd in data.get("result", []):
            msg = upd.get("message")
            if msg:
                cid = msg.get("chat", {}).get("id")
                if cid and isinstance(cid, int) and cid not in _subscribers:
                    _subscribers.append(cid)
                    added += 1
        if added:
            save_subscribers(_subscribers)
            print(f"[BACKFILL] Added {added} chat ID(s) from recent updates.")
    except Exception as exc:
        print(f"[BACKFILL] Skipped (not critical): {exc}")


def log_signal(pair: str, direction: str, entry: float, tp1: float, tp2: float, sl: float, source: str) -> None:
    global _signal_log
    record = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "time": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        "pair": pair,
        "direction": direction,
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
        "source": source,
    }
    _signal_log.append(record)
    save_signal_log(_signal_log)


def get_active_provider() -> str:
    if NEWS_PROVIDER in {"newsdata", "newsapi", "finnhub"}:
        return NEWS_PROVIDER
    if FINNHUB_API_KEY:
        return "finnhub"
    if NEWS_API_KEY:
        return "newsapi"
    return "newsdata"


def build_newsdata_url(query: str) -> str:
    params = {
        "apikey": NEWSDATA_API_KEY,
        "q": query,
        "language": "en",
        "category": "business",
    }
    return f"{NEWSDATA_API_URL}?{urlencode(params)}"


def build_newsapi_url(query: str) -> str:
    params = {
        "apiKey": NEWS_API_KEY,
        "q": query,
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


def identify_asset(article: dict[str, Any]) -> str:
    text = normalize_text(article)
    for symbol, hints in CURRENCY_HINTS.items():
        if any(hint in text for hint in hints):
            return symbol
    return "MARKET"


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
        for asset, pairs in TRADE_PAIRS.items():
            for pair, _, _ in pairs:
                if pair in rates:
                    continue
                if "/" not in pair:
                    continue
                base, quote = pair.split("/")
                b_rate = usd_base.get(base)
                q_rate = usd_base.get(quote)
                if b_rate and q_rate:
                    rates[pair] = q_rate / b_rate
    except Exception:
        pass

    yf_map = {
        "XAU/USD": "GC=F",
        "XAG/USD": "SI=F",
        "WTI": "CL=F",
        "BRENT": "BZ=F",
        "US10Y": "^TNX",
        "BTC/USD": "BTC-USD",
        "ETH/USD": "ETH-USD",
        "SOL/USD": "SOL-USD",
        "XRP/USD": "XRP-USD",
        "ADA/USD": "ADA-USD",
        "DOGE/USD": "DOGE-USD",
        "DOT/USD": "DOT-USD",
        "AVAX/USD": "AVAX-USD",
        "LINK/USD": "LINK-USD",
        "LTC/USD": "LTC-USD",
        "US30": "^DJI",
        "US100": "^IXIC",
        "DXY": "DX-Y.NYB",
        "SP500": "^GSPC",
        "UK100": "^FTSE",
        "GER40": "^GDAXI",
        "JPN225": "^N225",
        "HK50": "^HSI",
        "AUS200": "^AXJO",
        "NIFTY": "^NSEI",
        "SENSEX": "^BSESN",
        "BANKNIFTY": "^NSEBANK",
        "AAPL": "AAPL",
        "MSFT": "MSFT",
        "GOOGL": "GOOGL",
        "AMZN": "AMZN",
        "NVDA": "NVDA",
        "META": "META",
        "TSLA": "TSLA",
        "JPM": "JPM",
        "V": "V",
        "WMT": "WMT",
        "JNJ": "JNJ",
        "PG": "PG",
        "XOM": "XOM",
        "UNH": "UNH",
        "HD": "HD",
        "BAC": "BAC",
        "DIS": "DIS",
        "NFLX": "NFLX",
        "ADBE": "ADBE",
        "CRM": "CRM",
        "INTC": "INTC",
        "AMD": "AMD",
        "PYPL": "PYPL",
        "UBER": "UBER",
        "NKE": "NKE",
        "BA": "BA",
        "COIN": "COIN",
        "SNAP": "SNAP",
        "SQ": "SQ",
        "PLTR": "PLTR",
        "RBLX": "RBLX",
        "MCD": "MCD",
        "SBUX": "SBUX",
        "NIO": "NIO",
        "RIVN": "RIVN",
        "RELIANCE": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "HDFCBANK": "HDFCBANK.NS",
        "INFY": "INFY.NS",
        "ICICIBANK": "ICICIBANK.NS",
        "SBIN": "SBIN.NS",
        "BHARTI": "BHARTIARTL.NS",
        "WIPRO": "WIPRO.NS",
        "ITC": "ITC.NS",
        "LT": "LT.NS",
        "AXISBANK": "AXISBANK.NS",
        "KOTAKBANK": "KOTAKBANK.NS",
        "MARUTI": "MARUTI.NS",
        "TATAMOTORS": "TATAMOTORS.NS",
        "ASIANPAINT": "ASIANPAINT.NS",
        "HCLTECH": "HCLTECH.NS",
        "SUNPHARMA": "SUNPHARMA.NS",
        "BAJFINANCE": "BAJFINANCE.NS",
        "TITAN": "TITAN.NS",
        "NTPC": "NTPC.NS",
        "ONGC": "ONGC.NS",
        "POWERGRID": "POWERGRID.NS",
        "ULTRACEMCO": "ULTRACEMCO.NS",
        "TATASTEEL": "TATASTEEL.NS",
        "JSWSTEEL": "JSWSTEEL.NS",
        "HINDALCO": "HINDALCO.NS",
        "TECHM": "TECHM.NS",
        "COALINDIA": "COALINDIA.NS",
        "HINDUNILVR": "HINDUNILVR.NS",
        "BRITANNIA": "BRITANNIA.NS",
        "NESTLEIND": "NESTLEIND.NS",
        "M&M": "M&M.NS",
        "EICHERMOT": "EICHERMOT.NS",
        "HEROMOTOCO": "HEROMOTOCO.NS",
        "BAJAJ_AUTO": "BAJAJ-AUTO.NS",
        "TATACONSUM": "TATACONSUM.NS",
        "DABUR": "DABUR.NS",
        "MARICO": "MARICO.NS",
        "HDFC": "HDFC.NS",
        "ICICIPRUDI": "ICICIPRUDI.NS",
        "HDFCLIFE": "HDFCLIFE.NS",
        "SBILIFE": "SBILIFE.NS",
        "TRENT": "TRENT.NS",
        "AVENUE": "AVENUE.NS",
        "PIDILITIND": "PIDILITIND.NS",
        "HAVELLS": "HAVELLS.NS",
        "SIEMENS": "SIEMENS.NS",
        "BEL": "BEL.NS",
        "BHEL": "BHEL.NS",
        "HAL": "HAL.NS",
        "IRFC": "IRFC.NS",
        "IREDA": "IREDA.NS",
        "SUZLON": "SUZLON.NS",
        "ADANIENT": "ADANIENT.NS",
        "ADANIPORTS": "ADANIPORTS.NS",
        "ADANIGREEN": "ADANIGREEN.NS",
        "ADANITRANS": "ADANITRANS.NS",
        "ADANIPOWER": "ADANIPOWER.NS",
        "HINDZINC": "HINDZINC.NS",
        "VEDL": "VEDL.NS",
        "IOC": "IOC.NS",
        "BPCL": "BPCL.NS",
        "GAIL": "GAIL.NS",
        "NATIONALUM": "NATIONALUM.NS",
        "ZOMATO": "ZOMATO.NS",
        "SWIGGY": "SWIGGY.NS",
        "PAYTM": "PAYTM.NS",
        "POLICYBZR": "POLICYBZR.NS",
        "NYKAA": "NYKAA.NS",
        "HDFCAMC": "HDFCAMC.NS",
        "GRASIM": "GRASIM.NS",
        "DIVISLAB": "DIVISLAB.NS",
        "CIPLA": "CIPLA.NS",
        "DRREDDY": "DRREDDY.NS",
        "APOLLOHOSP": "APOLLOHOSP.NS",
        "AUROPHARMA": "AUROPHARMA.NS",
        "TVSMOTOR": "TVSMOTOR.NS",
    }
    try:
        for pair, ticker in yf_map.items():
            if pair not in rates:
                tk = yf.Ticker(ticker)
                hist = tk.history(period="1d")
                if not hist.empty:
                    rates[pair] = round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass

    return rates


def compute_confidence(text: str) -> tuple[str, str]:
    score = sum(1 for word in POSITIVE_KEYWORDS if word in text)
    score -= sum(1 for word in NEGATIVE_KEYWORDS if word in text)
    abs_score = abs(score)
    if abs_score >= 4:
        level = "High"
    elif abs_score >= 2:
        level = "Medium"
    else:
        level = "Low"
    direction = "Bullish" if score > 0 else "Bearish"
    return direction, level


def is_high_impact(article: dict[str, Any]) -> bool:
    text = normalize_text(article)
    return any(kw in text for kw in HIGH_IMPACT_KEYWORDS)


def format_trade_lines(bias: str, source: str = "news") -> str | None:
    parts = bias.split()
    if len(parts) != 2:
        return None
    direction_str, asset = parts[0], parts[1]
    pairs = TRADE_PAIRS.get(asset)
    if not pairs:
        return None
    is_bullish = direction_str == "Bullish"
    prices = fetch_current_prices()
    lines: list[str] = []
    for i, (pair, multiplier, pip_size) in enumerate(pairs, 1):
        price = prices.get(pair)
        if not price:
            lines.append(f"{i}. {pair}")
            continue
        is_buy = (is_bullish == (multiplier > 0))
        entry = round(price, 4)
        tp1 = round(price + (30 * pip_size) if is_buy else price - (30 * pip_size), 4)
        tp2 = round(price + (50 * pip_size) if is_buy else price - (50 * pip_size), 4)
        sl = round(price - (20 * pip_size) if is_buy else price + (20 * pip_size), 4)
        dir_label = "BUY" if is_buy else "SELL"
        icon = " 🟢" if is_buy else " 🔴"
        lines.append(f"{i}.{icon} {dir_label} {pair} @ {_price_str(entry, pair)}")
        lines.append(f"   Targets: {_price_str(tp1, pair)} / {_price_str(tp2, pair)} | SL: {_price_str(sl, pair)}")
        log_signal(pair, dir_label, entry, tp1, tp2, sl, source)
    return "\n".join(lines) if lines else None


def detect_asset_in_text(text: str) -> str | None:
    text_lower = text.lower()
    for symbol, hints in CURRENCY_HINTS.items():
        if any(hint in text_lower for hint in hints):
            return symbol
    return None


def ai_verify_trade_suggestion(trade_text: str, asset: str) -> str | None:
    prompt = (
        "You are an expert trading analyst. Verify this trade suggestion:\n"
        f"{trade_text}\n\n"
        f"Is this a reasonable trade setup for {asset}? "
        "Consider current market conditions. "
        "Reply: 'APPROVED - [reason]' or 'REJECTED - [reason]'. "
        "Be concise - max 2 sentences."
    )
    return _best_ai(prompt)


def ai_enhance_trade_suggestion(trade_text: str, context_title: str) -> str | None:
    prompt = (
        "You are an expert trading analyst improving a trade suggestion.\n"
        f"Current suggestion:\n{trade_text}\n\n"
        f"News context: {context_title}\n\n"
        "Review this suggestion for:\n"
        "1. Direction correctness based on the news\n"
        "2. Sensible entry/TP/SL levels\n"
        "3. Risk management quality\n\n"
        "If it is already good, reply 'OK'.\n"
        "If it needs improvement, provide the improved version. "
        "Keep the same format (BUY/SELL, @, Targets:, SL). "
        "Max 2 sentences of explanation."
    )
    result = _best_ai(prompt)
    if result and result.strip().upper() == "OK":
        return None
    return result


def generate_asset_trade_setup(asset: str, question: str) -> str | None:
    pairs = TRADE_PAIRS.get(asset)
    if not pairs:
        return None

    prices = fetch_current_prices()

    dir_prompt = (
        f"Based on this question: '{question}'\n"
        f"Should we go LONG (buy) or SHORT (sell) {asset}? "
        "Reply with only one word: LONG or SHORT."
    )
    direction = _best_ai(dir_prompt, system_prompt=TRADING_SYSTEM_PROMPT)
    if not direction:
        return None
    is_bullish = "LONG" in direction.strip().upper()

    lines: list[str] = []
    for i, (pair, multiplier, pip_size) in enumerate(pairs, 1):
        price = prices.get(pair)
        if not price:
            lines.append(f"{i}. {pair} - price unavailable")
            continue
        is_buy = (is_bullish == (multiplier > 0))
        entry = round(price, 4)
        tp1 = round(price + (30 * pip_size) if is_buy else price - (30 * pip_size), 4)
        tp2 = round(price + (50 * pip_size) if is_buy else price - (50 * pip_size), 4)
        sl = round(price - (20 * pip_size) if is_buy else price + (20 * pip_size), 4)
        dir_label = "BUY" if is_buy else "SELL"
        icon = " 🟢" if is_buy else " 🔴"
        lines.append(f"{i}.{icon} {dir_label} {pair} @ {_price_str(entry, pair)}")
        lines.append(f"   Targets: {_price_str(tp1, pair)} / {_price_str(tp2, pair)} | SL: {_price_str(sl, pair)}")
        log_signal(pair, dir_label, entry, tp1, tp2, sl, "question")

    if not lines:
        return None

    trade_text = "\n".join(lines)
    verification = ai_verify_trade_suggestion(trade_text, asset)

    result = [f"<b>Real-Time Setup ({asset}):</b>", trade_text]
    if verification:
        result.append(f"\n<b>AI Verification:</b> {verification}")

    return "\n".join(result)


def _groq_chat(prompt: str, system_prompt: str | None = None) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        import requests
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
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return escape(text)
    except Exception:
        return None


# ── Finnhub API helpers ──────────────────────────────────────────────────────

_FINNHUB_SESSION_CACHE: dict[str, tuple[float, dict]] = {}


def _finnhub_get(path: str, params: dict | None = None) -> dict | None:
    if not FINNHUB_API_KEY:
        return None
    try:
        p = dict(params or {})
        p["token"] = FINNHUB_API_KEY
        url = f"{FINNHUB_BASE}{path}?{urlencode(p)}"
        with urlopen(url, timeout=10) as r:
            return json.load(r)
    except Exception:
        return None


def finnhub_quote(symbol: str) -> dict | None:
    """Get real-time quote for a stock symbol from Finnhub."""
    return _finnhub_get("/quote", {"symbol": symbol})


def finnhub_company_news(symbol: str, from_date: str = "", to_date: str = "") -> list[dict]:
    """Get company news from Finnhub."""
    now = datetime.now(timezone.utc)
    to_d = to_date or now.strftime("%Y-%m-%d")
    from_d = from_date or (now - timedelta(days=7)).strftime("%Y-%m-%d")
    data = _finnhub_get("/company-news", {"symbol": symbol, "from": from_d, "to": to_d})
    return data if isinstance(data, list) else []


def finnhub_market_news(category: str = "general") -> list[dict]:
    """Get market news. Categories: general, forex, crypto, merger."""
    data = _finnhub_get("/news", {"category": category})
    return data if isinstance(data, list) else []


def finnhub_news_sentiment(symbol: str) -> dict | None:
    """Get news sentiment for a stock from Finnhub."""
    return _finnhub_get("/news-sentiment", {"symbol": symbol})


def finnhub_stock_symbols(exchange: str = "US") -> list[dict]:
    """Get list of stock symbols for an exchange."""
    data = _finnhub_get("/stock/symbol", {"exchange": exchange})
    return data if isinstance(data, list) else []


def finnhub_company_profile(symbol: str) -> dict | None:
    """Get company profile from Finnhub."""
    return _finnhub_get("/stock/profile2", {"symbol": symbol})


def finnhub_enrich_with_sentiment(asset: str) -> str | None:
    """Enrich trade signal with Finnhub sentiment data."""
    finnhub_symbol = _asset_to_finnhub_symbol(asset)
    if not finnhub_symbol:
        return None
    quote = finnhub_quote(finnhub_symbol)
    sentiment = finnhub_news_sentiment(finnhub_symbol)
    parts: list[str] = []
    if quote:
        c = quote.get("c")
        dp = quote.get("dp")
        h = quote.get("h")
        l = quote.get("l")
        if c:
            chg_str = f" ({'+' if dp and dp >= 0 else ''}{dp:.2f}%)" if dp else ""
            parts.append(f"Last: {c}{chg_str}")
            if h and l:
                parts.append(f"Day Range: {l} - {h}")
    if sentiment:
        bs = sentiment.get("bearishPercent")
        bsp = sentiment.get("bullishPercent")
        if bs is not None and bsp is not None:
            parts.append(f"Bearish: {bs:.1f}% / Bullish: {bsp:.1f}%")
        mention = sentiment.get("mentionCount")
        if mention:
            parts.append(f"Mentions: {mention}")
    return " | ".join(parts) if parts else None


def _asset_to_finnhub_symbol(asset: str) -> str | None:
    """Map internal asset symbols to Finnhub tickers."""
    m = {
        "AAPL": "AAPL", "MSFT": "MSFT", "GOOGL": "GOOGL", "AMZN": "AMZN",
        "NVDA": "NVDA", "META": "META", "TSLA": "TSLA", "JPM": "JPM",
        "V": "V", "WMT": "WMT", "JNJ": "JNJ", "PG": "PG",
        "XOM": "XOM", "UNH": "UNH", "HD": "HD", "BAC": "BAC",
        "DIS": "DIS", "NFLX": "NFLX", "ADBE": "ADBE", "CRM": "CRM",
        "INTC": "INTC", "AMD": "AMD", "PYPL": "PYPL", "UBER": "UBER",
        "NKE": "NKE", "BA": "BA", "COIN": "COIN", "SNAP": "SNAP",
        "SQ": "SQ", "PLTR": "PLTR", "RBLX": "RBLX", "MCD": "MCD",
        "SBUX": "SBUX", "NIO": "NIO", "RIVN": "RIVN",
        "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS",
        "HDFCBANK": "HDFCBANK.NS", "INFY": "INFY.NS",
        "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
        "BHARTI": "BHARTIARTL.NS", "WIPRO": "WIPRO.NS",
        "ITC": "ITC.NS", "LT": "LT.NS", "MARUTI": "MARUTI.NS",
        "TATAMOTORS": "TATAMOTORS.NS", "NIFTY": "^NSEI",
        "SENSEX": "^BSESN", "XAU/USD": "GC=F", "XAG/USD": "SI=F",
        "WTI": "CL=F", "BRENT": "BZ=F", "BTC/USD": "BTC-USD",
        "ETH/USD": "ETH-USD",
    }
    return m.get(asset)


# ── OpenAI API helper (alternative to Groq) ──────────────────────────────────

def _openai_chat(prompt: str, system_prompt: str | None = None) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        import requests
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
                "max_tokens": 500,
            },
            timeout=20,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return escape(text)
    except Exception:
        return None


def _best_ai(prompt: str, system_prompt: str | None = None) -> str | None:
    """Try OpenAI first, fall back to Groq."""
    result = _openai_chat(prompt, system_prompt)
    if result:
        return result
    return _groq_chat(prompt, system_prompt)


def ai_enhanced_market_analysis(asset: str, news_text: str) -> str | None:
    """Use OpenAI for deeper market analysis with Finnhub data enrichment."""
    finnhub_data = finnhub_enrich_with_sentiment(asset)
    context = f"Asset: {asset}\nNews: {news_text[:500]}"
    if finnhub_data:
        context += f"\nMarket Data: {finnhub_data}"
    prompt = (
        "You are an expert financial analyst. Analyze this asset based on the news and market data provided.\n\n"
        f"{context}\n\n"
        "Provide:\n"
        "1. Direction bias (Bullish/Bearish/Neutral) with confidence level\n"
        "2. Key support and resistance levels\n"
        "3. Entry strategy with specific price zones\n"
        "4. Risk management advice\n"
        "Keep it concise - max 5 sentences."
    )
    return _best_ai(prompt, "You are a professional trading analyst. Be factual and data-driven.")


def finnhub_fetch_news(category: str = "general") -> list[dict]:
    """Fetch news from Finnhub and normalize to our format."""
    raw = finnhub_market_news(category)
    articles: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pub = item.get("datetime")
        pub_dt = ""
        if pub:
            try:
                pub_dt = datetime.fromtimestamp(pub, tz=timezone.utc).isoformat()
            except Exception:
                pub_dt = ""
        articles.append({
            "article_id": item.get("id") or item.get("url") or item.get("headline", ""),
            "title": item.get("headline", ""),
            "description": item.get("summary", ""),
            "link": item.get("url", ""),
            "pubDate": pub_dt,
            "source_name": item.get("source", "Finnhub"),
            "keywords": item.get("categories", []),
            "related": item.get("related", ""),
        })
    return articles


def build_market_context() -> str:
    ctx_parts: list[str] = []
    try:
        prices = fetch_current_prices()
        key_prices = {
            "XAU/USD": prices.get("XAU/USD"),
            "US100": prices.get("US100"),
            "EUR/USD": prices.get("EUR/USD"),
            "BTC/USD": prices.get("BTC/USD"),
        }
        for name, price in key_prices.items():
            if price:
                ctx_parts.append(f"{name}: {price}")
    except Exception:
        pass
    if not ctx_parts:
        return ""
    return "Current prices: " + ", ".join(ctx_parts) + "."


def ai_analyze_news(article: dict[str, Any]) -> str | None:
    title = article.get("title", "")
    desc = (article.get("description") or "")[:200]
    market_ctx = build_market_context()

    asset = identify_asset(article)
    finnhub_enrichment = ""
    if asset and asset != "MARKET":
        try:
            fh = finnhub_enrich_with_sentiment(asset)
            if fh:
                finnhub_enrichment = f"\nFinnhub Data: {fh}"
        except Exception:
            pass

    prompt = (
        f"News: {title}\n{desc}\n\n"
        f"{market_ctx}{finnhub_enrichment}\n\n"
        "Give a 1-line trading insight for this financial news. "
        "Mention direction (bullish/bearish) and which asset. "
        "Be specific (entry bias, key level). Max 20 words."
    )
    return _best_ai(prompt, system_prompt=TRADING_SYSTEM_PROMPT)


def ai_answer_question(question: str) -> str | None:
    market_ctx = build_market_context()
    prompt = (
        "You are an expert forex and stock market trading analyst. "
        "Answer the user's trading question concisely and accurately. "
        "Provide analysis, direction (bullish/bearish), key price levels if applicable, "
        "and risk management advice.\n\n"
        f"{market_ctx}\n\n"
        f"Question: {question}\n\n"
        "Keep it under 150 words. Be specific about entry zones, not just direction."
    )
    return _best_ai(prompt, system_prompt=TRADING_SYSTEM_PROMPT)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _subscribers
    chat_id = update.effective_chat.id
    if chat_id not in _subscribers:
        _subscribers.append(chat_id)
        save_subscribers(_subscribers)
        print(f"[SUBSCRIBE] Chat {chat_id} subscribed via /start")
    await update.message.reply_text(
        "<b>ForexSignalAI Trade Analyzer</b>\n\n"
        "You are now subscribed to trading signals and market updates.\n\n"
        "Send me any trading or market question and I'll analyze it with AI.\n\n"
        "<b>Commands:</b>\n"
        "/stock TICKER — Full stock analysis (tech + fundamentals + sentiment)\n"
        "/fundamentals TICKER — Quick fundamental metrics snapshot\n\n"
        "<b>Examples:</b>\n"
        "- Is EUR/USD bullish today?\n"
        "- Should I buy gold now?\n"
        "- What's the outlook for AAPL?\n"
        "- Technical analysis of Nifty\n"
        "- What is the market outlook for this week?",
        parse_mode="HTML",
    )


async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stock <TICKER> — comprehensive stock analysis."""
    global _subscribers
    chat_id = update.effective_chat.id
    if chat_id not in _subscribers:
        _subscribers.append(chat_id)
        save_subscribers(_subscribers)

    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /stock <TICKER>\n"
            "Example: /stock AAPL\n\n"
            "Get comprehensive analysis with technical data, fundamentals, "
            "news sentiment, and trading recommendations.",
            parse_mode="HTML",
        )
        return

    ticker = args[0].upper().strip()
    await update.message.chat.send_action(action="typing")

    question = " ".join(args[1:]) if len(args) > 1 else ""
    result = stock_analysis.comprehensive_analysis(ticker, question)

    if result:
        await update.message.reply_text(result, parse_mode="HTML")
    else:
        await update.message.reply_text(
            f"Sorry, could not analyze <b>{ticker}</b>. "
            f"Please check the ticker symbol and try again.",
            parse_mode="HTML",
        )


async def fundamentals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /fundamentals <TICKER> — quick fundamental metrics snapshot."""
    global _subscribers
    chat_id = update.effective_chat.id
    if chat_id not in _subscribers:
        _subscribers.append(chat_id)
        save_subscribers(_subscribers)

    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /fundamentals <TICKER>\n"
            "Example: /fundamentals MSFT\n\n"
            "Get P/E, EPS, dividend yield, market cap, and other key metrics.",
            parse_mode="HTML",
        )
        return

    ticker = args[0].upper().strip()
    await update.message.chat.send_action(action="typing")

    result = stock_analysis.quick_fundamentals(ticker)
    if result:
        await update.message.reply_text(result, parse_mode="HTML")
    else:
        await update.message.reply_text(
            f"Sorry, could not fetch fundamentals for <b>{ticker}</b>.",
            parse_mode="HTML",
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _subscribers
    chat_id = update.effective_chat.id
    if chat_id not in _subscribers:
        _subscribers.append(chat_id)
        save_subscribers(_subscribers)
        print(f"[SUBSCRIBE] Chat {chat_id} subscribed via /help")
    await update.message.reply_text(
        "Send any trading or market question. "
        "I will analyze it using AI and provide trading insights.\n\n"
        "Commands:\n"
        "/stock TICKER — Full stock analysis with AI recommendations\n"
        "/fundamentals TICKER — Quick fundamental metrics\n"
        "/subscribe — Get trading signals\n"
        "/unsubscribe — Stop signals\n"
        "/status — Check subscription"
    )


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _subscribers
    chat_id = update.effective_chat.id
    if chat_id in _subscribers:
        await update.message.reply_text("You are already subscribed to trading signals.")
        return
    _subscribers.append(chat_id)
    save_subscribers(_subscribers)
    print(f"[SUBSCRIBE] Chat {chat_id} subscribed via /subscribe")
    await update.message.reply_text(
        "✅ You are now subscribed to trading signals and market updates!\n\n"
        "You will receive:\n"
        "• Forex / crypto / stock trade signals\n"
        "• India NSE/BSE intraday alerts\n"
        "• BTC market updates & trade ideas\n"
        "• AI educational tips\n"
        "• Morning briefing & session summaries\n\n"
        "Use /unsubscribe to stop."
    )


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _subscribers
    chat_id = update.effective_chat.id
    if chat_id in _subscribers:
        _subscribers.remove(chat_id)
        save_subscribers(_subscribers)
        print(f"[UNSUBSCRIBE] Chat {chat_id} unsubscribed")
    await update.message.reply_text("You have been unsubscribed from trading signals.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    is_sub = chat_id in _subscribers
    await update.message.reply_text(
        f"🔔 Subscription status: {'✅ Active' if is_sub else '❌ Not subscribed'}\n\n"
        f"Chat ID: `{chat_id}`\n"
        f"Total subscribers: `{len(_subscribers)}`\n\n"
        f"Use /subscribe to start receiving signals.\n"
        f"Use /unsubscribe to stop.",
        parse_mode="Markdown",
    )


async def handle_user_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _subscribers
    try:
        chat_id = update.effective_chat.id
        if chat_id not in _subscribers:
            _subscribers.append(chat_id)
            save_subscribers(_subscribers)
            print(f"[SUBSCRIBE] Chat {chat_id} subscribed via message")

        question = update.message.text.strip()
        if not question:
            return

        await update.message.chat.send_action(action="typing")

        # Detect if this is a stock-specific question
        asset = detect_asset_in_text(question)
        is_stock_question = asset and asset in stock_analysis.STOCK_SYMBOLS

        if is_stock_question:
            # Route to comprehensive stock analysis
            result = stock_analysis.comprehensive_analysis(asset, question)
            if result:
                await update.message.reply_text(result, parse_mode="HTML")
                return
            # Fall through to generic analysis if stock analysis fails

        # Generic AI answer
        answer = ai_answer_question(question)

        msg_parts: list[str] = []
        if answer:
            msg_parts.append(
                f"<b>Question:</b> {escape(question)}\n\n"
                f"<b>AI Analysis:</b>\n{answer}"
            )
        else:
            msg_parts.append(
                "<b>AI analysis unavailable.</b>\n\n"
                "GROQ_API_KEY or OPENAI_API_KEY may not be configured. Please check server settings."
            )
            await update.message.reply_text("\n".join(msg_parts), parse_mode="HTML")
            return

        if asset and asset in TRADE_PAIRS:
            trade_setup = generate_asset_trade_setup(asset, question)
            if trade_setup:
                enhancement = ai_enhance_trade_suggestion(trade_setup, question)
                if enhancement:
                    trade_setup += f"\n\n<b>AI Improvement:</b> {enhancement}"
                msg_parts.append(f"\n\n{trade_setup}")

        await update.message.reply_text("\n".join(msg_parts), parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] handle_user_question: {e}")
        try:
            await update.message.reply_text(
                "Sorry, an error occurred while processing your question. Please check the bot logs."
            )
        except Exception:
            pass


def ensure_summary(article: dict[str, Any]) -> str:
    summary = article.get("description") or article.get("content") or ""
    summary = summary.strip()
    if summary:
        return escape(summary[:400])
    title = article.get("title") or ""
    if title:
        return escape(title[:400])
    return "No summary available."


def ai_translate(text: str, target_lang: str = "Bengali") -> str | None:
    if not GROQ_API_KEY or not text or not text.strip():
        return None
    prompt = (
        f"Translate this English text to {target_lang}. "
        "Keep ALL financial terms, numbers, percentages, currency codes (USD, EUR, XAU, etc.), "
        "and trading jargon (BUY, SELL, TP, SL, bullish, bearish, resistance, support, breakout, "
        "rally, decline) in English. Only translate surrounding explanatory words.\n\n"
        f"{text[:400]}"
    )
    return _groq_chat(prompt)


def translate_to_bengali(text: str) -> str | None:
    if not text or not text.strip():
        return None
    text = text[:500]

    ai_result = ai_translate(text)
    if ai_result:
        return ai_result

    try:
        from urllib.parse import quote
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=bn&dt=t&q={quote(text)}"
        with urlopen(url, timeout=10) as r:
            data = json.load(r)
        translated = data[0][0][0] if data and data[0] and data[0][0] else None
        if translated and translated.strip():
            return escape(translated)
    except Exception:
        pass

    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="en", target="bn")
        translated = translator.translate(text)
        if translated and translated.strip():
            return escape(translated)
    except Exception:
        pass

    return None


def format_stock_price_info(asset: str) -> str | None:
    try:
        import indian_market as im
        yf_map = {
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
            "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "HDFCBANK": "HDFCBANK.NS",
            "INFY": "INFY.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
            "BHARTI": "BHARTIARTL.NS", "WIPRO": "WIPRO.NS", "ITC": "ITC.NS",
            "LT": "LT.NS", "AXISBANK": "AXISBANK.NS", "KOTAKBANK": "KOTAKBANK.NS",
            "MARUTI": "MARUTI.NS", "TATAMOTORS": "TATAMOTORS.NS",
            "ASIANPAINT": "ASIANPAINT.NS", "HCLTECH": "HCLTECH.NS",
            "SUNPHARMA": "SUNPHARMA.NS", "BAJFINANCE": "BAJFINANCE.NS",
            "TITAN": "TITAN.NS", "NTPC": "NTPC.NS", "ONGC": "ONGC.NS",
            "POWERGRID": "POWERGRID.NS", "ULTRACEMCO": "ULTRACEMCO.NS",
            "TATASTEEL": "TATASTEEL.NS", "JSWSTEEL": "JSWSTEEL.NS",
            "HINDALCO": "HINDALCO.NS", "TECHM": "TECHM.NS",
            "COALINDIA": "COALINDIA.NS", "HINDUNILVR": "HINDUNILVR.NS",
            "BRITANNIA": "BRITANNIA.NS", "NESTLEIND": "NESTLEIND.NS",
            "M&M": "M&M.NS", "EICHERMOT": "EICHERMOT.NS",
            "HEROMOTOCO": "HEROMOTOCO.NS",
            "TATACONSUM": "TATACONSUM.NS", "DABUR": "DABUR.NS",
            "MARICO": "MARICO.NS", "HDFC": "HDFC.NS",
            "ICICIPRUDI": "ICICIPRUDI.NS", "HDFCLIFE": "HDFCLIFE.NS",
            "SBILIFE": "SBILIFE.NS", "TRENT": "TRENT.NS",
            "AVENUE": "AVENUE.NS", "PIDILITIND": "PIDILITIND.NS",
            "HAVELLS": "HAVELLS.NS", "SIEMENS": "SIEMENS.NS",
            "BEL": "BEL.NS", "BHEL": "BHEL.NS", "HAL": "HAL.NS",
            "IRFC": "IRFC.NS", "IREDA": "IREDA.NS", "SUZLON": "SUZLON.NS",
            "ADANIENT": "ADANIENT.NS", "ADANIPORTS": "ADANIPORTS.NS",
            "ADANIGREEN": "ADANIGREEN.NS", "ADANITRANS": "ADANITRANS.NS",
            "ADANIPOWER": "ADANIPOWER.NS",
            "HINDZINC": "HINDZINC.NS", "VEDL": "VEDL.NS",
            "IOC": "IOC.NS", "BPCL": "BPCL.NS", "GAIL": "GAIL.NS",
            "NATIONALUM": "NATIONALUM.NS",
            "ZOMATO": "ZOMATO.NS", "SWIGGY": "SWIGGY.NS",
            "PAYTM": "PAYTM.NS", "POLICYBZR": "POLICYBZR.NS",
            "NYKAA": "NYKAA.NS", "HDFCAMC": "HDFCAMC.NS",
            "GRASIM": "GRASIM.NS", "DIVISLAB": "DIVISLAB.NS",
            "CIPLA": "CIPLA.NS", "DRREDDY": "DRREDDY.NS",
            "APOLLOHOSP": "APOLLOHOSP.NS", "AUROPHARMA": "AUROPHARMA.NS",
            "TVSMOTOR": "TVSMOTOR.NS",
            "NIFTY": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK",
            "SP500": "^GSPC", "UK100": "^FTSE", "GER40": "^GDAXI",
            "JPN225": "^N225", "HK50": "^HSI", "AUS200": "^AXJO",
        }
        yf_symbol = yf_map.get(asset)
        if not yf_symbol:
            return None
        data = im.fetch_ticker_price(yf_symbol)
        if not data:
            return None
        sign = "+" if data["change"] >= 0 else ""
        return (f"<b>Live Price:</b> {data['price']} ({sign}{data['change']} | "
                f"{sign}{data['pct']}%)")
    except Exception:
        return None


def generate_trade_suggestion(article: dict[str, Any], asset: str) -> str:
    bias = infer_bias_signal(article)
    if bias:
        trade = format_trade_lines(bias)
        if trade:
            return trade

    text = normalize_text(article)
    score = sum(1 for word in POSITIVE_KEYWORDS if word in text)
    score -= sum(1 for word in NEGATIVE_KEYWORDS if word in text)

    if score > 0:
        direction = "BUY"
    elif score < 0:
        direction = "SELL"
    else:
        direction = "WATCH"

    return f"{direction} {asset} - Monitor for confirmation with proper risk management"


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


def fetch_latest_articles(query: str = FOREX_QUERY) -> list[dict[str, Any]]:
    provider = get_active_provider()

    if provider == "finnhub":
        categories = ["general", "forex", "crypto", "merger"]
        all_articles: list[dict] = []
        for cat in categories:
            try:
                articles = finnhub_fetch_news(cat)
                all_articles.extend(articles)
            except Exception:
                pass
        seen = set()
        unique = []
        for a in all_articles:
            k = article_key(a)
            if k and k not in seen:
                seen.add(k)
                unique.append(a)
        return unique

    url = build_newsapi_url(query) if provider == "newsapi" else build_newsdata_url(query)
    with urlopen(url, timeout=30) as response:
        payload = json.load(response)

    if provider == "newsapi":
        return load_newsapi_articles(payload)
    return load_newsdata_articles(payload)


def is_recent(article: dict[str, Any], max_age_hours: int = 48) -> bool:
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


def format_market_snapshot_block() -> str | None:
    try:
        import indian_market as im
        indian = im.format_market_snapshot()
        global_data = im.format_global_snapshot()
        parts = []
        if global_data:
            parts.append(global_data)
        if indian:
            parts.append(indian)
        return "\n\n".join(parts) if parts else None
    except Exception:
        return None


def _calc_rr(trade_text: str) -> str | None:
    for line in trade_text.split("\n"):
        if "Targets:" not in line:
            continue
        try:
            entry_line = ""
            lines = trade_text.split("\n")
            idx = lines.index(line)
            if idx > 0:
                entry_line = lines[idx - 1]
            entry_str = entry_line.split("@")[-1].strip() if "@" in entry_line else ""
            entry_str = _re.sub(r'[$₹,€£¥]', '', entry_str)
            if not entry_str:
                continue
            entry = float(entry_str)
            targets_str = line.split("Targets:")[1].split("|")[0].strip()
            sl_str = line.split("SL:")[1].strip() if "SL:" in line else ""
            targets_str = _re.sub(r'[$₹,€£¥]', '', targets_str)
            sl_str = _re.sub(r'[$₹,€£¥]', '', sl_str)
            tp_parts = targets_str.split("/")
            tp_reward = max(float(tp_parts[0].strip()), float(tp_parts[1].strip()))
            sl = float(sl_str) if sl_str else 0
            reward = abs(tp_reward - entry)
            risk = abs(sl - entry)
            if risk > 0:
                return f"R:R 1:{reward / risk:.1f}"
        except (ValueError, IndexError, AttributeError):
            pass
    return None


import re as _re


def _strip_md(text: str) -> str:
    return _re.sub(r'[*_`>#()\[\]\\<>]', '', text)


def _confidence_pct(level: str) -> int:
    return {"High": 78, "Medium": 62, "Low": 45}.get(level, 50)


_USD_QUOTE_PAIRS = frozenset({
    "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD",
    "XAU/USD", "XAG/USD",
    "BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD",
    "DOGE/USD", "DOT/USD", "AVAX/USD", "LINK/USD", "LTC/USD",
    "WTI", "BRENT", "US30", "US100", "SP500", "UK100", "GER40",
    "JPN225", "HK50", "AUS200",
    "USD/CHF", "USD/CAD", "USD/MXN", "USD/ZAR", "USD/TRY",
    "USD/SGD", "USD/HKD", "USD/CNY",
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "WMT", "JNJ", "PG", "XOM", "UNH", "HD", "BAC",
    "DIS", "NFLX", "ADBE", "CRM", "INTC", "AMD", "PYPL", "UBER",
    "NKE", "BA", "COIN", "SNAP", "SQ", "PLTR", "RBLX", "MCD",
    "SBUX", "NIO", "RIVN",
})

_STOCK_ASSETS = frozenset({
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTI",
    "WIPRO", "ITC", "LT", "AXISBANK", "KOTAKBANK", "MARUTI", "TATAMOTORS",
    "ASIANPAINT", "HCLTECH", "SUNPHARMA", "BAJFINANCE", "TITAN", "NTPC",
    "ONGC", "POWERGRID", "ULTRACEMCO", "TATASTEEL", "JSWSTEEL", "HINDALCO",
    "TECHM", "COALINDIA", "HINDUNILVR", "BRITANNIA", "NESTLEIND", "M&M",
    "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "TATACONSUM", "DABUR", "MARICO",
    "HDFC", "ICICIPRUDI", "HDFCLIFE", "SBILIFE", "TRENT", "AVENUE",
    "PIDILITIND", "HAVELLS", "SIEMENS", "BEL", "BHEL", "HAL",
    "IRFC", "IREDA", "SUZLON", "ADANIENT", "ADANIPORTS",
    "ADANIGREEN", "ADANITRANS", "ADANIPOWER", "HINDZINC", "VEDL",
    "IOC", "BPCL", "GAIL", "NATIONALUM", "ZOMATO", "SWIGGY",
    "PAYTM", "POLICYBZR", "NYKAA", "HDFCAMC", "GRASIM",
    "DIVISLAB", "CIPLA", "DRREDDY", "APOLLOHOSP", "AUROPHARMA", "TVSMOTOR",
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "WMT", "JNJ", "PG", "XOM", "UNH", "HD", "BAC",
    "DIS", "NFLX", "ADBE", "CRM", "INTC", "AMD", "PYPL", "UBER",
    "NKE", "BA", "COIN", "SNAP", "SQ", "PLTR", "RBLX", "MCD", "SBUX", "NIO", "RIVN",
})


def _price_str(val: float, pair: str) -> str:
    if pair in _USD_QUOTE_PAIRS:
        if abs(val) >= 1000:
            return f"${val:,.2f}"
        elif abs(val) >= 1:
            return f"${val:.2f}"
        return f"${val:.4f}"
    if abs(val) >= 1000:
        return f"{val:,.2f}"
    elif abs(val) >= 1:
        return f"{val:.2f}"
    return f"{val:.4f}"


def _calc_percentage_levels(price: float, is_buy: bool,
                            tp1_pct: float = 1.0, tp2_pct: float = 2.0,
                            sl_pct: float = 0.5) -> tuple[float, float, float, float]:
    entry = round(price, 2)
    tp1 = round(price * (1 + tp1_pct / 100) if is_buy else price * (1 - tp1_pct / 100), 2)
    tp2 = round(price * (1 + tp2_pct / 100) if is_buy else price * (1 - tp2_pct / 100), 2)
    sl  = round(price * (1 - sl_pct / 100) if is_buy else price * (1 + sl_pct / 100), 2)
    return entry, tp1, tp2, sl


def format_professional_signal(
    pair: str, direction: str, entry: float, tp1: float, tp2: float, sl: float,
    confidence_pct: int, reason: str, timeframe: str = "H1",
) -> str:
    dir_icon = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
    pips_sl = _price_str(abs(round(sl - entry, 4)), pair)
    pips_tp1 = _price_str(abs(round(tp1 - entry, 4)), pair)
    pips_tp2 = _price_str(abs(round(tp2 - entry, 4)), pair)
    risk = abs(sl - entry)
    reward = abs(tp2 - entry)
    rr = f"{reward / risk:.1f}" if risk > 0 else "?"
    name = INSTRUMENT_NAMES.get(pair, pair)
    lines = [
        "📡 *TradeSignal Pro* | AI Signal",
        "",
        f"*{pair}* · {dir_icon} · {timeframe}",
        f"_{name}_",
        "",
        "━━━━━━━━━━━━━━",
        f"📌 Entry:      {_price_str(entry, pair)}",
        f"🛑 Stop Loss:  {_price_str(sl, pair)}  (-{pips_sl})",
        f"🎯 TP 1:       {_price_str(tp1, pair)} (+{pips_tp1})",
        f"🎯 TP 2:       {_price_str(tp2, pair)} (+{pips_tp2})",
        f"⚖️ Risk:Reward: 1 : {rr}",
        "━━━━━━━━━━━━━━",
        f"🤖 AI Confidence: {confidence_pct}%",
        "",
        f"📝 Reason: {_strip_md(reason[:300])}",
        "",
        "⚠️ Not financial advice. Trade at your own risk.",
    ]
    return "\n".join(lines)


def format_high_impact_alert(
    title: str, asset: str, direction: str, confidence_pct: int,
    analysis: str,
) -> str:
    """Template 2 — High-impact breaking news alert."""
    dir_icon = (
        "🟢 Bullish" if direction == "Bullish"
        else "🔴 Bearish" if direction == "Bearish"
        else "🟡 Neutral"
    )
    ist_now  = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    date_str = ist_now.strftime("%d %b %Y, %I:%M %p IST")
    return (
        f"📰 *BREAKING NEWS ALERT*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*{_strip_md(title[:80])}*\n"
        f"🌍 *Asset:* {asset}  ·  {date_str}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💥 *Impact:* {dir_icon} for *{asset}*\n"
        f"🤖 *Confidence:* {confidence_pct}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Quick Analysis:*\n"
        f"{_strip_md(analysis[:350])}\n\n"
        f"🔖 #{asset}  #highimpact  #breakingnews  #news"
    )


def format_nse_signal(
    index: str, option_type: str, strike: str, direction: str,
    entry_low: float, entry_high: float, sl: float, tp1: float, tp2: float,
    spot: float, pcr: float | None, reason: str, bengali: str | None = None,
    expiry: str = "Weekly",
) -> str:
    dir_emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
    sl_pct = round(abs(sl - entry_low) / entry_low * 100)
    tp1_pct = round(abs(tp1 - entry_low) / entry_low * 100)
    tp2_pct = round(abs(tp2 - entry_low) / entry_low * 100)
    pcr_str = ""
    if pcr is not None:
        pcr_label = "bullish" if pcr > 1.2 else ("bearish" if pcr < 0.8 else "neutral")
        pcr_str = f"📊 PCR:             {pcr:.2f} ({pcr_label})"
    expiry_label = f"Weekly Expiry · {expiry}"
    lines = [
        f"🇮🇳 *{index}* · {option_type} {strike} | {dir_emoji}",
        f"_{expiry_label} · Options_",
        "",
        "━━━━━━━━━━━━━━",
        f"📌 Entry (premium): ₹{entry_low}–{entry_high}",
        f"🛑 Stop Loss:       ₹{sl}  (-{sl_pct}%)",
        f"🎯 Target 1:        ₹{tp1}  (+{tp1_pct}%)",
        f"🎯 Target 2:        ₹{tp2}  (+{tp2_pct}%)",
        f"📍 Spot ref:        {spot}",
    ]
    if pcr_str:
        lines.append(pcr_str)
    lines.append("━━━━━━━━━━━━━━")
    lines.append(f"📝 Reason: {_strip_md(reason[:300])}")
    if bengali:
        lines.append("")
        lines.append(f"🇧🇩 বাংলা: {bengali[:150]}")
    lines.append("")
    lines.append(f"🔖 #{index} #options #NSE #India #{expiry}")
    return "\n".join(lines)


def format_calendar_alert_md(events: list[dict]) -> str | None:
    if not events:
        return None
    lines = [
        "📰 *ECONOMIC CALENDAR*",
        "━━━━━━━━━━━━━━",
    ]
    now = datetime.now(timezone.utc)
    for ev in events:
        dt = ev.get("datetime")
        if not dt:
            continue
        mins_until = int((dt - now).total_seconds() / 60)
        if mins_until <= 0:
            time_str = "NOW"
        elif mins_until < 60:
            time_str = f"in {mins_until}m"
        else:
            hours = mins_until // 60
            mins_left = mins_until % 60
            time_str = f"in {hours}h {mins_left}m" if mins_left else f"in {hours}h"
        icon = "🔴" if ev["impact"] == "high" else "🟡"
        title = _strip_md(ev["title"])
        country = ev["country"]
        forecast = _strip_md(ev.get("forecast", "N/A"))
        previous = _strip_md(ev.get("previous", "N/A"))
        lines.append(f"{icon} *{country}* — {title}")
        lines.append(f"   ⏰ {time_str} | 📈 Fcst: {forecast} | 📉 Prev: {previous}")
    if len(lines) == 2:
        return None
    lines.append("")
    lines.append("🔖 #calendar #forex #economic")
    return "\n".join(lines)


def _finnhub_sentiment_line(asset: str) -> str:
    """Add Finnhub sentiment enrichment line if data available."""
    try:
        fh = finnhub_enrich_with_sentiment(asset)
        if fh:
            return f"📊 *Sentiment:* {_strip_md(fh)}"
    except Exception:
        pass
    return ""


# ── Daily Style Theme System ─────────────────────────────────────────────
_WEEKLY_THEMES = [
    {"header": "🚀", "accent": "⚡", "sep": "▬" * 20, "name": "Monday Momentum"},
    {"header": "🔥", "accent": "💥", "sep": "═" * 20, "name": "Tuesday Trade"},
    {"header": "🎯", "accent": "📊", "sep": "▔" * 20, "name": "Wednesday Watch"},
    {"header": "💎", "accent": "🌟", "sep": "✦" * 20, "name": "Thursday Signals"},
    {"header": "🏆", "accent": "💰", "sep": "▬" * 20, "name": "Friday Forecast"},
    {"header": "📡", "accent": "📈", "sep": "─" * 20, "name": "Saturday Scan"},
    {"header": "🌐", "accent": "🔮", "sep": "━" * 20, "name": "Sunday Summary"},
]
_style_counter: dict[str, int] = {"day": -1}


def _get_today_theme() -> dict:
    today = datetime.now(timezone.utc).weekday()
    if _style_counter["day"] != today:
        _style_counter["day"] = today
    return _WEEKLY_THEMES[today]


def _style_header(title: str, theme: dict) -> str:
    return f"{theme['header']} *{title}*  {theme['header']}"


def _style_sep(theme: dict) -> str:
    return theme["sep"]


def _style_label(k: str, v: str, w: int = 14) -> str:
    return f"`{k:<{w}}` {v}"


def format_forex_message(article: dict[str, Any]) -> str:
    """Template 1 — Forex/Crypto trade signal or news alert."""
    title     = _strip_md(article.get("title") or "Market Update")
    source    = _strip_md(article.get("source_name") or "")
    published = _strip_md(article.get("pubDate") or "")
    link      = article.get("link") or ""

    asset  = identify_asset(article)
    bias   = infer_bias_signal(article)
    prices = fetch_current_prices()
    text_body = normalize_text(article)
    direction, confidence = "Neutral", "Low"
    if bias:
        direction, confidence = compute_confidence(text_body)

    pairs = TRADE_PAIRS.get(asset) if asset else None

    # ── Build trade signal card (Template 1) if we have a clear bias + pair ──
    if bias and pairs:
        parts = bias.split()
        if len(parts) == 2:
            direction_str, asset_sym = parts[0], parts[1]
            is_bullish = direction_str == "Bullish"
            pair, multiplier, pip_size = pairs[0]
            price = prices.get(pair)
            if price:
                is_buy = (is_bullish == (multiplier > 0))
                direction_label = "BUY" if is_buy else "SELL"
                dir_icon  = "🟢 BUY" if is_buy else "🔴 SELL"
                e  = round(price, 4)
                t1 = round(price + 30 * pip_size if is_buy else price - 30 * pip_size, 4)
                t2 = round(price + 50 * pip_size if is_buy else price - 50 * pip_size, 4)
                s  = round(price - 20 * pip_size if is_buy else price + 20 * pip_size, 4)
                reward = abs(t2 - e)
                risk   = abs(s - e)
                rr_str = f"{reward / risk:.1f}" if risk > 0 else "?"
                conf_pct = _confidence_pct(confidence)
                ai_reason = _strip_md(ai_analyze_news(article) or title[:200])
                inst_name = INSTRUMENT_NAMES.get(pair, pair)
                log_signal(pair, direction_label, e, t1, t2, s, "forex")
                theme = _get_today_theme()
                sep = _style_sep(theme)
                lines = [
                    "📡 *TradeSignal Pro* | AI Signal",
                    "",
                    _style_header(f"TradeSignal Pro — {dir_icon}", theme),
                    f"",
                    f"`Asset      ` *{pair}*   _{inst_name}_",
                    f"`Timeframe  ` H1  ·  {theme['accent']} {theme['name']}",
                    f"",
                    f"`{sep}`",
                    _style_label("Entry",      _price_str(e, pair)),
                    _style_label("Stop Loss",  f"{_price_str(s, pair)}  (-{_price_str(abs(s-e), pair)})"),
                    _style_label("TP 1",       f"{_price_str(t1, pair)}  (+{_price_str(abs(t1-e), pair)})"),
                    _style_label("TP 2",       f"{_price_str(t2, pair)}  (+{_price_str(abs(t2-e), pair)})"),
                    _style_label("Risk:Reward", f"1 : {rr_str}"),
                    f"`{sep}`",
                    _style_label("AI Confidence", f"{conf_pct}%"),
                    f"",
                    f"📝 {ai_reason[:280]}",
                    f"",
                    _finnhub_sentiment_line(asset).replace("*", ""),
                    f"",
                    f"`{sep}`",
                    f"🧠 *AI Learning Assistant*",
                    f"",
                    f"📘 *Beginner:* {dir_icon} means we expect {pair} to {'rise' if is_buy else 'fall'}. "
                    f"Entry at {_price_str(e, pair)} opens the trade. "
                    f"SL ({_price_str(s, pair)}) caps losses. TP1/TP2 lock profits.",
                    f"",
                    f"📙 *Intermediate:* Price {_price_str(e, pair)} with "
                    f"{'bullish' if is_buy else 'bearish'} news bias. "
                    f"Risk {_price_str(abs(s-e), pair)} to target "
                    f"{_price_str(abs(t1-e), pair)} (TP1) / {_price_str(abs(t2-e), pair)} (TP2). "
                    f"R:R 1:{rr_str}.",
                    f"",
                    f"📈 *Experienced:* {'Resistance' if not is_buy else 'Support'} cluster near "
                    f"{_price_str(t1, pair)}. Watch for volume confirmation. "
                    f"Scale 50% at TP1, trail SL to entry.",
                    f"",
                    f"🔖 #{asset_sym}  #forex  #signal  #{'long' if is_buy else 'short'}",
                    f"⚠️ _Not financial advice._",
                ]
                if link:
                    lines.append(f"🔗 {link}")
                return "\n".join(lines)

    # ── Fallback: news alert (Template 2 style) ──────────────────────────────
    ai_analysis = _strip_md(ai_analyze_news(article) or ensure_summary(article)[:300])
    dir_icon_fb = (
        "🟢 Bullish" if direction == "Bullish"
        else "🔴 Bearish" if direction == "Bearish"
        else "🟡 Neutral"
    )
    conf_pct_fb = _confidence_pct(confidence)
    ist_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y")
    theme = _get_today_theme()
    sep = _style_sep(theme)
    lines = [
        _style_header(f"Forex / Market Update", theme),
        f"`{sep}`",
        f"*{title[:80]}*",
        f"",
        _style_label("Asset",   asset),
        _style_label("Date",    ist_str),
        _style_label("Impact",  dir_icon_fb),
        _style_label("AI Conf.", f"{conf_pct_fb}%"),
        f"`{sep}`",
        f"📊 *Analysis:*",
        f"{ai_analysis[:350]}",
        f"",
        _finnhub_sentiment_line(asset),
        f"",
        f"🔖 #{asset}  #forex  #news",
    ]
    if source:
        lines.append(f"📰 _{source}  |  {published}_")
    if link:
        lines.append(f"🔗 {link}")
    return "\n".join(lines)


def format_india_message(article: dict[str, Any]) -> str:
    """Template 3 — India/NSE market signal."""
    title     = _strip_md(article.get("title") or "India Market Update")
    source    = _strip_md(article.get("source_name") or "")
    published = _strip_md(article.get("pubDate") or "")

    asset  = identify_asset(article)
    bias   = infer_bias_signal(article)
    prices = fetch_current_prices()
    text_body = normalize_text(article)
    direction, confidence = "Neutral", "Low"
    if bias:
        direction, confidence = compute_confidence(text_body)

    dir_icon = (
        "🟢 BUY"  if direction == "Bullish"
        else "🔴 SELL" if direction == "Bearish"
        else "➖ WATCH"
    )
    conf_pct   = _confidence_pct(confidence)
    ai_insight = _strip_md(ai_analyze_news(article) or ensure_summary(article)[:300])
    inst_name  = INSTRUMENT_NAMES.get(asset, asset)

    # Try to compute price levels
    pairs_list = TRADE_PAIRS.get(asset)
    entry_str = sl_str = tp1_str = tp2_str = "Monitor levels"
    sl_diff = tp1_diff = tp2_diff = ""
    is_buy = False
    e = t1 = t2 = s = 0.0
    if pairs_list:
        pair, multiplier, pip_size = pairs_list[0]
        price = prices.get(pair)
        if price:
            is_buy = (direction == "Bullish") == (multiplier > 0)
            if asset in _STOCK_ASSETS:
                e, t1, t2, s = _calc_percentage_levels(price, is_buy)
            else:
                e = round(price, 2)
                t1 = round(price + 30 * pip_size if is_buy else price - 30 * pip_size, 2)
                t2 = round(price + 50 * pip_size if is_buy else price - 50 * pip_size, 2)
                s  = round(price - 20 * pip_size if is_buy else price + 20 * pip_size, 2)
            entry_str = _price_str(e, pair)
            sl_str    = _price_str(s, pair)
            tp1_str   = _price_str(t1, pair)
            tp2_str   = _price_str(t2, pair)
            sl_diff   = _price_str(abs(s - e), pair)
            tp1_diff  = _price_str(abs(t1 - e), pair)
            tp2_diff  = _price_str(abs(t2 - e), pair)
            log_signal(pair, "BUY" if is_buy else "SELL", e, t1, t2, s, "india")

    live_price = format_stock_price_info(asset)
    theme = _get_today_theme()
    sep = _style_sep(theme)
    lines = [
        f"🔥 *NSE / BSE Signal* | SIGNAL",
        "",
        _style_header(f"NSE / BSE Signal — {dir_icon}", theme),
        f"`{sep}`",
        f"`Asset      ` *{asset}*  ·  {inst_name}",
        f"`{theme['name']}` _{title[:80]}_",
        f"",
    ]
    if live_price:
        lines.append(live_price)
        lines.append("")
    if pairs_list and price:
        entry_icon = "🟢 BUY" if is_buy else "🔴 SELL"
        if asset in _STOCK_ASSETS:
            pct_tp1 = abs(t1 - e) / e * 100
            pct_tp2 = abs(t2 - e) / e * 100
            pct_sl = abs(s - e) / e * 100
            rr = abs(t2 - e) / abs(s - e) if abs(s - e) > 0 else 0
            lines.extend([
                f"`{sep}`",
                _style_label("Entry",      entry_str),
                _style_label("Stop Loss",  f"{sl_str}  (-{pct_sl:.1f}%)"),
                _style_label("TP 1",       f"{tp1_str}  (+{pct_tp1:.1f}%)"),
                _style_label("TP 2",       f"{tp2_str}  (+{pct_tp2:.1f}%)"),
                _style_label("R:R",        f"1:{rr:.1f}"),
                _style_label("AI Confidence", f"{conf_pct}%"),
                f"`{sep}`",
                f"📊 *Analysis:* {ai_insight[:300]}",
                f"",
                f"`{sep}`",
                f"🧠 *AI Learning Assistant*",
                f"",
                f"📘 *Beginner:* {entry_icon} means we expect the price to {'rise' if is_buy else 'fall'}. "
                f"Entry {entry_str}, SL {sl_str} limits risk, "
                f"TP1 {tp1_str} / TP2 {tp2_str} lock profits.",
                f"",
                f"📙 *Intermediate:* {'Bullish' if is_buy else 'Bearish'} news bias. "
                f"Entry {entry_str}, {pct_sl:.1f}% risk for {pct_tp2:.1f}% reward (R:R 1:{rr:.1f}). "
                f"Scale 50% at TP1, trail SL to entry.",
                f"",
                f"📈 *Experienced:* Key level at {entry_str}. "
                f"{'Resistance' if not is_buy else 'Support'} near {tp1_str}. "
                f"Volume confirmation needed.",
                f"",
                f"🔖 #{asset}  #NSE  #BSE  #India  #{'long' if is_buy else 'short'}",
                f"⚠️ _Not financial advice._",
            ])
        else:
            lines.extend([
                f"`{sep}`",
                _style_label("Entry zone", entry_str),
                _style_label("Stop loss",  sl_str + (f"  (-{sl_diff})" if sl_diff else "")),
                _style_label("Target 1",   tp1_str + (f"  (+{tp1_diff})" if tp1_diff else "")),
                _style_label("Target 2",   tp2_str + (f"  (+{tp2_diff})" if tp2_diff else "")),
                _style_label("Confidence", f"{conf_pct}%"),
                f"`{sep}`",
                f"📊 *Analysis:* {ai_insight[:300]}",
                f"",
                f"🔖 #{asset}  #NSE  #BSE  #India  #news",
            ])
    else:
        lines.extend([
            f"`{sep}`",
            f"📊 *Analysis:* {ai_insight[:300]}",
            f"",
            f"🔖 #{asset}  #NSE  #BSE  #India  #news",
        ])
    if source:
        lines.append(f"📰 _{source}  |  {published}_")
    return "\n".join(lines)


def format_intraday_message(article: dict[str, Any]) -> str:
    """Template 3 variant — India intraday stock signal."""
    title     = _strip_md(article.get("title") or "Intraday Update")
    source    = _strip_md(article.get("source_name") or "")
    published = _strip_md(article.get("pubDate") or "")

    asset     = identify_asset(article)
    inst_name = INSTRUMENT_NAMES.get(asset, asset)
    bias      = infer_bias_signal(article)
    prices    = fetch_current_prices()
    text_body = normalize_text(article)
    direction, confidence = "Neutral", "Low"
    if bias:
        direction, confidence = compute_confidence(text_body)

    dir_icon = (
        "🟢 BUY"  if direction == "Bullish"
        else "🔴 SELL" if direction == "Bearish"
        else "➖ WATCH"
    )
    conf_pct   = _confidence_pct(confidence)
    ai_insight = _strip_md(ai_analyze_news(article) or ensure_summary(article)[:300])

    exchange_tag = "NSE" if asset in {
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTI",
        "WIPRO", "ITC", "LT", "AXISBANK", "KOTAKBANK", "MARUTI", "TATAMOTORS",
        "ASIANPAINT", "HCLTECH", "SUNPHARMA", "BAJFINANCE", "TITAN", "NTPC",
        "ONGC", "POWERGRID", "ULTRACEMCO", "NIFTY", "SENSEX", "BANKNIFTY",
        "TATASTEEL", "JSWSTEEL", "HINDALCO", "TECHM", "COALINDIA",
        "HINDUNILVR", "BRITANNIA", "NESTLEIND", "M&M", "EICHERMOT",
        "HEROMOTOCO", "BAJAJ-AUTO", "TATACONSUM", "DABUR", "MARICO",
        "HDFC", "ICICIPRUDI", "HDFCLIFE", "SBILIFE", "TRENT", "AVENUE",
        "PIDILITIND", "HAVELLS", "SIEMENS", "BEL", "BHEL", "HAL",
        "IRFC", "IREDA", "SUZLON", "ADANIENT", "ADANIPORTS",
        "ADANIGREEN", "ADANITRANS", "ADANIPOWER", "HINDZINC", "VEDL",
        "IOC", "BPCL", "GAIL", "NATIONALUM", "ZOMATO", "SWIGGY",
        "PAYTM", "POLICYBZR", "NYKAA", "HDFCAMC", "GRASIM",
        "DIVISLAB", "CIPLA", "DRREDDY", "APOLLOHOSP", "AUROPHARMA",
        "TVSMOTOR",
    } else "NYSE/NASDAQ" if asset in {
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "JPM", "V", "WMT", "JNJ", "PG", "XOM", "UNH", "HD", "BAC",
        "DIS", "NFLX", "ADBE", "CRM", "INTC", "AMD", "PYPL", "UBER",
        "NKE", "BA", "COIN", "SNAP", "SQ", "PLTR", "RBLX", "MCD",
        "SBUX", "NIO", "RIVN",
    } else "BSE/NSE"

    pairs_list = TRADE_PAIRS.get(asset)
    entry_str = sl_str = tp1_str = tp2_str = "Monitor levels"
    sl_diff = tp1_diff = tp2_diff = ""
    is_buy = False
    e = t1 = t2 = s = 0.0
    if pairs_list:
        pair, multiplier, pip_size = pairs_list[0]
        price = prices.get(pair)
        if price:
            is_buy = (direction == "Bullish") == (multiplier > 0)
            if asset in _STOCK_ASSETS:
                e, t1, t2, s = _calc_percentage_levels(price, is_buy)
            else:
                e = round(price, 2)
                t1 = round(price + 30 * pip_size if is_buy else price - 30 * pip_size, 2)
                t2 = round(price + 50 * pip_size if is_buy else price - 50 * pip_size, 2)
                s  = round(price - 20 * pip_size if is_buy else price + 20 * pip_size, 2)
            entry_str = _price_str(e, pair)
            sl_str    = _price_str(s, pair)
            tp1_str   = _price_str(t1, pair)
            tp2_str   = _price_str(t2, pair)
            sl_diff   = _price_str(abs(s - e), pair)
            tp1_diff  = _price_str(abs(t1 - e), pair)
            tp2_diff  = _price_str(abs(t2 - e), pair)
            log_signal(pair, "BUY" if is_buy else "SELL", e, t1, t2, s, "intraday")

    live_price = format_stock_price_info(asset)
    theme = _get_today_theme()
    sep = _style_sep(theme)
    lines = [
        f"🔥 *Intraday Signal* | SIGNAL",
        "",
        _style_header(f"Intraday Signal — {exchange_tag}", theme),
        f"`{sep}`",
        f"`Asset      ` *{asset}*  ·  {inst_name}  |  {dir_icon}",
        f"`{theme['name']}` _{title[:80]}_",
        f"",
    ]
    if live_price:
        lines.append(live_price)
        lines.append("")
    if pairs_list and price:
        entry_icon = "🟢 BUY" if is_buy else "🔴 SELL"
        if asset in _STOCK_ASSETS:
            pct_tp1 = abs(t1 - e) / e * 100
            pct_tp2 = abs(t2 - e) / e * 100
            pct_sl = abs(s - e) / e * 100
            rr = abs(t2 - e) / abs(s - e) if abs(s - e) > 0 else 0
            lines.extend([
                f"`{sep}`",
                _style_label("Entry",      entry_str),
                _style_label("Stop Loss",  f"{sl_str}  (-{pct_sl:.1f}%)"),
                _style_label("TP 1",       f"{tp1_str}  (+{pct_tp1:.1f}%)"),
                _style_label("TP 2",       f"{tp2_str}  (+{pct_tp2:.1f}%)"),
                _style_label("R:R",        f"1:{rr:.1f}"),
                _style_label("AI Confidence", f"{conf_pct}%"),
                f"`{sep}`",
                f"📊 *Analysis:* {ai_insight[:300]}",
                f"",
                f"`{sep}`",
                f"🧠 *AI Learning Assistant*",
                f"",
                f"📘 *Beginner:* {entry_icon} means we expect the stock to {'rise' if is_buy else 'fall'}. "
                f"Entry {entry_str}, SL {sl_str} limits losses, "
                f"TP1 {tp1_str} / TP2 {tp2_str} for profit taking.",
                f"",
                f"📙 *Intermediate:* {'Bullish' if is_buy else 'Bearish'} bias on {asset}. "
                f"Entry {entry_str}, {pct_sl:.1f}% risk for {pct_tp2:.1f}% reward (R:R 1:{rr:.1f}). "
                f"Book 50% at TP1, trail SL to breakeven.",
                f"",
                f"📈 *Experienced:* Price action at {entry_str}. "
                f"{'Resistance' if not is_buy else 'Support'} near {tp1_str}. "
                f"Volume confirmation key. Size based on volatility.",
                f"",
                f"🔖 #{asset}  #intraday  #{exchange_tag}  #{'long' if is_buy else 'short'}",
                f"⚠️ _Not financial advice._",
            ])
        else:
            lines.extend([
                f"`{sep}`",
                _style_label("Entry zone", entry_str),
                _style_label("Stop loss",  sl_str + (f"  (-{sl_diff})" if sl_diff else "")),
                _style_label("Target 1",   tp1_str + (f"  (+{tp1_diff})" if tp1_diff else "")),
                _style_label("Target 2",   tp2_str + (f"  (+{tp2_diff})" if tp2_diff else "")),
                _style_label("Confidence", f"{conf_pct}%"),
                f"`{sep}`",
                f"📊 *Analysis:* {ai_insight[:300]}",
                f"",
                f"🔖 #{asset}  #intraday  #{exchange_tag}  #India",
            ])
    else:
        lines.extend([
            f"`{sep}`",
            f"📊 *Analysis:* {ai_insight[:300]}",
            f"",
            f"🔖 #{asset}  #intraday  #{exchange_tag}  #India",
        ])
    if source:
        lines.append(f"📰 _{source}  |  {published}_")
    return "\n".join(lines)


async def broadcast(bot: Bot, text: str, parse_mode: str = "Markdown", disable_web_page_preview: bool = True) -> int:
    global _subscribers
    sent = 0
    targets: list[int | str] = list(_subscribers)
    if TELEGRAM_CHAT_ID:
        targets.insert(0, TELEGRAM_CHAT_ID)

    seen_cids: set[int | str] = set()
    for cid in targets:
        if cid in seen_cids:
            continue
        seen_cids.add(cid)
        try:
            await bot.send_message(
                chat_id=cid,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            sent += 1
        except Exception as exc:
            err_str = str(exc).lower()
            if "blocked" in err_str or "forbidden" in err_str or "chat not found" in err_str:
                if isinstance(cid, int) and cid in _subscribers:
                    _subscribers.remove(cid)
                    save_subscribers(_subscribers)
                    print(f"[BROADCAST] Removed blocked/subscriber {cid}")
            else:
                print(f"[BROADCAST] Failed to send via primary bot to {cid}: {exc}")
    return sent


async def send_category_article(
    bot: Bot,
    articles: list[dict[str, Any]],
    seen_keys: set[str],
    category_prefix: str,
    format_func: Any,
) -> int:
    for article in articles:
        key = article_key(article)
        if not key:
            continue
        full_key = f"{category_prefix}:{key}"
        if full_key in seen_keys:
            continue
        if not is_recent(article):
            continue

        text = format_func(article)
        if not text:
            continue

        await broadcast(bot, text)
        seen_keys.add(full_key)
        save_seen_keys(seen_keys)
        return 1
    return 0


async def send_options_suggestion(bot: Bot, seen_keys: set[str]) -> int:
    import indian_market as im

    nifty_suggestion = im.format_nifty_options_suggestion()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")

    sent = 0

    if nifty_suggestion:
        key = f"option:nifty_{today}"
        if key not in seen_keys:
            await broadcast(bot, nifty_suggestion, parse_mode="HTML")
            seen_keys.add(key)
            save_seen_keys(seen_keys)
            sent += 1

    sensex_suggestion = im.format_sensex_options_suggestion()
    if sensex_suggestion:
        key = f"option:sensex_{today}"
        if key not in seen_keys:
            await broadcast(bot, sensex_suggestion, parse_mode="HTML")
            seen_keys.add(key)
            save_seen_keys(seen_keys)
            sent += 1

    return sent


async def send_institutional_signals(bot: Bot, seen_keys: set[str]) -> int:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"institutional_signals:{today}"
    if key in seen_keys:
        return 0
    if not MASSIVE_API_KEY:
        return 0

    sent = 0
    try:
        block = massive_data.format_institutional_signal_block()
        if block:
            await broadcast(bot, block)
            seen_keys.add(key)
            save_seen_keys(seen_keys)
            sent += 1
            print("[INSTITUTIONAL SIGNALS] Sent consensus ratings")

        commodity_block = massive_data.format_commodity_signal_block()
        if commodity_block:
            await broadcast(bot, commodity_block)
            sent += 1
            print("[COMMODITY WATCH] Sent commodity prices")

        us_block = massive_data.format_us_market_block()
        if us_block:
            await broadcast(bot, us_block)
            sent += 1
            print("[US MARKET DATA] Sent indices & yields")
    except Exception as e:
        print(f"[ERROR] Institutional signals: {e}")

    return sent


async def run_worker_cycle(bot: Bot, seen_keys: set[str]) -> int:
    total_sent = 0

    forex_articles = fetch_latest_articles(FOREX_QUERY)
    total_sent += await send_category_article(
        bot, forex_articles, seen_keys,
        "forex", format_forex_message,
    )

    india_articles = fetch_latest_articles(INDIA_MARKET_QUERY)
    total_sent += await send_category_article(
        bot, india_articles, seen_keys,
        "india", format_india_message,
    )

    intraday_articles = fetch_latest_articles(INTRADAY_STOCK_QUERY)
    total_sent += await send_category_article(
        bot, intraday_articles, seen_keys,
        "intraday", format_intraday_message,
    )

    total_sent += await send_options_suggestion(bot, seen_keys)
    total_sent += await send_institutional_signals(bot, seen_keys)

    return total_sent


def validate_config() -> list[str]:
    missing = []
    bt = os.environ.get("BOT_TOKEN") or os.environ.get("BOT_TOKEN3") or ""
    if not bt:
        missing.append("BOT_TOKEN / BOT_TOKEN3")
    ci = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID3") or ""
    if not ci:
        missing.append("TELEGRAM_CHAT_ID / TELEGRAM_CHAT_ID3")

    provider = get_active_provider()
    if provider == "newsapi":
        if not NEWS_API_KEY:
            missing.append("NEWS_API_KEY")
    elif provider == "finnhub":
        if not FINNHUB_API_KEY:
            missing.append("FINNHUB_API_KEY")
    elif not NEWSDATA_API_KEY:
        missing.append("NEWSDATA_API_KEY")

    return missing


async def crypto_screener_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic crypto pump/dump screening job."""
    try:
        sent = crypto_screener.run_scan_cycle()
        if sent:
            print(f"[CRYPTO SCREENER] Sent {sent} pump alert(s).")
    except Exception as exc:
        print(f"[CRYPTO SCREENER] Scan cycle failed: {exc}")


async def news_broadcast_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    global _seen_keys
    try:
        sent_count = await run_worker_cycle(context.bot, _seen_keys)
        if sent_count:
            print(f"Worker cycle complete. Sent {sent_count} message(s).")
    except Exception as exc:
        print(f"[ERROR] Worker cycle failed: {exc}")


async def high_impact_check_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    global _seen_keys
    try:
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
            if full_key in _seen_keys:
                continue

            asset = identify_asset(article)
            text = normalize_text(article)
            bias = infer_bias_signal(article)
            direction, confidence = "Neutral", "Low"
            if bias:
                direction, confidence = compute_confidence(text)
            ai_analysis = ai_analyze_news(article) or ""
            conf_pct = _confidence_pct(confidence)
            now_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y")
            text_msg = format_high_impact_alert(
                title=article.get("title", "Breaking News"),
                asset=asset,
                direction=direction,
                confidence_pct=conf_pct,
                analysis=ai_analysis or "Significant market-moving event detected.",
            )
            await broadcast(context.bot, text_msg)
            _seen_keys.add(full_key)
            save_seen_keys(_seen_keys)
            print(f"[HIGH IMPACT NEWS] Text alert sent: {(article.get('title') or '')[:80]}")
    except Exception as exc:
        print(f"[ERROR] High impact news check failed: {exc}")

    try:
        import forexfactory_calendar as ffcal
        events = ffcal.get_upcoming_high_impact(hours_ahead=2, target_currencies={"USD"})
        if events:
            now = datetime.now(timezone.utc)
            for ev in events:
                dt = ev.get("datetime")
                if not dt:
                    continue
                mins_until = int((dt - now).total_seconds() / 60)
                if mins_until > 90:
                    continue
                hour_key = dt.strftime("%Y%m%d_%H%M")
                cal_key = f"calendar:{hour_key}:{ev['country']}:{ev['title']}"
                if cal_key in _seen_keys:
                    continue
                alert_text = format_calendar_alert_md([ev])
                if not alert_text:
                    continue
                await broadcast(context.bot, alert_text)
                _seen_keys.add(cal_key)
                save_seen_keys(_seen_keys)
                print(f"[CALENDAR] Alert: {ev['title']} ({ev['country']}) in {mins_until}m")
    except Exception as exc:
        print(f"[ERROR] Calendar check failed: {exc}")


def _signals_yesterday() -> list[dict]:
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    return [s for s in load_signal_log() if s.get("date") == yesterday]


def _build_signal_results_block(signals: list[dict]) -> str:
    if not signals:
        return "_No signals sent yesterday._"
    lines: list[str] = []
    for s in signals:
        icon = " 🟢" if s["direction"] == "BUY" else " 🔴"
        lines.append(f"{icon} {s['pair']}: {s['direction']} @ {s['entry']} — OPEN")
        lines.append(f"   TP1: {s['tp1']} / TP2: {s['tp2']} | SL: {s['sl']}")
    return "\n".join(lines)


async def morning_briefing_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Template 4 — Morning market briefing (text, English only)."""
    try:
        now_ist  = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        date_str = now_ist.strftime("%d %B %Y")

        # Yesterday's signals
        yesterday_signals = _signals_yesterday()
        sig_lines = []
        for s in yesterday_signals[:4]:
            icon = "🟢" if s["direction"] == "BUY" else "🔴"
            sig_lines.append(f"{icon} {s['pair']} {s['direction']} @ {s['entry']} — OPEN")
        sig_block = "\n".join(sig_lines) if sig_lines else "_No signals sent yesterday._"

        # Key events today
        ev_lines = []
        try:
            import forexfactory_calendar as ffcal
            all_events = ffcal.get_upcoming_high_impact(hours_ahead=24)
            for ev in all_events[:4]:
                imp     = ev.get("impact", "MED").upper()
                imp_ico = "🔴" if imp == "HIGH" else "🟡"
                ev_lines.append(f"{imp_ico} {ev.get('time','')}  —  {_strip_md(ev['title'])}  [{imp}]")
        except Exception:
            pass
        ev_block = "\n".join(ev_lines) if ev_lines else "_No major events today._"

        # Market overview (English only)
        prices      = fetch_current_prices()
        gold_price  = prices.get("XAU/USD", "N/A")
        dxy_price   = prices.get("DXY",     "N/A")
        nifty_price = prices.get("NIFTY",   "N/A")

        overview = _strip_md(
            _groq_chat(
                f"Generate a 3-4 sentence market overview for {date_str}. "
                f"DXY={dxy_price}, Gold={gold_price}, Nifty={nifty_price}. "
                "Cover DXY trend, Gold level, key overnight moves, caution zones. "
                "English only. Concise."
            ) or
            f"Gold at {gold_price}. DXY at {dxy_price}. Nifty at {nifty_price}. "
            "Trade cautiously around major economic events today."
        )

        text = (
            f"🌅 *Market Briefing — {date_str}*\n"
            f"_Forex  ·  Crypto  ·  NSE / BSE  ·  Events_\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📋 *Yesterday's Signals*\n"
            f"{sig_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Key Events Today* (IST)\n"
            f"{ev_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔭 *Market Overview*\n"
            f"{overview}\n\n"
            f"🔖 #morning  #briefing  #forex  #NSE  #crypto"
        )
        await broadcast(context.bot, text)
        print(f"[MORNING BRIEFING] Sent for {date_str}")
    except Exception as exc:
        print(f"[ERROR] Morning briefing failed: {exc}")


async def premarket_india_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Template 6 — Pre-market India NSE/BSE news (30 min before 9:15 AM IST open)."""
    try:
        now_ist  = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        date_str = now_ist.strftime("%d %b %Y")

        articles = fetch_latest_articles(INTRADAY_STOCK_QUERY) + \
                   fetch_latest_articles(INDIA_MARKET_QUERY)

        news_lines = []
        seen_titles: set[str] = set()
        for a in articles:
            t = _strip_md(a.get("title") or "")
            if not t or t in seen_titles:
                continue
            seen_titles.add(t)
            src = _strip_md(a.get("source_name") or "")
            news_lines.append(f"• {t[:90]}" + (f"\n  📰 _{src}_" if src else ""))
            if len(news_lines) >= 5:
                break

        news_block = "\n".join(news_lines) if news_lines else "_No pre-market news available._"

        prices      = fetch_current_prices()
        nifty_price = prices.get("NIFTY", "N/A")
        sensex_str  = "—"
        nifty_str   = f"{nifty_price}" if nifty_price != "N/A" else "N/A"

        outlook_prompt = (
            f"In 2 sentences, give a pre-market outlook for Indian NSE/BSE markets on {date_str}. "
            f"Nifty futures: {nifty_str}. English only. Concise."
        )
        outlook = _strip_md(_groq_chat(outlook_prompt) or
                            "Watch for gap-up or gap-down openings based on overnight global cues.")

        text = (
            f"🔔 *PRE-MARKET INDIA — {date_str}*\n"
            f"⏰ _NSE/BSE opens in ~30 minutes_\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📰 *Top Stories Before Open*\n"
            f"{news_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Pre-Market Levels*\n"
            f"  NIFTY futures:  {nifty_str}\n\n"
            f"💡 *Pre-Market Signal:* {outlook}\n\n"
            f"🔖 #premarket  #NSE  #BSE  #India"
        )
        await broadcast(context.bot, text)
        print(f"[PRE-MARKET INDIA] Sent for {date_str}")
    except Exception as exc:
        print(f"[ERROR] Pre-market India job failed: {exc}")


async def session_summary_job(
    context: ContextTypes.DEFAULT_TYPE,
    session_name: str,
    is_open: bool,
    tags: list[str],
) -> None:
    """Template 5 — Market session open / close summary."""
    try:
        now_ist  = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        date_str = now_ist.strftime("%d %b %Y")
        time_str = now_ist.strftime("%I:%M %p")
        phase    = "OPENS 🟢" if is_open else "CLOSES 🔴"
        phase_icon = "🔔" if is_open else "🔕"

        prices = fetch_current_prices()
        label_map = [
            ("XAU/USD", "Gold  (XAU/USD)"),
            ("EUR/USD", "EUR/USD       "),
            ("GBP/USD", "GBP/USD       "),
            ("US100",   "NASDAQ 100    "),
            ("US30",    "Dow Jones     "),
            ("DXY",     "DXY Index     "),
            ("NIFTY",   "Nifty 50      "),
            ("WTI",     "Crude Oil WTI "),
            ("US10Y",   "US 10Y Yield  "),
        ]
        price_lines = []
        for key, label in label_map:
            val = prices.get(key)
            if val:
                price_lines.append(f"  {label}: {_price_str(val, key)}")
            if len(price_lines) >= 6:
                break
        prices_block = "\n".join(price_lines) if price_lines else "  _Prices unavailable_"

        outlook_prompt = (
            f"In 2-3 sentences give a trading outlook for the {session_name} "
            f"session {'opening' if is_open else 'closing'} on {date_str}. "
            "English only. Factual and concise."
        )
        outlook = _strip_md(_groq_chat(outlook_prompt) or
                            f"Monitor key levels during the {session_name} session.")

        tag_str = "  ".join(f"#{t}" for t in tags)
        text = (
            f"{phase_icon} *{session_name} — {phase}*\n"
            f"📅 {date_str}  ·  {time_str} IST\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Market Snapshot*\n"
            f"{prices_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Session Outlook:*\n"
            f"{outlook}\n\n"
            f"🔖 {tag_str}"
        )
        await broadcast(context.bot, text)
        print(f"[SESSION] {session_name} {'OPEN' if is_open else 'CLOSE'} summary sent.")
    except Exception as exc:
        print(f"[ERROR] Session summary job failed: {exc}")


# ── Session job wrappers (one per open/close event) ──────────────────────────
async def _nse_open_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "NSE / BSE India", True, ["NSE", "BSE", "India", "marketopen"])

async def _nse_close_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "NSE / BSE India", False, ["NSE", "BSE", "India", "marketclose"])

async def _london_open_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "London Forex", True, ["London", "forex", "GBP", "EUR", "session"])

async def _london_close_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "London Forex", False, ["London", "forex", "session"])

async def _ny_open_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "New York Forex", True, ["NewYork", "NYSE", "forex", "USD", "session"])

async def _ny_close_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "New York Forex", False, ["NewYork", "forex", "session"])


async def _realtime_polling_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Run VIX spike, pre-market gap, and economic calendar checks."""
    sent = realtime_alert.run_polling_cycle()
    if sent:
        print(f"[REALTIME] {sent} alert(s) sent via polling cycle.")


# ── AI Agent Improvement Job ─────────────────────────────────────────────────
@contextmanager
def _period_counter():
    _period_counter._n = getattr(_period_counter, "_n", 0) + 1
    yield _period_counter._n
    _period_counter._n = getattr(_period_counter, "_n", 0)

async def ai_agent_improvement_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """AI agent runs every ~30 min to improve trade suggestions and app quality."""
    try:
        with _period_counter() as cycle:
            now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
            time_str = now_ist.strftime("%H:%M IST")

            # 1. BTC market update every cycle
            try:
                btc_update = ai_agent.generate_btc_market_update()
                if btc_update:
                    btc_block = ai_agent.format_btc_market_update(btc_update)
                    await broadcast(context.bot, btc_block)
                    print(f"[AI AGENT] BTC market update sent at {time_str}")
            except Exception as e:
                print(f"[AI AGENT] BTC update failed: {e}")

            # 2. BTC trade suggestion every other cycle (every ~60 min)
            if cycle % 2 == 0:
                try:
                    btc_suggestion = ai_agent.generate_btc_trade_suggestion()
                    if btc_suggestion:
                        btc_sig_block = ai_agent.format_btc_signal_block(btc_suggestion)
                        await broadcast(context.bot, btc_sig_block)
                        print(f"[AI AGENT] BTC trade suggestion sent at {time_str}")
                except Exception as e:
                    print(f"[AI AGENT] BTC suggestion failed: {e}")

            # 3. Educational tip every 6 cycles (~3 hours)
            if cycle % 6 == 0:
                try:
                    recent_signals = load_signal_log()[-20:]
                    tip = ai_agent.generate_market_education_tip(recent_signals)
                    if tip:
                        await broadcast(context.bot, f"🧠 *AI Education Tip*\n\n{tip}")
                        print(f"[AI AGENT] Education tip sent at {time_str}")
                except Exception as e:
                    print(f"[AI AGENT] Education tip failed: {e}")

            # 4. System improvement report twice daily (every ~12 hours = cycle 24)
            if cycle % 24 == 0:
                try:
                    recent_signals = load_signal_log()[-50:]
                    improvement = ai_agent.analyze_recent_signals_for_improvement(recent_signals)
                    if improvement:
                        await broadcast(
                            context.bot,
                            f"🤖 *AI System Improvement Report*\n\n{improvement}",
                        )
                        print(f"[AI AGENT] Improvement report sent at {time_str}")
                except Exception as e:
                    print(f"[AI AGENT] Improvement report failed: {e}")

            # 5. Market snapshot every 8 cycles (~4 hours)
            if cycle % 8 == 0:
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
                    await broadcast(context.bot, "\n".join(snapshot_lines))
                    print(f"[AI AGENT] Market snapshot sent at {time_str}")
                except Exception as e:
                    print(f"[AI AGENT] Market snapshot failed: {e}")

            print(f"[AI AGENT] Cycle {cycle} completed at {time_str}")
    except Exception as exc:
        print(f"[AI AGENT] Job failed: {exc}")


async def worker_loop() -> None:
    global _seen_keys, _signal_log, _subscribers
    _seen_keys  = load_seen_keys()
    _signal_log = load_signal_log()
    _subscribers = load_subscribers()
    provider    = get_active_provider()

    print("ForexSignalAI worker started.")
    print(f"Polling {provider} every {FETCH_INTERVAL_SECONDS}s / high-impact every {HIGH_IMPACT_CHECK_INTERVAL}s")
    print(f"Loaded {len(_seen_keys)} previously sent article keys.")
    print(f"Loaded {len(_subscribers)} subscriber(s).")
    _backfill_subscribers_from_updates()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  start_command))
    app.add_handler(CommandHandler("help",   help_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stock",  stock_command))
    app.add_handler(CommandHandler("fundamentals", fundamentals_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_question))

    jq = app.job_queue

    # ── Start Finnhub WebSocket listener in background ────────────────────────
    try:
        realtime_alert.start_websocket_thread()
        print("[REALTIME] Finnhub WebSocket listener started.")
    except Exception as e:
        print(f"[REALTIME] WebSocket thread failed: {e}")

    # ── Regular news broadcast & high-impact monitoring ───────────────────────
    jq.run_repeating(news_broadcast_job,      interval=FETCH_INTERVAL_SECONDS,       first=10)
    jq.run_repeating(high_impact_check_job,   interval=HIGH_IMPACT_CHECK_INTERVAL,   first=5)

    # ── Crypto pump screener (every N seconds, configurable) ────────────────────
    jq.run_repeating(crypto_screener_job,     interval=crypto_screener.CRYPTO_SCAN_INTERVAL, first=30)

    # ── AI Agent improvement loop (every 30 min) ─────────────────────────────
    jq.run_repeating(ai_agent_improvement_job, interval=1800, first=60)

    # ── Real-time monitoring polling checks ───────────────────────────────────
    jq.run_repeating(_realtime_polling_job,   interval=300, first=30)  # every 5 minutes

    # ── Dedicated major pair signals (XAUUSD, BTC, Nasdaq, US30, EUR/USD, GBP/USD) ──
    # Run every 4 hours to ensure consistent coverage of major pairs
    async def _dedicated_signals_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            import run as _run
            # Inline the dedicated signal sending to avoid module issues
            from telegram import Bot
            prices = fetch_current_prices()
            sent = 0

            for pair_info in [
                ("XAU/USD GOLD", "🥇", "XAU/USD · Gold vs USD", "XAU/USD"),
                ("BTC/USD BITCOIN", "₿", "BTC/USD · Bitcoin vs USD", "BTC/USD"),
                ("US100 NASDAQ", "📈", "US100 · NASDAQ Index", "US100"),
                ("US30 DOW JONES", "📊", "US30 · Dow Jones Index", "US30"),
                ("EUR/USD", "💶", "EUR/USD · Euro vs US Dollar", "EUR/USD"),
                ("GBP/USD", "💷", "GBP/USD · British Pound vs US Dollar", "GBP/USD"),
            ]:
                signal_type, icon, pair_label, pair_key = pair_info
                current_price = prices.get(pair_key)
                if signal_type == "XAU/USD GOLD":
                    ai_fn = ai_agent.generate_xauusd_signal
                elif signal_type == "BTC/USD BITCOIN":
                    ai_fn = ai_agent.generate_btc_trade_suggestion
                elif signal_type == "US100 NASDAQ":
                    ai_fn = ai_agent.generate_nasdaq_signal
                elif signal_type == "US30 DOW JONES":
                    ai_fn = ai_agent.generate_us30_signal
                else:
                    ai_fn = lambda cp=None, nc="": ai_agent.generate_forex_pair_signal(pair_key, cp, nc)

                ai_output = ai_fn(current_price=current_price)
                if ai_output:
                    block = ai_agent.format_ai_signal_block(signal_type, icon, pair_label, ai_output, current_price)
                    if block:
                        await broadcast(ctx.bot, block)
                        sent += 1
            if sent:
                print(f"[DEDICATED SIGNALS] Sent {sent} major pair signal(s).")
        except Exception as e:
            print(f"[DEDICATED SIGNALS] Job failed: {e}")

    jq.run_repeating(_dedicated_signals_job, interval=14400, first=120)  # every 4 hours

    # ── Morning briefing: 8:00 AM IST = 02:30 UTC ────────────────────────────
    jq.run_daily(morning_briefing_job,  time=time(hour=2,  minute=30), name="morning_briefing")

    # ── Pre-market India: 8:45 AM IST = 03:15 UTC ────────────────────────────
    jq.run_daily(premarket_india_job,   time=time(hour=3,  minute=15), name="premarket_india")

    # ── NSE/BSE Session: Open 9:15 AM IST (03:45 UTC), Close 3:30 PM (10:00 UTC)
    jq.run_daily(_nse_open_job,         time=time(hour=3,  minute=45), name="nse_open")
    jq.run_daily(_nse_close_job,        time=time(hour=10, minute=0),  name="nse_close")

    # ── London Forex: Open 1:30 PM IST (08:00 UTC), Close 9:30 PM (16:00 UTC)
    jq.run_daily(_london_open_job,      time=time(hour=8,  minute=0),  name="london_open")
    jq.run_daily(_london_close_job,     time=time(hour=16, minute=0),  name="london_close")

    # ── New York Forex: Open 6:30 PM IST (13:00 UTC), Close 12:30 AM (19:00 UTC)
    jq.run_daily(_ny_open_job,          time=time(hour=13, minute=0),  name="ny_open")
    jq.run_daily(_ny_close_job,         time=time(hour=19, minute=0),  name="ny_close")

    print("All jobs scheduled. Listening for user questions...")

    await app.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> int:
    print("Launching ForexSignalAI Bot Engine...")
    missing = validate_config()
    if missing:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing)}")
        return 1

    asyncio.run(worker_loop())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

