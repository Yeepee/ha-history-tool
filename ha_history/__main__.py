"""Command-line interface for querying Home Assistant history."""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .client import HistoryAPIError, HistoryClient
from .stats import compute_stats


class CLIArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def positive_int(value: str) -> int:
    try:
        days = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if days <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return days


def non_negative_float(value: str) -> float:
    try:
        threshold = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a finite non-negative number") from exc
    if not math.isfinite(threshold) or threshold < 0:
        raise argparse.ArgumentTypeError("must be a finite non-negative number")
    return threshold


def parse_utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO 8601 timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"timestamp must include a UTC timezone: {value}")
    return parsed.astimezone(timezone.utc)


def format_utc_datetime(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = CLIArgumentParser(
        prog="ha-history",
        description="Query Home Assistant history and calculate numeric statistics.",
    )
    parser.add_argument("--entity", required=True, help="comma-separated entity IDs")
    parser.add_argument("--start", required=True, help="UTC ISO 8601 start time")
    end_options = parser.add_mutually_exclusive_group()
    end_options.add_argument("--end", help="UTC ISO 8601 end time")
    end_options.add_argument("--days", type=positive_int, help="period length in days (default: 30)")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument(
        "--trend-threshold",
        type=non_negative_float,
        default=0.5,
        help="trend threshold (default: 0.5)",
    )
    parser.add_argument(
        "--trend-mode",
        choices=("absolute", "relative"),
        default="absolute",
        help="interpret the trend threshold as an absolute value or percent of the value range",
    )
    return parser


def render_text(results: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for result in results:
        stats = result["stats"]
        assert isinstance(stats, dict)
        lines.append(
            f'{result["entity_id"]}: {stats["count"]} numeric points, '
            f'min={stats["min"]}, max={stats["max"]}, mean={stats["mean"]}, '
            f'current={stats["current"]}, trend={stats["trend"]}'
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    entity_ids = [entity_id.strip() for entity_id in args.entity.split(",")]
    if not entity_ids or any(not entity_id for entity_id in entity_ids):
        print("ha-history: error: --entity must contain non-empty entity IDs", file=sys.stderr)
        return 1
    if len(set(entity_ids)) != len(entity_ids):
        print("ha-history: error: --entity must not contain duplicate entity IDs", file=sys.stderr)
        return 1

    try:
        start = parse_utc_datetime(args.start)
        end = (
            parse_utc_datetime(args.end)
            if args.end
            else start + timedelta(days=args.days if args.days is not None else 30)
        )
        if end <= start:
            raise ValueError("--end must be later than --start")
    except ValueError as exc:
        print(f"ha-history: error: {exc}", file=sys.stderr)
        return 1

    base_url = os.environ.get("HASS_URL")
    token = os.environ.get("HASS_TOKEN")
    if not base_url or not base_url.strip():
        print("ha-history: error: HASS_URL environment variable is required", file=sys.stderr)
        return 1
    if not token or not token.strip():
        print("ha-history: error: HASS_TOKEN environment variable is required", file=sys.stderr)
        return 1
    if not token.startswith("eyJ"):
        print("ha-history: error: HASS_TOKEN must be a Home Assistant long-lived access token", file=sys.stderr)
        return 1

    try:
        point_data = HistoryClient(base_url.strip(), token.strip()).get_history(
            entity_ids, format_utc_datetime(start), format_utc_datetime(end)
        )
    except HistoryAPIError as exc:
        print(f"ha-history: error: {exc}", file=sys.stderr)
        return 1

    results = [
        {
            "entity_id": entity_id,
            "points": point_data[entity_id],
            "stats": compute_stats(
                point_data[entity_id],
                trend_threshold=args.trend_threshold,
                trend_mode=args.trend_mode,
            ),
        }
        for entity_id in entity_ids
    ]
    if args.format == "json":
        output: object = results[0] if len(results) == 1 else results
        print(json.dumps(output, indent=2))
    else:
        print(render_text(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
