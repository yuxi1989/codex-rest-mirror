# Codex Reset Monitor

监控 [hascodexratelimitreset.today](https://hascodexratelimitreset.today/) 与 [Codex Radar](https://codexradar.com/) 的 Codex 额度重置状态，并在重要状态变化时推送到企业微信、飞书、钉钉机器人。

Monitor the Codex rate-limit reset status from [hascodexratelimitreset.today](https://hascodexratelimitreset.today/) and [Codex Radar](https://codexradar.com/), then notify WeCom, Feishu/Lark, or DingTalk webhooks on meaningful changes.

## 功能介绍

- 定时请求公开接口：`https://hascodexratelimitreset.today/api/status`
- 同步读取 Codex Radar：窗口状态、24/48 小时预测、最近窗口、Model IQ
- 检测重要状态变化并自动去重，避免更新时间刷新导致重复通知
- 支持 GitHub Actions 定时部署，无需服务器
- 支持企业微信、飞书、钉钉多个 webhook 同时推送
- 通知内容包含当前状态、页面更新时间、最新追踪帖子、最近确认重置帖子
- 通知内容包含 Codex Radar 的窗口建议、预测摘要、最近重置窗口、Model IQ
- 通知时间固定显示为北京时间，适合 GitHub Actions 的 UTC 运行环境
- 自动生成中文译文，保留英文原文和原帖链接
- 企业微信支持 `markdown + news` 图文卡片
- 飞书支持 `post` 富文本消息
- 钉钉支持 `markdown + feedCard` 图文卡片
- 支持飞书、钉钉 webhook 签名校验
- 支持手动强制推送，用于测试通知格式

## Features

- Polls the public endpoint: `https://hascodexratelimitreset.today/api/status`
- Reads Codex Radar window status, prediction, recent windows, and Model IQ
- Detects meaningful status changes and suppresses timestamp-only duplicate alerts
- Runs on GitHub Actions without a dedicated server
- Sends notifications to WeCom, Feishu/Lark, and DingTalk webhooks
- Includes current status, update time, latest tracked post, and last confirmed reset
- Includes Codex Radar action, prediction summary, recent reset window, and Model IQ
- Displays timestamps in Beijing time even when running in GitHub Actions UTC
- Adds Chinese translation while keeping the original English text and source links
- Supports WeCom `markdown + news`
- Supports Feishu/Lark `post` rich text
- Supports DingTalk `markdown + feedCard`
- Supports Feishu and DingTalk webhook signing secrets
- Supports forced manual notifications for format testing

## 监控数据

站点前端使用的公开 JSON 接口：

```text
GET https://hascodexratelimitreset.today/api/status
GET https://codexradar.com/current.json
```

脚本会关注这些字段：

- `state`: 当前状态，例：`yes` / `no`
- `updatedAt`: 状态更新时间，毫秒时间戳
- `resetAt`: 预计或自动重置时间，毫秒时间戳
- `automationSummary.latest`: 最近一次追踪到的帖子和判定
- `automationSummary.lastReset`: 最近一次确认 reset 的帖子和判定

The monitor watches these fields and stores the last seen signature in `.hascodex-monitor-state.json`.

Codex Radar 重点关注这些字段：

- `window_open` / `status` / `recommended_action`: 当前是否有窗口、状态与建议动作
- `window`: 当前窗口标题、范围、打开/关闭时间、来源链接
- `prediction`: 24/48 小时概率、预测级别、摘要、正负信号
- `recent_windows[0]`: 最近一次重置窗口
- `model_iq.latest`: 最新 Model IQ 分数和状态

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

持续轮询，默认每 300 秒检查一次：

```bash
python3 monitor_hascodex.py
```

自定义轮询间隔：

```bash
HASCODEX_INTERVAL=60 python3 monitor_hascodex.py
```

强制发送一次通知，用于测试格式：

```bash
HASCODEX_FORCE_NOTIFY=1 python3 monitor_hascodex.py --once
```

## Webhook 配置

至少配置一个 webhook。未配置的平台会自动跳过。

| 平台 | Webhook 环境变量 | 签名密钥环境变量 | 默认消息格式 |
|---|---|---|---|
| 企业微信 | `WECOM_WEBHOOK_URL` | 不需要 | `markdown,news` |
| 飞书/Lark | `FEISHU_WEBHOOK_URL` | `FEISHU_SECRET` | `post` |
| 钉钉 | `DINGTALK_WEBHOOK_URL` | `DINGTALK_SECRET` | `markdown,feedcard` |

如果飞书或钉钉机器人开启了签名校验，额外配置：

```bash
export FEISHU_SECRET='飞书签名密钥'
export DINGTALK_SECRET='钉钉加签密钥'
```

Optional signing secrets:

```bash
export FEISHU_SECRET='Feishu signing secret'
export DINGTALK_SECRET='DingTalk signing secret'
```

## GitHub Actions 部署

仓库已提供 workflow：

```text
.github/workflows/monitor-hascodex.yml
```

默认行为：

- 每 10 分钟运行一次
- 支持在 GitHub Actions 页面手动触发
- 手动触发时可以把 `force_notify` 设为 `true`
- 自动提交 `.hascodex-monitor-state.json`，用于跨次运行去重

部署步骤：

1. 把代码推送到 GitHub 仓库。
2. 进入仓库 `Settings -> Secrets and variables -> Actions -> New repository secret`。
3. 按需添加以下 Secrets。

```text
WECOM_WEBHOOK_URL
FEISHU_WEBHOOK_URL
FEISHU_SECRET
DINGTALK_WEBHOOK_URL
DINGTALK_SECRET
```

English setup:

1. Push this repository to GitHub.
2. Open `Settings -> Secrets and variables -> Actions -> New repository secret`.
3. Add one or more webhook secrets listed above.
4. Open the Actions page and run `Monitor hascodex reset` manually with `force_notify=true` to test the notification format.

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HASCODEX_STATUS_URL` | `https://hascodexratelimitreset.today/api/status` | 监控接口地址 |
| `CODEX_RADAR_URL` | `https://codexradar.com/current.json` | Codex Radar JSON 地址；设为空可关闭 |
| `HASCODEX_INTERVAL` | `300` | 本地持续运行时的轮询间隔，单位秒 |
| `HASCODEX_TIMEOUT` | `15` | HTTP 请求超时时间，单位秒 |
| `HASCODEX_STATE_FILE` | `.hascodex-monitor-state.json` | 本地状态文件路径 |
| `HASCODEX_FORCE_NOTIFY` | 空 | 设为 `1` 时强制发送一次通知 |
| `HASCODEX_IMAGE_URL` | 默认占位图 | 企业微信/钉钉图文卡片封面图 |
| `WECOM_WEBHOOK_URL` | 空 | 企业微信机器人 webhook |
| `WECOM_MESSAGE_MODE` | `markdown,news` | 企业微信消息类型 |
| `FEISHU_WEBHOOK_URL` | 空 | 飞书/Lark 机器人 webhook |
| `FEISHU_SECRET` | 空 | 飞书签名密钥 |
| `DINGTALK_WEBHOOK_URL` | 空 | 钉钉机器人 webhook |
| `DINGTALK_SECRET` | 空 | 钉钉加签密钥 |
| `DINGTALK_MESSAGE_MODE` | `markdown,feedcard` | 钉钉消息类型 |

## 去重逻辑

脚本只在重要字段变化时发送通知，避免 `updatedAt`、`resetAt`、`checkedAt` 这类频繁刷新字段造成 webhook 噪音。

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

GitHub Actions 会把 `.hascodex-monitor-state.json` 提交回仓库，所以每次定时运行都能基于上一次结果判断是否需要推送。

## 安全建议

- 不要把 webhook URL 或签名密钥写进代码。
- 不要提交 `.env`。
- GitHub Actions 中使用 repository secrets。
- 企业微信、飞书、钉钉机器人建议开启关键词、签名或 IP 白名单等安全策略。

## License

MIT
