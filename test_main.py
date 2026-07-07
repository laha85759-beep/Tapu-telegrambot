import inspect
import unittest
from unittest.mock import AsyncMock, patch

import main


class BotConfigTests(unittest.TestCase):
    def test_resolve_bot_settings_prefers_primary_bot_token(self):
        env = {
            "BOT_TOKEN": "main-bot-token",
            "BOT_TOKEN3": "backup-bot-token",
            "TELEGRAM_CHAT_ID": "@primary",
            "TELEGRAM_CHAT_ID3": "@backup",
        }

        self.assertEqual(main.resolve_bot_settings(env), ("main-bot-token", "@primary"))


class NewsHelpersTests(unittest.TestCase):
    def test_build_newsdata_url_uses_query_and_api_key(self):
        with patch.object(main, "NEWSDATA_API_KEY", "demo-key"):
            url = main.build_newsdata_url("forex usd")

        self.assertIn("apikey=demo-key", url)
        self.assertIn("q=forex+usd", url)

    def test_build_newsapi_url_uses_query_and_api_key(self):
        with patch.object(main, "NEWS_API_KEY", "demo-key"):
            url = main.build_newsapi_url("forex usd")

        self.assertIn("apiKey=demo-key", url)
        self.assertIn("q=forex+usd", url)

    def test_get_active_provider_prefers_explicit_provider(self):
        with patch.object(main, "NEWS_PROVIDER", "newsdata"), patch.object(main, "NEWS_API_KEY", "demo"):
            self.assertEqual(main.get_active_provider(), "newsdata")

    def test_get_active_provider_uses_newsapi_when_key_exists(self):
        with patch.object(main, "NEWS_PROVIDER", "auto"), patch.object(main, "NEWS_API_KEY", "demo"):
            self.assertEqual(main.get_active_provider(), "newsapi")

    def test_is_forex_relevant_detects_currency_news(self):
        article = {"title": "Dollar rises as Fed signals another hike"}

        self.assertTrue(main.is_forex_relevant(article))

    def test_infer_bias_signal_detects_bullish_usd(self):
        article = {"title": "Dollar gains after hawkish Fed comments"}

        self.assertEqual(main.infer_bias_signal(article), "Bullish USD")

    def test_format_forex_message_includes_bias_asset_and_suggestion(self):
        article = {
            "title": "Dollar gains after hawkish Fed comments",
            "source_name": "Reuters",
            "pubDate": "2026-06-23 10:00:00",
            "description": "The US dollar climbed after stronger inflation data.",
            "link": "https://example.com/story",
        }

        with patch.object(main, "ai_analyze_news", return_value=None), \
             patch.object(main, "_groq_chat", return_value=None), \
             patch.object(main, "translate_to_bengali", return_value=None), \
             patch.object(main, "fetch_current_prices", return_value={"EUR/USD": 1.0800}):
            message = main.format_forex_message(article)

        self.assertIn("TradeSignal Pro", message)
        self.assertIn("AI Signal", message)
        self.assertIn("EUR/USD", message)
        self.assertIn("AI Confidence", message)

    def test_format_india_message_includes_all_mandatory_fields(self):
        article = {
            "title": "Nifty hits new high on RBI policy",
            "source_name": "Economic Times",
            "pubDate": "2026-06-23 10:00:00",
            "description": "The Nifty index reached a new all-time high.",
            "link": "https://example.com/nifty",
        }

        with patch.object(main, "translate_to_bengali", return_value=None), \
             patch.object(main, "format_stock_price_info", return_value=None), \
             patch.object(main, "fetch_current_prices", return_value={"NIFTY": 19500.0}):
            message = main.format_india_message(article)

        self.assertIn("NIFTY", message)
        self.assertIn("Analysis:", message)
        self.assertIn("SIGNAL", message)

    def test_format_intraday_message_includes_all_mandatory_fields(self):
        article = {
            "title": "Reliance surges on block deal",
            "source_name": "Bloomberg",
            "pubDate": "2026-06-23 10:00:00",
            "description": "Reliance Industries shares surged 3%.",
            "link": "https://example.com/reliance",
        }

        with patch.object(main, "translate_to_bengali", return_value=None), \
             patch.object(main, "format_stock_price_info", return_value=None), \
             patch.object(main, "fetch_current_prices", return_value={"RELIANCE": 2800.0}):
            message = main.format_intraday_message(article)

        self.assertIn("RELIANCE", message)
        self.assertIn("NSE", message)
        self.assertIn("Analysis:", message)
        self.assertIn("SIGNAL", message)

    def test_identify_asset_returns_symbol_when_found(self):
        article = {"title": "Dollar strengthens against euro"}

        self.assertEqual(main.identify_asset(article), "EUR")

    def test_identify_asset_returns_market_fallback(self):
        article = {"title": "Unknown financial news"}

        self.assertEqual(main.identify_asset(article), "MARKET")

    def test_ensure_summary_uses_description(self):
        article = {"description": "Detailed market analysis here"}

        self.assertIn("Detailed market analysis", main.ensure_summary(article))

    def test_ensure_summary_falls_back_to_title(self):
        article = {"title": "Breaking news headline", "description": ""}

        self.assertIn("Breaking news headline", main.ensure_summary(article))

    def test_ensure_summary_fallback_message(self):
        article = {"title": "", "description": ""}

        self.assertEqual(main.ensure_summary(article), "No summary available.")

    def test_generate_trade_suggestion_from_bias(self):
        article = {"title": "Dollar gains after hawkish Fed data"}
        suggestion = main.generate_trade_suggestion(article, "USD")

        self.assertIn("BUY", suggestion)
        self.assertIn("USD", suggestion)

    def test_generate_trade_suggestion_fallback(self):
        article = {"title": "Neutral market update"}
        suggestion = main.generate_trade_suggestion(article, "NIFTY")

        self.assertIn("WATCH", suggestion)
        self.assertIn("NIFTY", suggestion)

    def test_load_newsdata_articles_returns_results(self):
        payload = {"status": "success", "results": [{"title": "A"}, {"title": "B"}]}

        articles = main.load_newsdata_articles(payload)

        self.assertEqual(len(articles), 2)

    def test_load_newsapi_articles_normalizes_results(self):
        payload = {
            "status": "ok",
            "articles": [
                {
                    "title": "Dollar rises",
                    "description": "USD gains",
                    "url": "https://example.com/a",
                    "publishedAt": "2026-06-23T10:00:00Z",
                    "source": {"name": "Reuters"},
                }
            ],
        }

        articles = main.load_newsapi_articles(payload)

        self.assertEqual(articles[0]["source_name"], "Reuters")
        self.assertEqual(articles[0]["link"], "https://example.com/a")


class BilingualAndStockTests(unittest.TestCase):
    def test_translate_to_bengali_handles_import_error(self):
        result = main.translate_to_bengali("")
        self.assertIsNone(result)

    def test_translate_to_bengali_handles_api_error(self):
        with patch.object(main, "urlopen", side_effect=Exception("Network error")), \
             patch("deep_translator.GoogleTranslator", side_effect=Exception("API error")):
            result = main.translate_to_bengali("Hello world")
        self.assertIsNone(result)

    def test_format_forex_message_includes_bengali_summary_when_available(self):
        article = {
            "title": "Dollar rises on Fed",
            "source_name": "Reuters",
            "pubDate": "2026-06-23 10:00:00",
            "description": "The US dollar climbed higher.",
            "link": "https://example.com",
        }

        with patch.object(main, "ai_analyze_news", return_value=None), \
             patch.object(main, "_groq_chat", return_value=None), \
             patch.object(main, "translate_to_bengali", return_value="মার্কিন ডলার বেড়েছে"), \
             patch.object(main, "fetch_current_prices", return_value={"EUR/USD": 1.0800}):
            message = main.format_forex_message(article)

        self.assertIn("TradeSignal Pro", message)
        self.assertNotIn("মার্কিন ডলার বেড়েছে", message)
        self.assertNotIn("বাংলা", message)

    def test_format_forex_message_skips_bengali_when_unavailable(self):
        article = {
            "title": "Dollar rises on Fed",
            "source_name": "Reuters",
            "pubDate": "2026-06-23 10:00:00",
            "description": "The US dollar climbed higher.",
            "link": "https://example.com",
        }

        with patch.object(main, "ai_analyze_news", return_value=None), \
             patch.object(main, "_groq_chat", return_value=None), \
             patch.object(main, "translate_to_bengali", return_value=None), \
             patch.object(main, "fetch_current_prices", return_value={"EUR/USD": 1.0800}):
            message = main.format_forex_message(article)

        self.assertIn("TradeSignal Pro", message)
        self.assertNotIn("বাংলা", message)

    def test_format_intraday_message_shows_exchange_tag(self):
        article = {
            "title": "TCS wins big deal",
            "source_name": "Bloomberg",
            "pubDate": "2026-06-23 10:00:00",
            "description": "TCS shares surged on contract win.",
            "link": "https://example.com/tcs",
        }

        with patch.object(main, "translate_to_bengali", return_value=None), \
             patch.object(main, "format_stock_price_info", return_value=None), \
             patch.object(main, "fetch_current_prices", return_value={"TCS": 4000.0}):
            message = main.format_intraday_message(article)

        self.assertIn("TCS", message)
        self.assertIn("NSE", message)

    def test_format_stock_price_info_returns_none_for_unknown_asset(self):
        result = main.format_stock_price_info("UNKNOWN")
        self.assertIsNone(result)

    def test_format_india_message_includes_stock_price_when_available(self):
        article = {
            "title": "HDFC Bank gains on strong results",
            "source_name": "Economic Times",
            "pubDate": "2026-06-23 10:00:00",
            "description": "HDFC Bank shares rose after quarterly results.",
            "link": "https://example.com/hdfc",
        }

        with patch.object(main, "translate_to_bengali", return_value=None), \
             patch.object(main, "format_stock_price_info", return_value="<b>Live Price:</b> 1800.50 (+15.20 | +0.85%)"), \
             patch.object(main, "fetch_current_prices", return_value={"HDFCBANK": 1800.0}):
            message = main.format_india_message(article)

        self.assertIn("Live Price:", message)
        self.assertIn("1800.50", message)

    def test_more_indian_stocks_in_currency_hints(self):
        self.assertIn("WIPRO", main.CURRENCY_HINTS)
        self.assertIn("ITC", main.CURRENCY_HINTS)
        self.assertIn("TATAMOTORS", main.CURRENCY_HINTS)
        self.assertIn("BAJFINANCE", main.CURRENCY_HINTS)
        self.assertIn("ULTRACEMCO", main.CURRENCY_HINTS)


class AIQuestionTests(unittest.TestCase):
    def test_ai_answer_question_returns_none_without_key(self):
        with patch.object(main, "GROQ_API_KEY", ""), \
             patch.object(main, "fetch_current_prices", return_value={}):
            result = main.ai_answer_question("Is EUR/USD bullish?")
        self.assertIsNone(result)

    def test_ai_answer_question_handles_api_error(self):
        with patch.object(main, "GROQ_API_KEY", "demo-key"), \
             patch.object(main, "urlopen", side_effect=Exception("API error")), \
             patch.object(main, "fetch_current_prices", return_value={}):
            result = main.ai_answer_question("Is EUR/USD bullish?")
        self.assertIsNone(result)


class AsyncWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_category_article_sends_one_and_deduplicates(self):
        bot = AsyncMock()
        seen_keys = set()
        recent_date = main.datetime.now(main.timezone.utc).isoformat()
        articles = [
            {"article_id": "1", "title": "Dollar rises on Fed optimism", "description": "USD gains", "link": "https://a", "pubDate": recent_date},
            {"article_id": "1", "title": "Dollar rises on Fed optimism", "description": "USD gains", "link": "https://a", "pubDate": recent_date},
            {"article_id": "2", "title": "Euro climbs on ECB rate hold", "description": "EUR gains", "link": "https://b", "pubDate": recent_date},
        ]

        with patch.object(main, "fetch_current_prices", return_value={"EUR/USD": 1.0800}), \
             patch.object(main, "TELEGRAM_CHAT_ID", "@channel"):
            sent = await main.send_category_article(bot, articles, seen_keys, "forex", main.format_forex_message)

        self.assertEqual(sent, 1)
        self.assertEqual(bot.send_message.await_count, 1)
        self.assertIn("forex:1", seen_keys)

    async def test_send_category_article_skips_seen_keys(self):
        bot = AsyncMock()
        seen_keys = {"forex:1"}
        recent_date = main.datetime.now(main.timezone.utc).isoformat()
        articles = [
            {"article_id": "1", "title": "Dollar rises on Fed optimism", "description": "USD gains", "link": "https://a", "pubDate": recent_date},
        ]

        sent = await main.send_category_article(bot, articles, seen_keys, "forex", main.format_forex_message)

        self.assertEqual(sent, 0)
        self.assertEqual(bot.send_message.await_count, 0)

    async def test_run_worker_cycle_sends_forex_and_india_messages(self):
        bot = AsyncMock()
        seen_keys = set()
        recent_date = main.datetime.now(main.timezone.utc).isoformat()

        article = {"article_id": "1", "title": "Euro rises on ECB outlook", "description": "EUR gains", "link": "https://a", "pubDate": recent_date}

        with patch.object(main, "fetch_latest_articles", return_value=[article]), \
             patch.object(main, "send_options_suggestion", return_value=0), \
             patch.object(main, "format_market_snapshot_block", return_value=None), \
             patch.object(main, "fetch_current_prices", return_value={"EUR/USD": 1.0800}), \
             patch.object(main, "TELEGRAM_CHAT_ID", "@channel"):
            sent = await main.run_worker_cycle(bot, seen_keys)

        self.assertGreaterEqual(sent, 1)
        self.assertGreaterEqual(bot.send_message.await_count, 1)


class MainTests(unittest.TestCase):
    def test_validate_config_lists_missing_variables_for_newsdata(self):
        with patch.object(main, "BOT_TOKEN", ""), patch.object(main, "TELEGRAM_CHAT_ID", ""), patch.object(main, "NEWS_PROVIDER", "newsdata"), patch.object(main, "NEWSDATA_API_KEY", ""):
            missing = main.validate_config()

        self.assertEqual(missing, ["BOT_TOKEN / BOT_TOKEN3", "TELEGRAM_CHAT_ID / TELEGRAM_CHAT_ID3", "NEWSDATA_API_KEY"])

    def test_validate_config_lists_missing_variables_for_newsapi(self):
        with patch.object(main, "BOT_TOKEN", "token"), patch.object(main, "TELEGRAM_CHAT_ID", "@channel"), patch.object(main, "NEWS_PROVIDER", "newsapi"), patch.object(main, "NEWS_API_KEY", ""):
            missing = main.validate_config()

        self.assertEqual(missing, ["NEWS_API_KEY"])

    @patch.object(main, "worker_loop")
    def test_main_runs_worker_when_config_is_present(self, worker_loop_mock):
        with patch.object(main, "BOT_TOKEN", "token"), patch.object(main, "TELEGRAM_CHAT_ID", "@channel"), patch.object(main, "NEWS_PROVIDER", "newsapi"), patch.object(main, "NEWS_API_KEY", "demo"):
            with patch("main.asyncio.run") as run_mock:
                exit_code = main.main()

        self.assertEqual(exit_code, 0)
        run_mock.assert_called_once()
        coroutine_arg = run_mock.call_args.args[0]
        self.assertTrue(inspect.iscoroutine(coroutine_arg))
        coroutine_arg.close()

    def test_main_returns_error_when_config_missing(self):
        with patch.object(main, "BOT_TOKEN", ""), patch.object(main, "TELEGRAM_CHAT_ID", ""), patch.object(main, "NEWS_PROVIDER", "newsapi"), patch.object(main, "NEWS_API_KEY", ""):
            self.assertEqual(main.main(), 1)


class PersistentDedupTests(unittest.TestCase):
    def setUp(self):
        self.test_file = "_test_sent_keys.json"
        main.SENT_KEYS_FILE = self.test_file

    def tearDown(self):
        import os
        try:
            os.remove(self.test_file)
        except FileNotFoundError:
            pass
        main.SENT_KEYS_FILE = "sent_articles.json"

    def test_save_and_load_roundtrip(self):
        keys = {"forex:abc", "india:def", "intraday:ghi"}
        main.save_seen_keys(keys)
        loaded = main.load_seen_keys()
        self.assertEqual(keys, loaded)

    def test_load_returns_empty_set_on_missing_file(self):
        keys = main.load_seen_keys()
        self.assertEqual(keys, set())


if __name__ == "__main__":
    unittest.main()
