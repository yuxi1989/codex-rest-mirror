from __future__ import annotations

from .signature import changed_keys
from .sources import RADAR_SITE_URL, SITE_URL
from .utils import markdown_lines, timestamp_to_text, truncate


def build_markdown(snapshot: dict, old_signature: dict, new_signature: dict) -> str:
    hascodex = snapshot["hascodex"]
    radar = snapshot["radar"]
    latest = hascodex["latest"]
    last_reset = hascodex["last_reset"]
    model_iq = radar["model_iq"]
    recent_window = radar["recent_window"]

    title = "Codex 综合监控有更新" if old_signature else "Codex 综合监控已启动"
    lines = [
        f"**{title}**",
        f"> 结论: {snapshot['conclusion']}",
        f"> hascodex: {hascodex['state_text']}，页面更新时间 {hascodex['updated_at']}",
        f"> Radar: {'窗口开启' if radar['window_open'] else '窗口未开启'}，状态 {radar['status']}，建议 {radar['action']}",
        f"> 预测: {radar['prediction_level']}，24h {radar['probability_24h']} / 48h {radar['probability_48h']}，{radar['expected_window']}",
        *markdown_lines("预测摘要", radar["summary_short"], 180),
    ]

    if model_iq:
        lines.append(
            f"> Model IQ: {model_iq.get('date', '-')}，{model_iq.get('model', '-')} {model_iq.get('reasoning_effort', '')}，"
            f"{model_iq.get('score', '-')} 分，{model_iq.get('passed', '-')}/{model_iq.get('tasks', '-')} 通过，状态 {model_iq.get('status', '-')}"
        )

    if last_reset:
        lines.extend(
            [
                "",
                "**最近确认重置**",
                f"> 判定: {hascodex['last_reset_text']}，追踪时间 {timestamp_to_text(last_reset.get('checkedAt'))}",
                *markdown_lines("证据", last_reset.get("tweetText"), 180),
                f"> 链接: [查看原帖]({last_reset.get('tweetUrl') or SITE_URL})",
            ]
        )

    if latest and latest.get("tweetId") != last_reset.get("tweetId"):
        lines.extend(
            [
                "",
                "**最新追踪**",
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
                f"> {recent_window.get('title') or '-'} / {recent_window.get('scope') or '-'} / {recent_window.get('status') or '-'} / {recent_window.get('window_human') or '-'}",
                *markdown_lines("说明", recent_window.get("summary"), 160),
            ]
        )

    lines.extend(["", f"链接: [hascodex]({SITE_URL}) / [Codex Radar]({radar['site_url'] or RADAR_SITE_URL})"])

    if snapshot["source_errors"]:
        lines.extend(["", f"数据源警告: {'; '.join(snapshot['source_errors'])}"])

    if old_signature:
        keys = changed_keys(old_signature, new_signature)
        lines.extend(["", f"变化字段: {', '.join(keys[:12]) or '-'}"])

    return "\n".join(lines)


def build_plain_summary(snapshot: dict) -> str:
    hascodex = snapshot["hascodex"]
    radar = snapshot["radar"]
    model_iq = radar["model_iq"]
    return "\n".join(
        [
            f"结论: {snapshot['conclusion']}",
            f"hascodex: {hascodex['state_text']}，更新时间 {hascodex['updated_at']}",
            f"Radar: {'窗口开启' if radar['window_open'] else '窗口未开启'}，状态 {radar['status']}，建议 {radar['action']}",
            f"预测: {radar['prediction_level']}，24h {radar['probability_24h']} / 48h {radar['probability_48h']}，{radar['expected_window']}",
            f"预测摘要: {radar['summary_short']}",
            f"Model IQ: {model_iq.get('date', '-')}，{model_iq.get('score', '-')} 分，状态 {model_iq.get('status', '-')}" if model_iq else "Model IQ: -",
            f"链接: {SITE_URL} / {radar['site_url'] or RADAR_SITE_URL}",
        ]
    )


def build_news_articles(snapshot: dict, image_url: str) -> list[dict]:
    radar = snapshot["radar"]
    hascodex = snapshot["hascodex"]
    recent_window = radar["recent_window"]
    articles = [
        {
            "title": f"Codex 综合监控: {snapshot['conclusion']}",
            "description": truncate(
                f"hascodex {hascodex['state_text']} / Radar {'开启' if radar['window_open'] else '未开启'} / "
                f"24h {radar['probability_24h']} / 48h {radar['probability_48h']}",
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
    content = [
        [{"tag": "text", "text": f"结论: {snapshot['conclusion']}"}],
        [{"tag": "text", "text": f"hascodex: {hascodex['state_text']}，更新时间 {hascodex['updated_at']}"}],
        [{"tag": "text", "text": f"Radar: {'窗口开启' if radar['window_open'] else '窗口未开启'}，状态 {radar['status']}，建议 {radar['action']}"}],
        [{"tag": "text", "text": f"预测: {radar['prediction_level']}，24h {radar['probability_24h']} / 48h {radar['probability_48h']}，{radar['expected_window']}"}],
        [{"tag": "text", "text": f"预测摘要: {radar['summary_short']}"}],
    ]
    if model_iq:
        content.append([{"tag": "text", "text": f"Model IQ: {model_iq.get('date', '-')}，{model_iq.get('score', '-')} 分，状态 {model_iq.get('status', '-')}"}])
    content.append([{"tag": "a", "text": "查看 Codex Radar", "href": radar["site_url"] or RADAR_SITE_URL}])
    content.append([{"tag": "a", "text": "查看 hascodex", "href": SITE_URL}])
    return {"msg_type": "post", "content": {"post": {"zh_cn": {"title": "Codex 综合监控", "content": content}}}}
