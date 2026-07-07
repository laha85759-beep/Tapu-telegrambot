"""Tests for the stock_analysis module."""

import unittest
from unittest.mock import patch

import stock_analysis


class StockSymbolDetectionTests(unittest.TestCase):
    def test_is_stock_symbol_returns_known_us_stock(self):
        self.assertEqual(stock_analysis.is_stock_symbol("AAPL"), "AAPL")

    def test_is_stock_symbol_returns_known_indian_stock(self):
        self.assertEqual(stock_analysis.is_stock_symbol("RELIANCE"), "RELIANCE")

    def test_is_stock_symbol_returns_none_for_non_stock(self):
        self.assertIsNone(stock_analysis.is_stock_symbol("EUR/USD"))

    def test_is_stock_symbol_case_insensitive(self):
        self.assertEqual(stock_analysis.is_stock_symbol("aapl"), "AAPL")

    def test_stock_symbols_contains_us_stocks(self):
        self.assertIn("MSFT", stock_analysis.STOCK_SYMBOLS)
        self.assertIn("TSLA", stock_analysis.STOCK_SYMBOLS)
        self.assertIn("GOOGL", stock_analysis.STOCK_SYMBOLS)

    def test_stock_symbols_contains_indian_stocks(self):
        self.assertIn("TCS", stock_analysis.STOCK_SYMBOLS)
        self.assertIn("HDFCBANK", stock_analysis.STOCK_SYMBOLS)
        self.assertIn("INFY", stock_analysis.STOCK_SYMBOLS)

    def test_yf_ticker_maps_indian_stocks(self):
        self.assertEqual(stock_analysis._yf_ticker("TCS"), "TCS.NS")
        self.assertEqual(stock_analysis._yf_ticker("RELIANCE"), "RELIANCE.NS")

    def test_yf_ticker_passes_through_us_stocks(self):
        self.assertEqual(stock_analysis._yf_ticker("AAPL"), "AAPL")
        self.assertEqual(stock_analysis._yf_ticker("MSFT"), "MSFT")


class PriceFormattingTests(unittest.TestCase):
    def test_format_price_large(self):
        self.assertEqual(stock_analysis._fmt_price(1500.0), "$1,500.00")

    def test_format_price_medium(self):
        self.assertEqual(stock_analysis._fmt_price(150.5), "$150.50")

    def test_format_price_small(self):
        self.assertEqual(stock_analysis._fmt_price(0.001), "$0.0010")

    def test_format_price_none(self):
        self.assertEqual(stock_analysis._fmt_price(None), "N/A")

    def test_format_pct_positive(self):
        self.assertEqual(stock_analysis._fmt_pct(2.5), "+2.50%")

    def test_format_pct_negative(self):
        self.assertEqual(stock_analysis._fmt_pct(-1.3), "-1.30%")

    def test_format_pct_none(self):
        self.assertEqual(stock_analysis._fmt_pct(None), "N/A")

    def test_format_billions(self):
        self.assertEqual(stock_analysis._fmt_billions(2_500_000_000_000), "$2,500.00B")

    def test_format_billions_none(self):
        self.assertEqual(stock_analysis._fmt_billions(None), "N/A")


class AIHelperTests(unittest.TestCase):
    def test_openai_chat_returns_none_without_key(self):
        with patch.object(stock_analysis, "OPENAI_API_KEY", ""):
            result = stock_analysis._openai_chat("test")
        self.assertIsNone(result)

    def test_groq_chat_returns_none_without_key(self):
        with patch.object(stock_analysis, "GROQ_API_KEY", ""):
            result = stock_analysis._groq_chat("test")
        self.assertIsNone(result)

    def test_call_ai_returns_none_without_keys(self):
        with patch.object(stock_analysis, "OPENAI_API_KEY", ""), \
             patch.object(stock_analysis, "GROQ_API_KEY", ""):
            result = stock_analysis._call_ai("test")
        self.assertIsNone(result)


class FetchStockInfoTests(unittest.TestCase):
    @patch("stock_analysis.yf.Ticker")
    def test_fetch_stock_info_returns_defaults_on_empty(self, mock_ticker):
        mock_info = {"longName": "Apple Inc."}
        mock_ticker.return_value.info = mock_info
        result = stock_analysis.fetch_stock_info("AAPL")
        self.assertEqual(result["name"], "Apple Inc.")
        self.assertIsNone(result["price"])

    @patch("stock_analysis.yf.Ticker")
    def test_fetch_stock_info_parses_price(self, mock_ticker):
        mock_info = {
            "longName": "Apple Inc.",
            "currentPrice": 185.50,
            "previousClose": 183.20,
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3_000_000_000_000,
            "trailingPE": 29.5,
        }
        mock_ticker.return_value.info = mock_info
        result = stock_analysis.fetch_stock_info("AAPL")
        self.assertEqual(result["price"], 185.50)
        self.assertEqual(result["change_pct"], ((185.50 - 183.20) / 183.20) * 100)


class QuickFundamentalsTests(unittest.TestCase):
    @patch("stock_analysis.fetch_stock_info")
    def test_quick_fundamentals_returns_formatted_output(self, mock_fetch):
        mock_fetch.return_value = {
            "name": "Apple Inc.",
            "short_name": "Apple",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "price": 185.50,
            "prev_close": 183.20,
            "change": 2.30,
            "change_pct": 1.26,
            "market_cap": 3_000_000_000_000,
            "beta": 1.2,
            "pe_ratio": 29.5,
            "forward_pe": 27.0,
            "pb_ratio": 8.5,
            "peg_ratio": None,
            "dividend_yield": 0.52,
            "dividend_rate": 0.96,
            "eps": 6.29,
            "eps_growth": None,
            "revenue_growth": None,
            "roe": 0.30,
            "roa": None,
            "debt_to_equity": None,
            "fifty_two_high": 200.0,
            "fifty_two_low": 150.0,
            "description": "Test description",
            "website": "",
            "exchange": "NASDAQ",
        }
        result = stock_analysis.quick_fundamentals("AAPL")
        self.assertIsNotNone(result)
        self.assertIn("AAPL", result)
        self.assertIn("Apple Inc.", result)
        self.assertIn("Technology", result)
        self.assertIn("NASDAQ", result)

    @patch("stock_analysis.fetch_stock_info")
    def test_quick_fundamentals_returns_none_on_no_price(self, mock_fetch):
        mock_fetch.return_value = {"name": "Unknown", "price": None}
        result = stock_analysis.quick_fundamentals("UNKNOWN")
        self.assertIsNotNone(result)
        self.assertIn("Could not fetch", result)


class ComprehensiveAnalysisTests(unittest.TestCase):
    @patch("stock_analysis.fetch_stock_info")
    @patch("stock_analysis.fetch_multi_timeframe_candles")
    @patch("stock_analysis.fetch_news_sentiment")
    @patch("stock_analysis._call_ai")
    def test_comprehensive_analysis_returns_formatted_html(
        self, mock_ai, mock_news, mock_candles, mock_info
    ):
        mock_info.return_value = {
            "name": "Apple Inc.",
            "short_name": "Apple",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "price": 185.50,
            "prev_close": 183.20,
            "change": 2.30,
            "change_pct": 1.26,
            "market_cap": 3_000_000_000_000,
            "beta": 1.2,
            "pe_ratio": 29.5,
            "forward_pe": 27.0,
            "pb_ratio": 8.5,
            "dividend_yield": 0.52,
            "eps": 6.29,
            "roe": 0.30,
            "fifty_two_high": 200.0,
            "fifty_two_low": 150.0,
            "description": "Leading tech company",
            "exchange": "NASDAQ",
        }
        mock_candles.return_value = {
            "1min": {
                "current": 185.50, "open": 185.00, "high": 186.00,
                "low": 184.80, "volume_avg": 50000, "change_pct": 0.27,
            }
        }
        mock_news.return_value = {
            "sentiment": "Positive",
            "score": 0.75,
            "articles": [{"title": "Apple earnings beat", "publisher": "Reuters", "link": ""}],
            "rationale": "Strong earnings report",
        }
        mock_ai.return_value = (
            "Recommendation: BUY\nEntry Price: $185.50\nStop-Loss: $183.00\n"
            "Target Price: $190.00\nRationale: Strong uptrend."
        )

        result = stock_analysis.comprehensive_analysis("AAPL")
        self.assertIsNotNone(result)
        self.assertIn("Apple Inc.", result)
        self.assertIn("AAPL", result)
        self.assertIn("185.50", result)
        self.assertIn("BUY", result)


if __name__ == "__main__":
    unittest.main()
