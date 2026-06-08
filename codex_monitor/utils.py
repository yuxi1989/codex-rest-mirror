from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


BEIJING_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def fetch_json(url: str, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "codex-reset-monitor/2.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def timestamp_to_text(value) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S 北京时间")


def iso_to_text(value) -> str:
    if not isinstance(value, str) or not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S 北京时间")
    except ValueError:
        return value


def percentage(value) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return f"{value * 100:.0f}%"


def probability_bucket(value, step: float = 0.05):
    if not isinstance(value, (int, float)):
        return None
    return round(round(value / step) * step, 2)


def truncate(value: str, limit: int) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[: max(0, limit - 1)]}…"


def markdown_lines(label: str, value: str, limit: int = 220) -> list[str]:
    lines = truncate(str(value or "-"), limit).splitlines() or ["-"]
    return [f"> {label}: {lines[0]}", *[f"> {line}" for line in lines[1:]]]

