from __future__ import annotations

from .sources import RADAR_SITE_URL, SITE_URL
from .utils import iso_to_text, percentage, timestamp_to_text, truncate


STATE_LABELS = {"yes": "已重置", "no": "未重置"}
VERDICT_LABELS = {"reset_confirmed": "已确认重置", "not_reset": "未重置", "uncertain": "待复核"}


def status_label(value: str) -> str:
    if not value:
        return "未知"
    return f"{STATE_LABELS.get(value, value)} ({value.upper()})"


def verdict_label(value: str) -> str:
    if not value:
        return "-"
    return f"{VERDICT_LABELS.get(value, value)} ({value})"


def alert_level(hascodex: dict, radar: dict | None) -> tuple[str, str]:
    prediction = (radar or {}).get("prediction") or {}
    probability_48h = prediction.get("probability_48h")
    window_open = bool((radar or {}).get("window_open"))

    if hascodex.get("state") == "yes" or window_open:
        return "reset", "重置窗口开启或已确认重置"
    if prediction.get("level") in {"medium", "high"} or (isinstance(probability_48h, (int, float)) and probability_48h >= 0.5):
        return "watch", "预测升温，需要关注"
    return "quiet", "暂无重置窗口，保持等待"


def build_snapshot(hascodex: dict, radar: dict | None, source_errors: list[str]) -> dict:
    summary = hascodex.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    window = (radar or {}).get("window") or {}
    prediction = (radar or {}).get("prediction") or {}
    recent_windows = (radar or {}).get("recent_windows") or []
    recent_window = recent_windows[0] if recent_windows else {}
    model_iq = (((radar or {}).get("model_iq") or {}).get("latest") or {})
    level, conclusion = alert_level(hascodex, radar)

    return {
        "level": level,
        "conclusion": conclusion,
        "hascodex": {
            "state": hascodex.get("state") or "unknown",
            "state_text": status_label(hascodex.get("state")),
            "updated_at": timestamp_to_text(hascodex.get("updatedAt")),
            "reset_at": timestamp_to_text(hascodex.get("resetAt")),
            "latest": latest,
            "latest_verdict_text": verdict_label(latest.get("verdict")),
            "last_reset": last_reset,
            "last_reset_text": verdict_label(last_reset.get("verdict")),
            "site_url": SITE_URL,
        },
        "radar": {
            "available": bool(radar),
            "window_open": bool((radar or {}).get("window_open")),
            "status": (radar or {}).get("status") or "-",
            "action": (radar or {}).get("recommended_action") or window.get("action") or "-",
            "window_title": window.get("title") or "-",
            "window_scope": window.get("scope") or "-",
            "window_message": window.get("message") or "-",
            "opened_at": iso_to_text(window.get("opened_at")),
            "closed_at": iso_to_text(window.get("closed_at")),
            "source_url": window.get("source_url") or RADAR_SITE_URL,
            "prediction_level": prediction.get("level") or "-",
            "probability_24h": percentage(prediction.get("probability_24h")),
            "probability_48h": percentage(prediction.get("probability_48h")),
            "expected_window": prediction.get("expected_window") or "-",
            "summary": prediction.get("summary") or "-",
            "summary_short": truncate(prediction.get("summary") or "-", 160),
            "recent_window": recent_window,
            "model_iq": model_iq,
            "site_url": ((radar or {}).get("links") or {}).get("html") or RADAR_SITE_URL,
        },
        "source_errors": source_errors,
    }

