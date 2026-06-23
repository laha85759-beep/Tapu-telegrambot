import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main


class ExtractSignalTests(unittest.TestCase):
    def test_extract_signal_parses_common_trade_format(self):
        raw_text = "BUY EURUSD @ 1.0850 SL: 1.0800 TP: 1.0950"

        parsed = main.extract_signal(raw_text)

        self.assertEqual(
            parsed,
            {
                "action": "BUY",
                "asset": "EURUSD",
                "entry": "1.0850",
                "sl": "1.0800",
                "tp": "1.0950",
            },
        )

    def test_extract_signal_returns_none_for_non_signal_text(self):
        self.assertIsNone(main.extract_signal("market update only"))


class MessageTextTests(unittest.TestCase):
    def test_get_message_text_prefers_channel_post(self):
        update = SimpleNamespace(
            channel_post=SimpleNamespace(text="channel text"),
            message=SimpleNamespace(text="message text"),
        )

        self.assertEqual(main.get_message_text(update), "channel text")

    def test_get_message_text_falls_back_to_message(self):
        update = SimpleNamespace(
            channel_post=None,
            message=SimpleNamespace(text="message text"),
        )

        self.assertEqual(main.get_message_text(update), "message text")


class MainTests(unittest.TestCase):
    @patch.object(main, "BOT_TOKEN", "PLACEHOLDER_TOKEN_REVOKED")
    def test_main_returns_error_when_token_missing(self):
        self.assertEqual(main.main(), 1)

    @patch.object(main, "BOT_TOKEN", "token")
    @patch.object(main, "build_application")
    def test_main_runs_polling_when_token_exists(self, build_application_mock):
        app = MagicMock()
        build_application_mock.return_value = app

        exit_code = main.main()

        self.assertEqual(exit_code, 0)
        build_application_mock.assert_called_once_with("token")
        app.run_polling.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
