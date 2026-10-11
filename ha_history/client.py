"""HTTP client for the Home Assistant history API."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from typing import Any


class HistoryAPIError(Exception):
    """An error returned by or encountered while calling the history API."""


class HistoryClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def get_history(
        self, entity_ids: list[str], start_time: str, end_time: str
    ) -> dict[str, list[dict[str, Any]]]:
        entity_points = {entity_id: [] for entity_id in entity_ids}
        path_start = quote(start_time, safe=":-+TZ.")
        query = urlencode(
            {
                "filter_entity_id": ",".join(entity_ids),
                "end_time": end_time,
                "minimal_response": "true",
            }
        )
        url = f"{self.base_url}/api/history/period/{path_start}?{query}"
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            exc.close()
            raise HistoryAPIError(f"Home Assistant returned HTTP {exc.code}: {exc.reason}") from exc
        except URLError as exc:
            raise HistoryAPIError(f"Could not connect to Home Assistant: {exc.reason}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HistoryAPIError(f"Home Assistant returned invalid JSON: {exc}") from exc

        if not isinstance(payload, list):
            raise HistoryAPIError("Home Assistant returned an unexpected history response")

        for history in payload:
            if not isinstance(history, list):
                continue
            for point in history:
                if not isinstance(point, dict):
                    continue
                entity_id = point.get("entity_id")
                if entity_id in entity_points:
                    entity_points[entity_id].append(point)

        return entity_points
