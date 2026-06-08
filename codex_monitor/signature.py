from __future__ import annotations

from .utils import probability_bucket


def _copy_previous_radar_keys(old_signature: dict) -> dict:
    return {key: value for key, value in old_signature.items() if key.startswith("radar")}


def radar_signature(payload: dict | None, old_signature: dict | None = None) -> dict:
    if not payload:
        return _copy_previous_radar_keys(old_signature or {})

    window = payload.get("window") or {}
    prediction = payload.get("prediction") or {}
    recent_windows = payload.get("recent_windows") or []
    latest_window = recent_windows[0] if recent_windows else {}
    model_iq = ((payload.get("model_iq") or {}).get("latest") or {})
    latest_window_key = latest_window.get("id") or "|".join(
        str(latest_window.get(key) or "") for key in ("title", "opened_at", "closed_at")
    )

    return {
        "radarWindowOpen": payload.get("window_open"),
        "radarStatus": payload.get("status"),
        "radarAction": payload.get("recommended_action"),
        "radarOpenedAt": window.get("opened_at"),
        "radarClosedAt": window.get("closed_at"),
        "radarSourceUrl": window.get("source_url"),
        "radarPredictionLevel": prediction.get("level"),
        "radarProbability24hBucket": probability_bucket(prediction.get("probability_24h")),
        "radarProbability48hBucket": probability_bucket(prediction.get("probability_48h")),
        "radarLatestWindow": latest_window_key,
        "radarLatestWindowStatus": latest_window.get("status"),
        "radarLatestWindowClosedAt": latest_window.get("closed_at"),
        "radarModelIqDate": model_iq.get("date"),
        "radarModelIqStatus": model_iq.get("status"),
        "radarModelIqScore": model_iq.get("score"),
    }


def build_signature(hascodex: dict, radar: dict | None, old_signature: dict | None = None) -> dict:
    summary = hascodex.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    signature = {
        "state": hascodex.get("state"),
        "latestTweetId": latest.get("tweetId"),
        "latestVerdict": latest.get("verdict"),
        "lastResetTweetId": last_reset.get("tweetId"),
    }
    signature.update(radar_signature(radar, old_signature))
    return signature


def changed_keys(old_signature: dict, new_signature: dict) -> list[str]:
    return [key for key, value in new_signature.items() if old_signature.get(key) != value]

