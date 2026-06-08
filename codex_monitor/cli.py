from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
from pathlib import Path

from .messages import build_feishu_post, build_markdown, build_news_articles, build_plain_summary
from .signature import build_signature
from .snapshot import build_snapshot
from .sources import RADAR_URL, fetch_sources
from .utils import load_state, save_state
from .webhooks import send_dingtalk, send_feishu, send_wecom
from .sources import STATUS_URL


DEFAULT_IMAGE_URL = "https://dummyimage.com/900x383/111827/ffffff.png&text=Codex+Reset"
DEFAULT_STATE_FILE = Path(".hascodex-monitor-state.json")


def has_changed(old_signature: dict, new_signature: dict) -> bool:
    if not old_signature:
        return True
    return old_signature != new_signature


def run_once(args: argparse.Namespace) -> bool:
    state = load_state(args.state_file)
    old_signature = state.get("signature") or {}
    hascodex, radar, source_errors = fetch_sources(args.status_url, args.radar_url, args.timeout)
    new_signature = build_signature(hascodex, radar, old_signature)

    if not args.force and not has_changed(old_signature, new_signature):
        print("No meaningful change.")
        return False

    snapshot = build_snapshot(hascodex, radar, source_errors)
    markdown = build_markdown(snapshot, old_signature, new_signature)
    plain_summary = build_plain_summary(snapshot)
    feishu_post = build_feishu_post(snapshot)
    articles = build_news_articles(snapshot, args.image_url)

    sent = False
    if args.webhook_url:
        send_wecom(args.webhook_url, markdown, articles, args.timeout, args.message_mode)
        sent = True
    if args.feishu_webhook_url:
        send_feishu(args.feishu_webhook_url, feishu_post, args.timeout, args.feishu_secret)
        sent = True
    if args.dingtalk_webhook_url:
        send_dingtalk(args.dingtalk_webhook_url, "Codex 综合监控", markdown, articles, args.timeout, args.dingtalk_message_mode, args.dingtalk_secret)
        sent = True

    if sent:
        print("Meaningful change detected, webhook sent.")
    else:
        print("Meaningful change detected, webhook URL not configured. Message preview:")
        print(markdown)
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
    parser.add_argument("--message-mode", default=os.getenv("WECOM_MESSAGE_MODE", "markdown"))
    parser.add_argument("--dingtalk-message-mode", default=os.getenv("DINGTALK_MESSAGE_MODE", "markdown"))
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
