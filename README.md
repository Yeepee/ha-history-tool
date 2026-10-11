# ha-history-tool

CLI tool to query the Home Assistant History API (`/api/history/period`) and return temperature trends and statistics over a given period.

## Features

- Fetch raw state points for one or multiple entities
- Compute stats: min, max, mean, current, trend (up/down/stable)
- Output as JSON or a human-readable summary
- Read credentials from the environment (no hardcoded secrets)

## Installation

Install from GitHub with `pipx`:

```bash
pipx install git+https://github.com/Yeepee/ha-history-tool.git
```

## Usage

```bash
export HASS_URL="http://127.0.0.1:8123"
export HASS_TOKEN="eyJh..."
ha-history --entity sensor.0xd44867fffe111d3c_temperature --start 2026-09-11T00:00:00Z --days 30
ha-history --entity sensor.temp_1,sensor.temp_2 --start 2026-09-01T00:00:00Z --days 30 --format json
```

`--start` is required and must include a UTC timezone (`Z` or `+00:00`). Use either `--end` or `--days`; when neither is provided, the period defaults to 30 days after `--start`. JSON output is an object for one entity and an array for multiple entities. Raw points are retained, while statistics ignore non-numeric states.

Trend detection uses a threshold of `0.5` by default. Set `--trend-threshold` to change it; `--trend-mode absolute` (the default) compares the trend's average-value delta directly against that threshold. With `--trend-mode relative`, the threshold is treated as a percentage of the numeric value range (`max - min`), so `--trend-threshold 10 --trend-mode relative` uses 10% of that range.

## Configuration

| Env var | Required | Description |
| --- | --- | --- |
| `HASS_URL` | yes | Base URL (e.g. `http://127.0.0.1:8123`) |
| `HASS_TOKEN` | yes | Long-Lived Access Token |
