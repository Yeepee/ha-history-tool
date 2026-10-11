import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

from ha_history import __main__
from ha_history.client import HistoryAPIError, HistoryClient
from ha_history.stats import compute_stats


class StatsTests(unittest.TestCase):
    def test_ignores_non_numeric_states_and_calculates_trend(self):
        points = [
            {"state": "10"},
            {"state": "unavailable"},
            {"state": "11"},
            {"state": "12"},
            {"state": "13"},
        ]
        self.assertEqual(
            compute_stats(points),
            {
                "count": 4,
                "min": 10.0,
                "max": 13.0,
                "mean": 11.5,
                "current": 13.0,
                "trend": "up",
            },
        )

    def test_trend_thresholds(self):
        self.assertEqual(compute_stats([{"state": "1"}, {"state": "1.5"}])["trend"], "stable")
        self.assertEqual(compute_stats([{"state": "1"}, {"state": "1.6"}])["trend"], "up")
        self.assertEqual(compute_stats([{"state": "2"}, {"state": "1.4"}])["trend"], "down")

    def test_custom_absolute_trend_threshold(self):
        points = [{"state": "1"}, {"state": "1.6"}]
        self.assertEqual(compute_stats(points, trend_threshold=0.7)["trend"], "stable")
        self.assertEqual(compute_stats(points, trend_threshold=0.5)["trend"], "up")

    def test_relative_trend_threshold_uses_value_range(self):
        points = [{"state": "0"}, {"state": "100"}]
        self.assertEqual(
            compute_stats(points, trend_threshold=100, trend_mode="relative")["trend"],
            "stable",
        )
        self.assertEqual(
            compute_stats(points, trend_threshold=99, trend_mode="relative")["trend"],
            "up",
        )

    def test_rejects_invalid_trend_options(self):
        points = [{"state": "1"}, {"state": "2"}]
        for threshold in (-0.1, float("inf"), float("nan")):
            with self.subTest(threshold=threshold):
                with self.assertRaisesRegex(ValueError, "trend_threshold"):
                    compute_stats(points, trend_threshold=threshold)
        with self.assertRaisesRegex(ValueError, "trend_mode"):
            compute_stats(points, trend_mode="invalid")


class ClientTests(unittest.TestCase):
    def test_http_404_is_reported(self):
        error = HTTPError("http://homeassistant/api", 404, "Not Found", {}, None)
        with patch("ha_history.client.urlopen", side_effect=error):
            with self.assertRaisesRegex(HistoryAPIError, "HTTP 404"):
                HistoryClient("http://homeassistant", "eyJtoken").get_history(
                    ["sensor.missing"], "2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z"
                )

    def test_multiple_entities_are_returned(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    [
                        [{"entity_id": "sensor.a", "state": "1"}],
                        [{"entity_id": "sensor.b", "state": "2"}],
                    ]
                ).encode()

        with patch("ha_history.client.urlopen", return_value=Response()):
            history = HistoryClient("http://homeassistant", "eyJtoken").get_history(
                ["sensor.a", "sensor.b"], "2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z"
            )
        self.assertEqual([len(history["sensor.a"]), len(history["sensor.b"])], [1, 1])

    def test_request_uses_history_endpoint_and_bearer_token(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"[]"

        with patch("ha_history.client.urlopen", return_value=Response()) as urlopen:
            HistoryClient("http://homeassistant/", "eyJtoken").get_history(
                ["sensor.a", "sensor.b"], "2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z"
            )
        request = urlopen.call_args.args[0]
        self.assertIn("/api/history/period/2026-09-01T00:00:00Z?", request.full_url)
        self.assertIn("filter_entity_id=sensor.a%2Csensor.b", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer eyJtoken")


class CLITests(unittest.TestCase):
    def test_parser_rejects_invalid_trend_options(self):
        base_args = ["--entity", "sensor.a", "--start", "2026-09-01T00:00:00Z"]
        invalid_options = [
            ["--trend-threshold", "-1"],
            ["--trend-threshold", "nan"],
            ["--trend-mode", "invalid"],
        ]
        for option in invalid_options:
            with self.subTest(option=option):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        __main__.build_parser().parse_args(base_args + option)
                self.assertEqual(error.exception.code, 1)

    def test_trend_options_are_passed_to_compute_stats(self):
        with patch.dict(os.environ, {"HASS_URL": "http://homeassistant", "HASS_TOKEN": "eyJtoken"}):
            with patch.object(HistoryClient, "get_history", return_value={"sensor.a": []}):
                with patch.object(__main__, "compute_stats", return_value={}) as compute:
                    with redirect_stdout(io.StringIO()):
                        result = __main__.main(
                            [
                                "--entity",
                                "sensor.a",
                                "--start",
                                "2026-09-01T00:00:00Z",
                                "--trend-threshold",
                                "12.5",
                                "--trend-mode",
                                "relative",
                            ]
                        )
        self.assertEqual(result, 0)
        compute.assert_called_once_with([], trend_threshold=12.5, trend_mode="relative")

    def test_days_computes_end_relative_to_start(self):
        with patch.dict(os.environ, {"HASS_URL": "http://homeassistant", "HASS_TOKEN": "eyJtoken"}):
            with patch.object(HistoryClient, "get_history", return_value={"sensor.a": []}) as get_history:
                with redirect_stdout(io.StringIO()):
                    result = __main__.main(
                        ["--entity", "sensor.a", "--start", "2026-09-01T00:00:00Z", "--days", "7"]
                    )
        self.assertEqual(result, 0)
        self.assertEqual(get_history.call_args.args[2], "2026-09-08T00:00:00Z")

    def test_missing_environment_variable_has_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = __main__.main(
                    ["--entity", "sensor.a", "--start", "2026-09-01T00:00:00Z"]
                )
        self.assertEqual(result, 1)
        self.assertIn("HASS_URL", stderr.getvalue())

    def test_multiple_entities_print_json_array(self):
        points = {"sensor.a": [], "sensor.b": []}
        with patch.dict(os.environ, {"HASS_URL": "http://homeassistant", "HASS_TOKEN": "eyJtoken"}):
            with patch.object(HistoryClient, "get_history", return_value=points):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    result = __main__.main(
                        ["--entity", "sensor.a,sensor.b", "--start", "2026-09-01T00:00:00Z"]
                    )
        self.assertEqual(result, 0)
        self.assertEqual(len(json.loads(stdout.getvalue())), 2)


if __name__ == "__main__":
    unittest.main()
