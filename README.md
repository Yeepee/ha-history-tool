# ha-history-tool

CLI tool to query the Home Assistant History API (`/api/history/period`) and return temperature trends and statistics over a given period.

## Features

- Fetch raw state points for one or multiple entities
- Compute stats: min, max, mean, current, trend (up/down/stable)
- Output as JSON or a human-readable summary
- Read credentials from the environment (no hardcoded secrets)

## Usage

```bash
ha-history --entity sensor.outdoor_temperature --start 2026-09-01 --end 2026-10-01
ha-history --entity sensor.temp_1,sensor.temp_2 --days 30 --format json
```

## Configuration

| Env var | Required | Description |
| --- | --- | --- |
| `HASS_URL` | yes | Base URL (e.g. `http://127.0.0.1:8123`) |
| `HASS_TOKEN` | yes | Long-Lived Access Token |
