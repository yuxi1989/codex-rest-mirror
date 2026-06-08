from __future__ import annotations

import json
import urllib.error

from .utils import fetch_json


STATUS_URL = "https://hascodexratelimitreset.today/api/status"
SITE_URL = "https://hascodexratelimitreset.today/"
RADAR_URL = "https://codexradar.com/current.json"
RADAR_SITE_URL = "https://codexradar.com/"


def fetch_sources(status_url: str, radar_url: str | None, timeout: int) -> tuple[dict, dict | None, list[str]]:
    errors: list[str] = []
    hascodex = fetch_json(status_url, timeout)
    radar = None

    if radar_url:
        try:
            radar = fetch_json(radar_url, timeout)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            errors.append(f"Codex Radar 获取失败: {exc}")

    return hascodex, radar, errors
