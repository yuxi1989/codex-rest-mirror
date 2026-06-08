from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request


def post_json(url: str, body: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def send_wecom(webhook_url: str, markdown: str, articles: list[dict], timeout: int, message_mode: str) -> None:
    modes = [mode.strip().lower() for mode in message_mode.split(",") if mode.strip()] or ["markdown"]
    for mode in modes:
        if mode == "markdown":
            payload = post_json(webhook_url, {"msgtype": "markdown", "markdown": {"content": markdown}}, timeout)
            if payload.get("errcode") != 0:
                raise RuntimeError(f"WeCom webhook failed: {payload}")
        elif mode == "news":
            payload = post_json(webhook_url, {"msgtype": "news", "news": {"articles": articles}}, timeout)
            if payload.get("errcode") != 0:
                raise RuntimeError(f"WeCom news webhook failed: {payload}")
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


def send_dingtalk(webhook_url: str, title: str, markdown: str, articles: list[dict], timeout: int, message_mode: str, secret: str | None) -> None:
    modes = [mode.strip().lower() for mode in message_mode.split(",") if mode.strip()] or ["markdown"]
    for mode in modes:
        signed_url = add_dingtalk_signature(webhook_url, secret)
        if mode == "markdown":
            payload = post_json(signed_url, {"msgtype": "markdown", "markdown": {"title": title, "text": markdown}}, timeout)
            if payload.get("errcode") != 0:
                raise RuntimeError(f"DingTalk webhook failed: {payload}")
        elif mode in ("feedcard", "feed_card"):
            links = [{"title": article["title"], "messageURL": article["url"], "picURL": article["picurl"]} for article in articles]
            payload = post_json(signed_url, {"msgtype": "feedCard", "feedCard": {"links": links}}, timeout)
            if payload.get("errcode") != 0:
                raise RuntimeError(f"DingTalk feedCard failed: {payload}")
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
    payload = post_json(webhook_url, add_feishu_signature(post_body, secret), timeout)
    if payload.get("code", 0) != 0:
        raise RuntimeError(f"Feishu webhook failed: {payload}")

