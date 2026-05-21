# hascodexratelimitreset.today monitor

这个站点前端使用了公开 JSON 接口：

```text
GET https://hascodexratelimitreset.today/api/status
```

当前返回字段里比较适合监控的是：

- `state`: 当前状态，例：`yes` / `no`
- `updatedAt`: 当前状态更新时间，毫秒时间戳
- `resetAt`: 预计或自动重置时间，毫秒时间戳
- `automationSummary.latest`: 最近一次追踪到的帖子和判定
- `automationSummary.lastReset`: 最近一次确认 reset 的帖子和判定

## Webhook 监控

```bash
export WECOM_WEBHOOK_URL='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key'
python3 monitor_hascodex.py --once
```

持续轮询，默认每 300 秒检查一次：

```bash
export WECOM_WEBHOOK_URL='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key'
python3 monitor_hascodex.py
```

同时支持企业微信、飞书、钉钉。配置一个或多个 webhook 都可以：

```bash
export WECOM_WEBHOOK_URL='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...'
export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/...'
export DINGTALK_WEBHOOK_URL='https://oapi.dingtalk.com/robot/send?access_token=...'
python3 monitor_hascodex.py --once
```

如果飞书或钉钉机器人开启了签名校验，额外配置：

```bash
export FEISHU_SECRET='飞书签名密钥'
export DINGTALK_SECRET='钉钉加签密钥'
```

自定义间隔：

```bash
HASCODEX_INTERVAL=60 python3 monitor_hascodex.py
```

脚本默认发送这些消息格式：

- 企业微信：`markdown,news`
- 飞书：`post` 富文本消息，包含中文摘要、原文、译文和链接
- 钉钉：`markdown,feedCard`，其中 `feedCard` 是图文卡片

脚本会把上一次看到的状态保存到 `.hascodex-monitor-state.json`，只有检测到这些字段变化时才发送 webhook 消息：

- `state`
- `updatedAt`
- `resetAt`
- `automationSummary.latest.tweetId`
- `automationSummary.latest.verdict`
- `automationSummary.lastReset.tweetId`
- `automationSummary.lastReset.checkedAt`

## GitHub Actions 部署

已提供 workflow：

```text
.github/workflows/monitor-hascodex.yml
```

它会每 10 分钟运行一次，也支持在 GitHub 页面手动触发 `workflow_dispatch`。
手动触发时可以把 `force_notify` 设为 `true`，即使状态没有变化也会强制发送一次通知，适合测试通知格式。

部署步骤：

1. 把本目录推送到 GitHub 仓库。
2. 进入仓库 `Settings -> Secrets and variables -> Actions -> New repository secret`。
3. 按需添加 secret：

```text
Name: WECOM_WEBHOOK_URL
Value: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key

Name: FEISHU_WEBHOOK_URL
Value: https://open.feishu.cn/open-apis/bot/v2/hook/...

Name: FEISHU_SECRET
Value: 飞书签名密钥，没有开启签名校验可不填

Name: DINGTALK_WEBHOOK_URL
Value: https://oapi.dingtalk.com/robot/send?access_token=...

Name: DINGTALK_SECRET
Value: 钉钉加签密钥，没有开启加签可不填
```

workflow 会把 `.hascodex-monitor-state.json` 提交回仓库，用于下次运行时判断是否有更新。不要把 webhook 写进代码或提交 `.env`。

可选环境变量：

- `WECOM_MESSAGE_MODE`: 通知类型，默认 `markdown,news`，也可以设为 `markdown` 或 `news`
- `DINGTALK_MESSAGE_MODE`: 钉钉通知类型，默认 `markdown,feedcard`，也可以设为 `markdown` 或 `feedcard`
- `HASCODEX_IMAGE_URL`: 图文卡片封面图 URL
- `HASCODEX_FORCE_NOTIFY`: 设为 `1` 时强制发送一次通知
