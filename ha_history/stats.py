"""Statistics for Home Assistant history points."""

import math
from typing import Any


def compute_stats(points: list[dict[str, Any]]) -> dict[str, int | float | str | None]:
    """Compute numeric statistics, ignoring states that cannot be parsed as numbers."""
    values: list[float] = []
    for point in points:
        try:
            value = float(point["state"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)

    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "current": None,
            "trend": "stable",
        }

    midpoint = len(values) // 2
    trend_delta = (
        sum(values[midpoint:]) / len(values[midpoint:])
        - sum(values[:midpoint]) / len(values[:midpoint])
        if midpoint
        else 0
    )
    trend = "up" if trend_delta > 0.5 else "down" if trend_delta < -0.5 else "stable"

    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "current": values[-1],
        "trend": trend,
    }
