# Codex Reset Monitor

合并监控 [hascodexratelimitreset.today](https://hascodexratelimitreset.today/) 与 [Codex Radar](https://codexradar.com/) 的 Codex 额度重置信息，并在重要变化时推送到企业微信、飞书、钉钉机器人。

## 当前能力

- 同时读取两个公开 JSON 数据源：
  - `https://hascodexratelimitreset.today/api/status`
  - `https://codexradar.com/current.json`
- 合并生成一份综合判断：是否重置、Radar 窗口状态、建议动作、24/48 小时概率、最近窗口、Model IQ。
- 默认只在重要字段变化时通知，过滤频繁刷新的时间戳字段。
- 默认每个平台只发一条 `markdown/post` 消息，避免 `markdown + news/feedCard` 造成一次事件多条 webhook。
- webhook 默认采用紧凑 Radar 卡片：行动、概率、状态、判断、IQ、依据。
- 低价值 `not_reset` 最新动态不会进入正文，避免把普通互动推文推送到群里。
- 低概率场景下，仅 `24h/48h` 概率桶变化不会触发 webhook，只更新状态文件。
- 支持 GitHub Actions 定时运行和手动强制推送。
- 支持企业微信、飞书/Lark、钉钉 webhook，飞书和钉钉支持签名密钥。

## 项目结构

```text
monitor_hascodex.py        # 兼容入口，GitHub Actions 仍执行这个文件
codex_monitor/
  cli.py                   # 参数解析、状态读写、调度入口
  sources.py               # 两个网站数据拉取
  signature.py             # 重要变化签名与去重
  snapshot.py              # 两站数据合并后的综合快照
  messages.py              # 企业微信/飞书/钉钉通知内容
  webhooks.py              # webhook 发送与签名
  utils.py                 # 时间、JSON、文本工具
```

## 快速开始

只配置企业微信：

```bash
export WECOM_WEBHOOK_URL='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key'
python3 monitor_hascodex.py --once
```

同时配置多个平台：

```bash
export WECOM_WEBHOOK_URL='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...'
export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/...'
export DINGTALK_WEBHOOK_URL='https://oapi.dingtalk.com/robot/send?access_token=...'
python3 monitor_hascodex.py --once
```

持续轮询：

```bash
python3 monitor_hascodex.py
```

强制发送一次，用于测试通知格式：

```bash
HASCODEX_FORCE_NOTIFY=1 python3 monitor_hascodex.py --once
```

## Webhook 配置

至少配置一个 webhook。未配置的平台会自动跳过。

| 平台 | Webhook 环境变量 | 签名密钥环境变量 | 默认消息格式 |
|---|---|---|---|
| 企业微信 | `WECOM_WEBHOOK_URL` | 不需要 | `markdown` |
| 飞书/Lark | `FEISHU_WEBHOOK_URL` | `FEISHU_SECRET` | `post` |
| 钉钉 | `DINGTALK_WEBHOOK_URL` | `DINGTALK_SECRET` | `markdown` |

如果确实需要图文卡片，可以显式打开多消息模式：

```bash
export WECOM_MESSAGE_MODE='markdown,news'
export DINGTALK_MESSAGE_MODE='markdown,feedcard'
```

注意：多消息模式会让同一次监控事件在同一平台发送多条 webhook，默认不建议开启。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HASCODEX_STATUS_URL` | `https://hascodexratelimitreset.today/api/status` | hascodex JSON 地址 |
| `CODEX_RADAR_URL` | `https://codexradar.com/current.json` | Codex Radar JSON 地址；设为空可关闭 |
| `HASCODEX_INTERVAL` | `300` | 本地持续运行时的轮询间隔，单位秒 |
| `HASCODEX_TIMEOUT` | `15` | HTTP 请求超时时间，单位秒 |
| `HASCODEX_STATE_FILE` | `.hascodex-monitor-state.json` | 状态文件路径 |
| `HASCODEX_FORCE_NOTIFY` | 空 | 设为 `1` 时强制发送一次 |
| `HASCODEX_IMAGE_URL` | 默认占位图 | 图文卡片封面图 |
| `WECOM_WEBHOOK_URL` | 空 | 企业微信机器人 webhook |
| `WECOM_MESSAGE_MODE` | `markdown` | 企业微信消息类型 |
| `FEISHU_WEBHOOK_URL` | 空 | 飞书/Lark 机器人 webhook |
| `FEISHU_SECRET` | 空 | 飞书签名密钥 |
| `DINGTALK_WEBHOOK_URL` | 空 | 钉钉机器人 webhook |
| `DINGTALK_SECRET` | 空 | 钉钉加签密钥 |
| `DINGTALK_MESSAGE_MODE` | `markdown` | 钉钉消息类型 |

## 去重策略

脚本会把“重要字段签名”保存到 `.hascodex-monitor-state.json`。下一次运行只有签名变化才发送通知。

hascodex 侧关注：

- `state`
- `automationSummary.latest.tweetId`
- `automationSummary.latest.verdict`
- `automationSummary.lastReset.tweetId`

Codex Radar 侧关注：

- `window_open`
- `status`
- `recommended_action`
- `window.opened_at` / `window.closed_at` / `window.source_url`
- `prediction.level`
- `prediction.probability_24h` / `prediction.probability_48h`，按 5% 档位去抖
- `recent_windows[0]`
- `model_iq.latest.date` / `score` / `status`

以下字段默认不触发通知：

- `updatedAt`
- `resetAt`
- `checkedAt`
- `prediction.updated_at`
- `monitored_at`

如果 Codex Radar 临时拉取失败，脚本会保留上一次 Radar 签名，不会因为单次源站失败触发重复通知；通知正文会显示数据源警告。

低概率 `low` 状态下，如果只有 `24h/48h` 概率桶变化，脚本只更新 `.hascodex-monitor-state.json`，不发送 webhook。

## GitHub Actions 部署

仓库提供 workflow：

```text
.github/workflows/monitor-hascodex.yml
```

默认行为：

- 每 10 分钟运行一次。
- 支持在 GitHub Actions 页面手动触发。
- 手动触发时可以把 `force_notify` 设为 `true`。
- 自动提交 `.hascodex-monitor-state.json`，用于跨次运行去重。

部署步骤：

1. 推送代码到 GitHub 仓库。
2. 进入 `Settings -> Secrets and variables -> Actions -> New repository secret`。
3. 添加需要的平台 webhook secret。

```text
WECOM_WEBHOOK_URL
FEISHU_WEBHOOK_URL
FEISHU_SECRET
DINGTALK_WEBHOOK_URL
DINGTALK_SECRET
```

## 本地验证

```bash
python3 -m compileall monitor_hascodex.py codex_monitor
tmp=$(mktemp)
HASCODEX_STATE_FILE="$tmp" python3 monitor_hascodex.py --once
HASCODEX_STATE_FILE="$tmp" python3 monitor_hascodex.py --once
rm -f "$tmp"
```

第二次输出 `No meaningful change.` 表示去重生效。

## 安全建议

- 不要把 webhook URL 或签名密钥写进代码。
- 不要提交 `.env`。
- GitHub Actions 中使用 repository secrets。
- 企业微信、飞书、钉钉机器人建议开启关键词、签名或 IP 白名单等安全策略。

## License

MIT
