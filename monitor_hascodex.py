#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path


STATUS_URL = "https://hascodexratelimitreset.today/api/status"
SITE_URL = "https://hascodexratelimitreset.today/"
RADAR_URL = "https://codexradar.com/current.json"
RADAR_SITE_URL = "https://codexradar.com/"
DEFAULT_IMAGE_URL = "https://dummyimage.com/900x383/111827/ffffff.png&text=Codex+Reset"
DEFAULT_STATE_FILE = Path(".hascodex-monitor-state.json")
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
BEIJING_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


VERDICT_LABELS = {
    "reset_confirmed": "已确认重置",
    "not_reset": "未重置",
    "uncertain": "待复核",
}

STATE_LABELS = {
    "yes": "已重置",
    "no": "未重置",
}

COLOR_INFO = "info"
COLOR_COMMENT = "comment"
COLOR_WARNING = "warning"
RESET_AT_LABEL = "页面状态自动复位时间"
TRACKED_AT_LABEL = "追踪/发布时间"
RESET_TIME_NOTE = "公开确认帖只说明官方已确认重置；账号实际重置时间以 Codex 面板的 Reset 时间倒推为准。"


def fetch_json(url: str, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "hascodex-monitor/1.0",
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
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S 北京时间")
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


def status_label(value: str) -> str:
    if not value:
        return "未知"
    return f"{STATE_LABELS.get(value, value)} ({value.upper()})"


def markdown_color(value: str, color: str) -> str:
    return f'<font color="{color}">{value}</font>'


def markdown_lines(label: str, value: str, color: str | None = None) -> list[str]:
    lines = str(value or "-").splitlines() or ["-"]
    rendered = [markdown_color(line, color) if color and line else line for line in lines]
    return [f"> {label}: {rendered[0]}", *[f"> {line}" for line in rendered[1:]]]


def state_color(value: str) -> str:
    if value == "yes":
        return COLOR_INFO
    if value == "no":
        return COLOR_WARNING
    return COLOR_COMMENT


def verdict_color(value: str) -> str:
    if value == "reset_confirmed":
        return COLOR_INFO
    if value == "not_reset":
        return COLOR_WARNING
    return COLOR_COMMENT


def verdict_label(value: str) -> str:
    if not value:
        return "-"
    return f"{VERDICT_LABELS.get(value, value)} ({value})"


def truncate(value: str, limit: int) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[: max(0, limit - 1)]}…"


def translate_text(text: str, timeout: int) -> str:
    text = (text or "").strip()
    if not text:
        return "-"

    params = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "auto",
            "tl": "zh-CN",
            "dt": "t",
            "q": text,
        }
    )
    request = urllib.request.Request(
        f"{TRANSLATE_URL}?{params}",
        headers={"User-Agent": "hascodex-monitor/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return "-"

    translated = "".join(part[0] for part in payload[0] if part and part[0])
    return translated.strip() or "-"


def enrich_translations(payload: dict, timeout: int) -> dict:
    summary = payload.get("automationSummary") or {}
    for key in ("latest", "lastReset"):
        item = summary.get(key)
        if isinstance(item, dict):
            item["tweetTextZh"] = translate_text(item.get("tweetText", ""), timeout)
            item["rationaleZh"] = translate_text(item.get("rationale", ""), timeout)
    return payload


def radar_signature(payload: dict | None) -> dict:
    if not payload:
        return {}

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


def current_signature(payload: dict, radar_payload: dict | None = None) -> dict:
    summary = payload.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    signature = {
        "state": payload.get("state"),
        "latestTweetId": latest.get("tweetId"),
        "latestVerdict": latest.get("verdict"),
        "lastResetTweetId": last_reset.get("tweetId"),
    }
    signature.update(radar_signature(radar_payload))
    return signature


def has_changed(old: dict, new: dict) -> bool:
    if not old:
        return True
    return old != new


def append_radar_markdown(lines: list[str], radar_payload: dict | None) -> None:
    if not radar_payload:
        return

    window = radar_payload.get("window") or {}
    prediction = radar_payload.get("prediction") or {}
    recent_windows = radar_payload.get("recent_windows") or []
    latest_window = recent_windows[0] if recent_windows else {}
    model_iq = ((radar_payload.get("model_iq") or {}).get("latest") or {})
    action = radar_payload.get("recommended_action") or window.get("action") or "-"
    status = radar_payload.get("status") or window.get("status") or "-"
    window_open = "开启" if radar_payload.get("window_open") else "未开启"

    lines.extend(
        [
            "",
            f"**{markdown_color('Codex Radar', COLOR_INFO)}**",
            f"> 窗口状态: **{markdown_color(window_open, COLOR_INFO if radar_payload.get('window_open') else COLOR_COMMENT)}**，状态: {status}，建议: {action}",
            f"> 当前窗口: {window.get('title') or '-'} / {window.get('scope') or '-'}",
            f"> 窗口时间: {iso_to_text(window.get('opened_at'))} ~ {iso_to_text(window.get('closed_at'))}",
            f"> 预测: {prediction.get('level') or '-'}，24h {percentage(prediction.get('probability_24h'))} / 48h {percentage(prediction.get('probability_48h'))}，{prediction.get('expected_window') or '-'}",
            *markdown_lines("预测摘要", prediction.get("summary", "-"), COLOR_COMMENT),
        ]
    )

    if latest_window:
        lines.extend(
            [
                f"> 最近窗口: {latest_window.get('title') or '-'} / {latest_window.get('status') or '-'} / {latest_window.get('window_human') or '-'}",
                *markdown_lines("最近窗口说明", latest_window.get("summary", "-"), COLOR_COMMENT),
            ]
        )

    if model_iq:
        lines.append(
            f"> Model IQ: {model_iq.get('date') or '-'}，{model_iq.get('model') or '-'} {model_iq.get('reasoning_effort') or ''}，"
            f"{model_iq.get('score', '-')} 分，{model_iq.get('passed', '-')}/{model_iq.get('tasks', '-')} 通过，状态 {model_iq.get('status') or '-'}"
        )

    links = radar_payload.get("links") or {}
    lines.append(f"> 链接: [Codex Radar]({links.get('html') or RADAR_SITE_URL})")


def build_markdown(payload: dict, old_signature: dict, new_signature: dict, radar_payload: dict | None = None) -> str:
    summary = payload.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    state = payload.get("state") or "unknown"
    title = "Codex 额度重置状态有更新" if old_signature else "Codex 额度重置监控已启动"
    state_text = markdown_color(status_label(state), state_color(state))
    updated_at = markdown_color(timestamp_to_text(payload.get("updatedAt")), COLOR_COMMENT)
    reset_at = markdown_color(timestamp_to_text(payload.get("resetAt")), COLOR_COMMENT)

    lines = [
        f"**{markdown_color(title, COLOR_INFO)}**",
        f"> 当前状态: **{state_text}**",
        f"> 页面更新时间: {updated_at}",
        f"> {RESET_AT_LABEL}: {reset_at}",
    ]

    if latest:
        latest_verdict = latest.get("verdict")
        lines.extend(
            [
                "",
                f"**{markdown_color('最新追踪帖子', COLOR_INFO)}**",
                f"> {TRACKED_AT_LABEL}: {markdown_color(timestamp_to_text(latest.get('checkedAt')), COLOR_COMMENT)}",
                f"> 判定: **{markdown_color(verdict_label(latest_verdict), verdict_color(latest_verdict))}**，置信度: {markdown_color(str(latest.get('confidence', '-')), COLOR_COMMENT)}",
                *markdown_lines("原文", latest.get("tweetText", "-")),
                *markdown_lines("译文", latest.get("tweetTextZh", "-"), COLOR_INFO),
                f"> 链接: [查看原帖]({latest.get('tweetUrl', '-')})",
            ]
        )

    if last_reset:
        last_reset_verdict = last_reset.get("verdict")
        lines.extend(
            [
                "",
                f"**{markdown_color('最近一次确认重置', COLOR_INFO)}**",
                f"> {TRACKED_AT_LABEL}: {markdown_color(timestamp_to_text(last_reset.get('checkedAt')), COLOR_COMMENT)}",
                f"> 判定: **{markdown_color(verdict_label(last_reset_verdict), verdict_color(last_reset_verdict))}**，置信度: {markdown_color(str(last_reset.get('confidence', '-')), COLOR_COMMENT)}",
                f"> 说明: {markdown_color(RESET_TIME_NOTE, COLOR_COMMENT)}",
                *markdown_lines("原文", last_reset.get("tweetText", "-")),
                *markdown_lines("译文", last_reset.get("tweetTextZh", "-"), COLOR_INFO),
                f"> 链接: [查看原帖]({last_reset.get('tweetUrl', '-')})",
            ]
        )

    append_radar_markdown(lines, radar_payload)

    if old_signature:
        changed_keys = [key for key, value in new_signature.items() if old_signature.get(key) != value]
        lines.extend(["", f"变化字段: {markdown_color(', '.join(changed_keys), COLOR_WARNING)}"])

    return "\n".join(lines)


def build_news_articles(payload: dict, old_signature: dict, image_url: str, radar_payload: dict | None = None) -> list[dict]:
    summary = payload.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    state = payload.get("state") or "unknown"
    title_prefix = "Codex 状态更新" if old_signature else "Codex 监控启动"

    articles = [
        {
            "title": f"{title_prefix}: {status_label(state)}",
            "description": "\n".join(
                [
                    f"页面更新时间: {timestamp_to_text(payload.get('updatedAt'))}",
                    f"{RESET_AT_LABEL}: {timestamp_to_text(payload.get('resetAt'))}",
                ]
            ),
            "url": latest.get("tweetUrl") or last_reset.get("tweetUrl") or SITE_URL,
            "picurl": image_url,
        }
    ]

    if latest:
        latest_description = truncate(latest.get("tweetTextZh") if latest.get("tweetTextZh") != "-" else latest.get("tweetText"), 72)
        articles.append(
            {
                "title": f"最新追踪: {verdict_label(latest.get('verdict'))}",
                "description": f"{timestamp_to_text(latest.get('checkedAt'))}\n{latest_description}",
                "url": latest.get("tweetUrl") or SITE_URL,
                "picurl": image_url,
            }
        )

    if last_reset and last_reset.get("tweetId") != latest.get("tweetId"):
        last_reset_description = truncate(
            last_reset.get("tweetTextZh") if last_reset.get("tweetTextZh") != "-" else last_reset.get("tweetText"),
            72,
        )
        articles.append(
            {
                "title": f"最近确认重置: {verdict_label(last_reset.get('verdict'))}",
                "description": f"{timestamp_to_text(last_reset.get('checkedAt'))}\n{last_reset_description}",
                "url": last_reset.get("tweetUrl") or SITE_URL,
                "picurl": image_url,
            }
        )

    if radar_payload:
        prediction = radar_payload.get("prediction") or {}
        window = radar_payload.get("window") or {}
        links = radar_payload.get("links") or {}
        articles.append(
            {
                "title": f"Codex Radar: {'窗口开启' if radar_payload.get('window_open') else '窗口未开启'} / {prediction.get('level') or '-'}",
                "description": truncate(
                    f"{prediction.get('summary') or window.get('message') or '-'}\n"
                    f"24h {percentage(prediction.get('probability_24h'))} / 48h {percentage(prediction.get('probability_48h'))}",
                    96,
                ),
                "url": links.get("html") or RADAR_SITE_URL,
                "picurl": image_url,
            }
        )

    return articles[:8]


def build_plain_summary(payload: dict, old_signature: dict, radar_payload: dict | None = None) -> str:
    summary = payload.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    state = payload.get("state") or "unknown"
    title = "Codex 额度重置状态有更新" if old_signature else "Codex 额度重置监控已启动"

    parts = [
        title,
        f"当前状态: {status_label(state)}",
        f"页面更新时间: {timestamp_to_text(payload.get('updatedAt'))}",
        f"{RESET_AT_LABEL}: {timestamp_to_text(payload.get('resetAt'))}",
    ]
    if latest:
        parts.extend(
            [
                "",
                "最新追踪帖子",
                f"{TRACKED_AT_LABEL}: {timestamp_to_text(latest.get('checkedAt'))}",
                f"判定: {verdict_label(latest.get('verdict'))}，置信度: {latest.get('confidence', '-')}",
                f"原文: {latest.get('tweetText', '-')}",
                f"译文: {latest.get('tweetTextZh', '-')}",
                f"链接: {latest.get('tweetUrl', '-')}",
            ]
        )
    if last_reset:
        parts.extend(
            [
                "",
                "最近一次确认重置",
                f"{TRACKED_AT_LABEL}: {timestamp_to_text(last_reset.get('checkedAt'))}",
                f"判定: {verdict_label(last_reset.get('verdict'))}，置信度: {last_reset.get('confidence', '-')}",
                f"说明: {RESET_TIME_NOTE}",
                f"原文: {last_reset.get('tweetText', '-')}",
                f"译文: {last_reset.get('tweetTextZh', '-')}",
                f"链接: {last_reset.get('tweetUrl', '-')}",
            ]
        )
    if radar_payload:
        prediction = radar_payload.get("prediction") or {}
        window = radar_payload.get("window") or {}
        model_iq = ((radar_payload.get("model_iq") or {}).get("latest") or {})
        parts.extend(
            [
                "",
                "Codex Radar",
                f"窗口状态: {'开启' if radar_payload.get('window_open') else '未开启'}，状态: {radar_payload.get('status') or '-'}，建议: {radar_payload.get('recommended_action') or '-'}",
                f"当前窗口: {window.get('title') or '-'} / {window.get('scope') or '-'}",
                f"预测: {prediction.get('level') or '-'}，24h {percentage(prediction.get('probability_24h'))} / 48h {percentage(prediction.get('probability_48h'))}",
                f"预测摘要: {prediction.get('summary') or '-'}",
                f"Model IQ: {model_iq.get('date') or '-'}，{model_iq.get('score', '-')} 分，状态 {model_iq.get('status') or '-'}",
                f"链接: {(radar_payload.get('links') or {}).get('html') or RADAR_SITE_URL}",
            ]
        )
    return "\n".join(parts)


def build_dingtalk_markdown(payload: dict, old_signature: dict, new_signature: dict, radar_payload: dict | None = None) -> str:
    return build_markdown(payload, old_signature, new_signature, radar_payload).replace('<font color="info">', "").replace(
        '<font color="comment">', ""
    ).replace('<font color="warning">', "").replace("</font>", "")


def build_feishu_post(payload: dict, old_signature: dict, radar_payload: dict | None = None) -> dict:
    summary = payload.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    state = payload.get("state") or "unknown"
    title = "Codex 额度重置状态有更新" if old_signature else "Codex 额度重置监控已启动"

    content = [
        [
            {"tag": "text", "text": "当前状态: "},
            {"tag": "text", "text": status_label(state)},
        ],
        [
            {"tag": "text", "text": f"页面更新时间: {timestamp_to_text(payload.get('updatedAt'))}"},
        ],
        [
            {"tag": "text", "text": f"{RESET_AT_LABEL}: {timestamp_to_text(payload.get('resetAt'))}"},
        ],
    ]

    if latest:
        content.extend(
            [
                [{"tag": "text", "text": "--------"}],
                [{"tag": "text", "text": f"最新追踪: {verdict_label(latest.get('verdict'))}，置信度: {latest.get('confidence', '-')}"}],
                [{"tag": "text", "text": f"{TRACKED_AT_LABEL}: {timestamp_to_text(latest.get('checkedAt'))}"}],
                [{"tag": "text", "text": f"原文: {latest.get('tweetText', '-')}"}],
                [{"tag": "text", "text": f"译文: {latest.get('tweetTextZh', '-')}"}],
                [{"tag": "a", "text": "查看最新原帖", "href": latest.get("tweetUrl") or SITE_URL}],
            ]
        )

    if last_reset:
        content.extend(
            [
                [{"tag": "text", "text": "--------"}],
                [{"tag": "text", "text": f"最近确认重置: {verdict_label(last_reset.get('verdict'))}，置信度: {last_reset.get('confidence', '-')}"}],
                [{"tag": "text", "text": f"{TRACKED_AT_LABEL}: {timestamp_to_text(last_reset.get('checkedAt'))}"}],
                [{"tag": "text", "text": f"说明: {RESET_TIME_NOTE}"}],
                [{"tag": "text", "text": f"原文: {last_reset.get('tweetText', '-')}"}],
                [{"tag": "text", "text": f"译文: {last_reset.get('tweetTextZh', '-')}"}],
                [{"tag": "a", "text": "查看重置原帖", "href": last_reset.get("tweetUrl") or SITE_URL}],
            ]
        )

    if radar_payload:
        prediction = radar_payload.get("prediction") or {}
        window = radar_payload.get("window") or {}
        model_iq = ((radar_payload.get("model_iq") or {}).get("latest") or {})
        content.extend(
            [
                [{"tag": "text", "text": "--------"}],
                [{"tag": "text", "text": f"Codex Radar: {'窗口开启' if radar_payload.get('window_open') else '窗口未开启'}，建议: {radar_payload.get('recommended_action') or '-'}"}],
                [{"tag": "text", "text": f"当前窗口: {window.get('title') or '-'} / {window.get('scope') or '-'}"}],
                [{"tag": "text", "text": f"预测: {prediction.get('level') or '-'}，24h {percentage(prediction.get('probability_24h'))} / 48h {percentage(prediction.get('probability_48h'))}"}],
                [{"tag": "text", "text": f"预测摘要: {prediction.get('summary') or '-'}"}],
                [{"tag": "text", "text": f"Model IQ: {model_iq.get('date') or '-'}，{model_iq.get('score', '-')} 分，状态 {model_iq.get('status') or '-'}"}],
                [{"tag": "a", "text": "查看 Codex Radar", "href": (radar_payload.get("links") or {}).get("html") or RADAR_SITE_URL}],
            ]
        )

    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content,
                }
            }
        },
    }


def send_wecom_markdown(webhook_url: str, content: str, timeout: int) -> None:
    body = json.dumps({"msgtype": "markdown", "markdown": {"content": content}}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("errcode") != 0:
            raise RuntimeError(f"WeCom webhook failed: {payload}")


def send_wecom_news(webhook_url: str, articles: list[dict], timeout: int) -> None:
    body = json.dumps({"msgtype": "news", "news": {"articles": articles}}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("errcode") != 0:
            raise RuntimeError(f"WeCom news webhook failed: {payload}")


def send_wecom(webhook_url: str, markdown: str, articles: list[dict], timeout: int, message_mode: str) -> None:
    modes = [mode.strip().lower() for mode in message_mode.split(",") if mode.strip()]
    if not modes:
        modes = ["markdown", "news"]

    for mode in modes:
        if mode == "markdown":
            send_wecom_markdown(webhook_url, markdown, timeout)
        elif mode == "news":
            send_wecom_news(webhook_url, articles, timeout)
        else:
            raise RuntimeError(f"Unsupported WECOM_MESSAGE_MODE: {mode}")


def add_dingtalk_signature(webhook_url: str, secret: str | None) -> str:
    if not secret:
        return webhook_url
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    separator = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{separator}timestamp={timestamp}&sign={sign}"


def send_dingtalk_markdown(webhook_url: str, title: str, markdown: str, timeout: int, secret: str | None = None) -> None:
    body = json.dumps(
        {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown,
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        add_dingtalk_signature(webhook_url, secret),
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("errcode") != 0:
            raise RuntimeError(f"DingTalk webhook failed: {payload}")


def send_dingtalk_feed_card(webhook_url: str, articles: list[dict], timeout: int, secret: str | None = None) -> None:
    links = [
        {
            "title": article["title"],
            "messageURL": article["url"],
            "picURL": article["picurl"],
        }
        for article in articles
    ]
    body = json.dumps({"msgtype": "feedCard", "feedCard": {"links": links}}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        add_dingtalk_signature(webhook_url, secret),
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("errcode") != 0:
            raise RuntimeError(f"DingTalk feedCard webhook failed: {payload}")


def send_dingtalk(webhook_url: str, title: str, markdown: str, articles: list[dict], timeout: int, message_mode: str, secret: str | None) -> None:
    modes = [mode.strip().lower() for mode in message_mode.split(",") if mode.strip()]
    if not modes:
        modes = ["markdown", "feedcard"]

    for mode in modes:
        if mode == "markdown":
            send_dingtalk_markdown(webhook_url, title, markdown, timeout, secret)
        elif mode in ("feedcard", "feed_card"):
            send_dingtalk_feed_card(webhook_url, articles, timeout, secret)
        else:
            raise RuntimeError(f"Unsupported DINGTALK_MESSAGE_MODE: {mode}")


def add_feishu_signature(body: dict, secret: str | None) -> dict:
    if not secret:
        return body
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, b"", hashlib.sha256).digest()
    signed_body = dict(body)
    signed_body["timestamp"] = timestamp
    signed_body["sign"] = base64.b64encode(digest).decode("utf-8")
    return signed_body


def send_feishu(webhook_url: str, post_body: dict, timeout: int, secret: str | None = None) -> None:
    body = json.dumps(add_feishu_signature(post_body, secret), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code", 0) != 0:
            raise RuntimeError(f"Feishu webhook failed: {payload}")


def run_once(args: argparse.Namespace) -> bool:
    payload = fetch_json(args.status_url, args.timeout)
    payload = enrich_translations(payload, args.timeout)
    radar_payload = None
    if args.radar_url:
        try:
            radar_payload = fetch_json(args.radar_url, args.timeout)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"Codex Radar fetch failed: {exc}", file=sys.stderr)

    state = load_state(args.state_file)
    old_signature = state.get("signature") or {}
    new_signature = current_signature(payload, radar_payload)

    if not args.force and not has_changed(old_signature, new_signature):
        print("No change.")
        return False

    message = build_markdown(payload, old_signature, new_signature, radar_payload)
    dingtalk_message = build_dingtalk_markdown(payload, old_signature, new_signature, radar_payload)
    plain_summary = build_plain_summary(payload, old_signature, radar_payload)
    feishu_post = build_feishu_post(payload, old_signature, radar_payload)
    articles = build_news_articles(payload, old_signature, args.image_url, radar_payload)
    sent = False
    if args.webhook_url:
        send_wecom(args.webhook_url, message, articles, args.timeout, args.message_mode)
        sent = True
    if args.feishu_webhook_url:
        send_feishu(args.feishu_webhook_url, feishu_post, args.timeout, args.feishu_secret)
        sent = True
    if args.dingtalk_webhook_url:
        send_dingtalk(
            args.dingtalk_webhook_url,
            "Codex 额度重置状态",
            dingtalk_message,
            articles,
            args.timeout,
            args.dingtalk_message_mode,
            args.dingtalk_secret,
        )
        sent = True

    if sent:
        print("Change detected, webhook sent.")
    else:
        print("Change detected, webhook URL not configured. Message preview:")
        print(message)
        print("\nPlain summary preview:")
        print(plain_summary)
        print("\nFeishu post preview:")
        print(json.dumps(feishu_post, ensure_ascii=False, indent=2))
        print("\nNews articles preview:")
        print(json.dumps(articles, ensure_ascii=False, indent=2))

    save_state(
        args.state_file,
        {
            "signature": new_signature,
            "checkedAt": int(time.time() * 1000),
            "statusUrl": args.status_url,
            "radarUrl": args.radar_url,
        },
    )
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor Codex reset status and notify chat webhooks on meaningful updates.")
    parser.add_argument("--status-url", default=os.getenv("HASCODEX_STATUS_URL", STATUS_URL))
    parser.add_argument("--radar-url", default=os.getenv("CODEX_RADAR_URL", RADAR_URL))
    parser.add_argument("--webhook-url", default=os.getenv("WECOM_WEBHOOK_URL"))
    parser.add_argument("--feishu-webhook-url", default=os.getenv("FEISHU_WEBHOOK_URL"))
    parser.add_argument("--feishu-secret", default=os.getenv("FEISHU_SECRET"))
    parser.add_argument("--dingtalk-webhook-url", default=os.getenv("DINGTALK_WEBHOOK_URL"))
    parser.add_argument("--dingtalk-secret", default=os.getenv("DINGTALK_SECRET"))
    parser.add_argument("--state-file", type=Path, default=Path(os.getenv("HASCODEX_STATE_FILE", DEFAULT_STATE_FILE)))
    parser.add_argument("--interval", type=int, default=int(os.getenv("HASCODEX_INTERVAL", "300")))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("HASCODEX_TIMEOUT", "15")))
    parser.add_argument("--image-url", default=os.getenv("HASCODEX_IMAGE_URL", DEFAULT_IMAGE_URL))
    parser.add_argument("--message-mode", default=os.getenv("WECOM_MESSAGE_MODE", "markdown,news"))
    parser.add_argument("--dingtalk-message-mode", default=os.getenv("DINGTALK_MESSAGE_MODE", "markdown,feedcard"))
    parser.add_argument("--force", action="store_true", default=os.getenv("HASCODEX_FORCE_NOTIFY") == "1")
    parser.add_argument("--once", action="store_true", help="Run one check and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.once:
        run_once(args)
        return 0

    while True:
        try:
            run_once(args)
        except (OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"Check failed: {exc}", file=sys.stderr)
        time.sleep(max(args.interval, 30))


if __name__ == "__main__":
    raise SystemExit(main())
