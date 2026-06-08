from __future__ import annotations

from .signature import changed_keys
from .sources import RADAR_SITE_URL, SITE_URL
from .utils import markdown_lines, timestamp_to_text, truncate


LEVEL_META = {
    "reset": ("🔴", "窗口可用", "优先打开 Codex 使用额度"),
    "watch": ("🟡", "重点关注", "接下来 24-48 小时关注 reset 动向"),
    "quiet": ("🟢", "继续等待", "无需操作，避免被低价值动态打扰"),
}

ACTION_LABELS = {
    "wait": "继续等待",
    "watch": "持续关注",
    "use": "立即使用",
    "open": "窗口开启",
    "none": "无动作",
}

STATUS_LABELS = {
    "none": "无窗口",
    "open": "已开启",
    "closed": "已关闭",
    "active": "进行中",
}

IQ_STATUS_LABELS = {
    "green": "绿色",
    "yellow": "黄色",
    "red": "红色",
}


def action_label(value: str) -> str:
    return ACTION_LABELS.get(value, value or "-")


def status_label(value: str) -> str:
    return STATUS_LABELS.get(value, value or "-")


def iq_status_label(value: str) -> str:
    return IQ_STATUS_LABELS.get(value, value or "-")


def level_meta(snapshot: dict) -> tuple[str, str, str]:
    return LEVEL_META.get(snapshot.get("level"), ("ℹ️", snapshot["conclusion"], "查看详情"))


def meaningful_latest(latest: dict, last_reset: dict) -> bool:
    if not latest or latest.get("tweetId") == last_reset.get("tweetId"):
        return False
    return latest.get("verdict") in {"reset_confirmed", "uncertain"}


def build_markdown(snapshot: dict, old_signature: dict, new_signature: dict) -> str:
    hascodex = snapshot["hascodex"]
    radar = snapshot["radar"]
    latest = hascodex["latest"]
    last_reset = hascodex["last_reset"]
    model_iq = radar["model_iq"]
    recent_window = radar["recent_window"]
    icon, status_text, action_text = level_meta(snapshot)

    title = f"{icon} Codex Radar：{status_text}"
    lines = [
        f"**{title}**",
        f"> 行动建议: {action_text}",
        f"> Radar 建议: {action_label(radar['action'])}，窗口：{'已开启' if radar['window_open'] else '未开启'}",
        f"> 重置概率: 24h {radar['probability_24h']} / 48h {radar['probability_48h']}，级别 {radar['prediction_level']}",
        f"> 综合状态: hascodex {hascodex['state_text']} / Radar {status_label(radar['status'])}",
        *markdown_lines("Radar 判断", radar["summary_short"], 180),
    ]

    if model_iq:
        lines.append(
            f"> Model IQ: {model_iq.get('score', '-')} 分，{model_iq.get('passed', '-')}/{model_iq.get('tasks', '-')} 通过，"
            f"{iq_status_label(model_iq.get('status'))}，{model_iq.get('model', '-')} {model_iq.get('reasoning_effort', '')}"
        )

    lines.extend(
        [
            "",
            "**状态依据**",
            f"> 当前窗口: {radar['window_title']} / {radar['window_scope']}",
            f"> 窗口时间: {radar['opened_at']} ~ {radar['closed_at']}",
            f"> hascodex 更新时间: {hascodex['updated_at']}",
        ]
    )

    if last_reset:
        lines.extend(
            [
                f"> 最近确认: {timestamp_to_text(last_reset.get('checkedAt'))}，{hascodex['last_reset_text']}",
                f"> 链接: [查看原帖]({last_reset.get('tweetUrl') or SITE_URL})",
            ]
        )

    if meaningful_latest(latest, last_reset):
        lines.extend(
            [
                "",
                "**需要复核的新动态**",
                f"> 判定: {hascodex['latest_verdict_text']}，追踪时间 {timestamp_to_text(latest.get('checkedAt'))}",
                *markdown_lines("内容", latest.get("tweetText"), 120),
                f"> 链接: [查看原帖]({latest.get('tweetUrl') or SITE_URL})",
            ]
        )

    if recent_window:
        lines.extend(
            [
                "",
                "**Radar 最近窗口**",
                f"> {recent_window.get('title') or '-'}，{recent_window.get('scope') or '-'}，{recent_window.get('window_human') or '-'}",
                *markdown_lines("说明", recent_window.get("summary"), 160),
            ]
        )

    lines.extend(["", f"链接: [hascodex]({SITE_URL}) / [Codex Radar]({radar['site_url'] or RADAR_SITE_URL})"])

    if snapshot["source_errors"]:
        lines.extend(["", f"数据源警告: {'; '.join(snapshot['source_errors'])}"])

    if old_signature:
        keys = changed_keys(old_signature, new_signature)
        if keys:
            lines.extend(["", f"变化字段: {', '.join(keys[:12])}"])

    return "\n".join(lines)


def build_plain_summary(snapshot: dict) -> str:
    hascodex = snapshot["hascodex"]
    radar = snapshot["radar"]
    model_iq = radar["model_iq"]
    icon, status_text, action_text = level_meta(snapshot)
    return "\n".join(
        [
            f"{icon} Codex Radar：{status_text}",
            f"行动建议: {action_text}",
            f"重置概率: 24h {radar['probability_24h']} / 48h {radar['probability_48h']}，级别 {radar['prediction_level']}",
            f"综合状态: hascodex {hascodex['state_text']} / Radar {status_label(radar['status'])} / {action_label(radar['action'])}",
            f"Radar 判断: {radar['summary_short']}",
            f"Model IQ: {model_iq.get('score', '-')} 分，状态 {iq_status_label(model_iq.get('status'))}" if model_iq else "Model IQ: -",
            f"链接: {SITE_URL} / {radar['site_url'] or RADAR_SITE_URL}",
        ]
    )


def build_news_articles(snapshot: dict, image_url: str) -> list[dict]:
    radar = snapshot["radar"]
    hascodex = snapshot["hascodex"]
    recent_window = radar["recent_window"]
    articles = [
        {
            "title": f"Codex Radar: {level_meta(snapshot)[1]}",
            "description": truncate(
                f"{level_meta(snapshot)[2]} / 24h {radar['probability_24h']} / 48h {radar['probability_48h']} / hascodex {hascodex['state_text']}",
                96,
            ),
            "url": radar["site_url"] or RADAR_SITE_URL,
            "picurl": image_url,
        }
    ]
    if recent_window:
        articles.append(
            {
                "title": f"最近窗口: {recent_window.get('title') or '-'}",
                "description": truncate(recent_window.get("summary") or "-", 96),
                "url": recent_window.get("source_url") or radar["site_url"] or RADAR_SITE_URL,
                "picurl": image_url,
            }
        )
    return articles


def build_feishu_post(snapshot: dict) -> dict:
    hascodex = snapshot["hascodex"]
    radar = snapshot["radar"]
    model_iq = radar["model_iq"]
    icon, status_text, action_text = level_meta(snapshot)
    content = [
        [{"tag": "text", "text": f"{icon} Codex Radar：{status_text}"}],
        [{"tag": "text", "text": f"行动建议: {action_text}"}],
        [{"tag": "text", "text": f"重置概率: 24h {radar['probability_24h']} / 48h {radar['probability_48h']}，级别 {radar['prediction_level']}"}],
        [{"tag": "text", "text": f"综合状态: hascodex {hascodex['state_text']} / Radar {status_label(radar['status'])} / {action_label(radar['action'])}"}],
        [{"tag": "text", "text": f"Radar 判断: {radar['summary_short']}"}],
    ]
    if model_iq:
        content.append([{"tag": "text", "text": f"Model IQ: {model_iq.get('score', '-')} 分，状态 {iq_status_label(model_iq.get('status'))}"}])
    content.append([{"tag": "a", "text": "查看 Codex Radar", "href": radar["site_url"] or RADAR_SITE_URL}])
    content.append([{"tag": "a", "text": "查看 hascodex", "href": SITE_URL}])
    return {"msg_type": "post", "content": {"post": {"zh_cn": {"title": f"Codex Radar：{status_text}", "content": content}}}}
