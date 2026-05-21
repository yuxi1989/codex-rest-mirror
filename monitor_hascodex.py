#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


STATUS_URL = "https://hascodexratelimitreset.today/api/status"
DEFAULT_STATE_FILE = Path(".hascodex-monitor-state.json")


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
    title = "Codex rate limit reset status changed" if old_signature else "Codex rate limit reset monitor started"

    lines = [
        f"**{title}**",
        f"> 当前状态: **{state.upper()}**",
        f"> 页面更新时间: {timestamp_to_text(payload.get('updatedAt'))}",
        f"> 预计/自动重置时间: {timestamp_to_text(payload.get('resetAt'))}",
    ]

    if latest:
        lines.extend(
            [
                "",
                "**Latest tracked post**",
                f"> Verdict: {latest.get('verdict', '-')}, confidence: {latest.get('confidence', '-')}",
                f"> Tweet: {latest.get('tweetText', '-')}",
                f"> URL: {latest.get('tweetUrl', '-')}",
            ]
        )

    if last_reset:
        lines.extend(
            [
                "",
                "**Last reset verdict**",
                f"> Verdict: {last_reset.get('verdict', '-')}, confidence: {last_reset.get('confidence', '-')}",
                f"> Tweet: {last_reset.get('tweetText', '-')}",
                f"> URL: {last_reset.get('tweetUrl', '-')}",
            ]
        )

    if old_signature:
        changed_keys = [key for key, value in new_signature.items() if old_signature.get(key) != value]
        lines.extend(["", f"Changed fields: `{', '.join(changed_keys)}`"])

    return "\n".join(lines)


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


def run_once(args: argparse.Namespace) -> bool:
    payload = fetch_json(args.status_url, args.timeout)
    state = load_state(args.state_file)
    old_signature = state.get("signature") or {}
    new_signature = current_signature(payload)

    if not has_changed(old_signature, new_signature):
        print("No change.")
        return False

    message = build_markdown(payload, old_signature, new_signature)
    if args.webhook_url:
        send_wecom_markdown(args.webhook_url, message, args.timeout)
        print("Change detected, webhook sent.")
    else:
        print("Change detected, webhook URL not configured. Message preview:")
        print(message)

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
