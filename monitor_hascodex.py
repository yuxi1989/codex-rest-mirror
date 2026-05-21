#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


STATUS_URL = "https://hascodexratelimitreset.today/api/status"
SITE_URL = "https://hascodexratelimitreset.today/"
DEFAULT_IMAGE_URL = "https://dummyimage.com/900x383/111827/ffffff.png&text=Codex+Reset"
DEFAULT_STATE_FILE = Path(".hascodex-monitor-state.json")
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


VERDICT_LABELS = {
    "reset_confirmed": "已确认重置",
    "not_reset": "未重置",
    "uncertain": "待复核",
}

STATE_LABELS = {
    "yes": "已重置",
    "no": "未重置",
}


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
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def status_label(value: str) -> str:
    if not value:
        return "未知"
    return f"{STATE_LABELS.get(value, value)} ({value.upper()})"


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


def current_signature(payload: dict) -> dict:
    summary = payload.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    return {
        "state": payload.get("state"),
        "updatedAt": payload.get("updatedAt"),
        "resetAt": payload.get("resetAt"),
        "latestTweetId": latest.get("tweetId"),
        "latestVerdict": latest.get("verdict"),
        "lastResetTweetId": last_reset.get("tweetId"),
        "lastResetCheckedAt": last_reset.get("checkedAt"),
    }


def has_changed(old: dict, new: dict) -> bool:
    if not old:
        return True
    return old != new


def build_markdown(payload: dict, old_signature: dict, new_signature: dict) -> str:
    summary = payload.get("automationSummary") or {}
    latest = summary.get("latest") or {}
    last_reset = summary.get("lastReset") or {}
    state = payload.get("state") or "unknown"
    title = "Codex 额度重置状态有更新" if old_signature else "Codex 额度重置监控已启动"

    lines = [
        f"**{title}**",
        f"> 当前状态: **{status_label(state)}**",
        f"> 页面更新时间: {timestamp_to_text(payload.get('updatedAt'))}",
        f"> 预计/自动重置时间: {timestamp_to_text(payload.get('resetAt'))}",
    ]

    if latest:
        lines.extend(
            [
                "",
                "**最新追踪帖子**",
                f"> 判定: {verdict_label(latest.get('verdict'))}，置信度: {latest.get('confidence', '-')}",
                f"> 原文: {latest.get('tweetText', '-')}",
                f"> 译文: {latest.get('tweetTextZh', '-')}",
                f"> 链接: {latest.get('tweetUrl', '-')}",
            ]
        )

    if last_reset:
        lines.extend(
            [
                "",
                "**最近一次确认重置**",
                f"> 判定: {verdict_label(last_reset.get('verdict'))}，置信度: {last_reset.get('confidence', '-')}",
                f"> 原文: {last_reset.get('tweetText', '-')}",
                f"> 译文: {last_reset.get('tweetTextZh', '-')}",
                f"> 链接: {last_reset.get('tweetUrl', '-')}",
            ]
        )

    if old_signature:
        changed_keys = [key for key, value in new_signature.items() if old_signature.get(key) != value]
        lines.extend(["", f"变化字段: `{', '.join(changed_keys)}`"])

    return "\n".join(lines)


def build_news_articles(payload: dict, old_signature: dict, image_url: str) -> list[dict]:
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
                    f"预计/自动重置时间: {timestamp_to_text(payload.get('resetAt'))}",
                ]
            ),
            "url": latest.get("tweetUrl") or last_reset.get("tweetUrl") or SITE_URL,
            "picurl": image_url,
        }
    ]

    if latest:
        articles.append(
            {
                "title": f"最新追踪: {verdict_label(latest.get('verdict'))}",
                "description": truncate(latest.get("tweetTextZh") if latest.get("tweetTextZh") != "-" else latest.get("tweetText"), 96),
                "url": latest.get("tweetUrl") or SITE_URL,
                "picurl": image_url,
            }
        )

    if last_reset and last_reset.get("tweetId") != latest.get("tweetId"):
        articles.append(
            {
                "title": f"最近确认重置: {verdict_label(last_reset.get('verdict'))}",
                "description": truncate(
                    last_reset.get("tweetTextZh") if last_reset.get("tweetTextZh") != "-" else last_reset.get("tweetText"),
                    96,
                ),
                "url": last_reset.get("tweetUrl") or SITE_URL,
                "picurl": image_url,
            }
        )

    return articles[:8]


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


def run_once(args: argparse.Namespace) -> bool:
    payload = fetch_json(args.status_url, args.timeout)
    payload = enrich_translations(payload, args.timeout)
    state = load_state(args.state_file)
    old_signature = state.get("signature") or {}
    new_signature = current_signature(payload)

    if not args.force and not has_changed(old_signature, new_signature):
        print("No change.")
        return False

    message = build_markdown(payload, old_signature, new_signature)
    articles = build_news_articles(payload, old_signature, args.image_url)
    if args.webhook_url:
        send_wecom(args.webhook_url, message, articles, args.timeout, args.message_mode)
        print("Change detected, webhook sent.")
    else:
        print("Change detected, webhook URL not configured. Message preview:")
        print(message)
        print("\nNews articles preview:")
        print(json.dumps(articles, ensure_ascii=False, indent=2))

    save_state(
        args.state_file,
        {
            "signature": new_signature,
            "checkedAt": int(time.time() * 1000),
            "statusUrl": args.status_url,
        },
    )
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor hascodexratelimitreset.today and notify WeCom on updates.")
    parser.add_argument("--status-url", default=os.getenv("HASCODEX_STATUS_URL", STATUS_URL))
    parser.add_argument("--webhook-url", default=os.getenv("WECOM_WEBHOOK_URL"))
    parser.add_argument("--state-file", type=Path, default=Path(os.getenv("HASCODEX_STATE_FILE", DEFAULT_STATE_FILE)))
    parser.add_argument("--interval", type=int, default=int(os.getenv("HASCODEX_INTERVAL", "300")))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("HASCODEX_TIMEOUT", "15")))
    parser.add_argument("--image-url", default=os.getenv("HASCODEX_IMAGE_URL", DEFAULT_IMAGE_URL))
    parser.add_argument("--message-mode", default=os.getenv("WECOM_MESSAGE_MODE", "markdown,news"))
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
