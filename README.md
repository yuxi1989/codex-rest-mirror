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

## 企业微信 webhook 监控

```bash
export WECOM_WEBHOOK_URL='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key'
python3 monitor_hascodex.py --once
```

持续轮询，默认每 300 秒检查一次：

```bash
export WECOM_WEBHOOK_URL='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key'
python3 monitor_hascodex.py
```

自定义间隔：

```bash
HASCODEX_INTERVAL=60 python3 monitor_hascodex.py
```

脚本会把上一次看到的状态保存到 `.hascodex-monitor-state.json`，只有检测到这些字段变化时才发送企业微信消息：

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

部署步骤：

1. 把本目录推送到 GitHub 仓库。
2. 进入仓库 `Settings -> Secrets and variables -> Actions -> New repository secret`。
3. 添加 secret：

```text
Name: WECOM_WEBHOOK_URL
Value: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key
```

workflow 会把 `.hascodex-monitor-state.json` 提交回仓库，用于下次运行时判断是否有更新。不要把 webhook 写进代码或提交 `.env`。
