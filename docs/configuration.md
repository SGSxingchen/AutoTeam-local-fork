# 配置说明

## .env 配置项

首次运行任何命令时会自动进入配置向导，交互式填写必填项并验证连通性。也可以手动编辑 `.env`：

```bash
cp .env.example .env
```

| 配置项 | 说明 | 必填 |
|--------|------|------|
| `CLOUDMAIL_BASE_URL` | CloudMail API 地址 | 是 |
| `CLOUDMAIL_EMAIL` | CloudMail 登录邮箱 | 是 |
| `CLOUDMAIL_PASSWORD` | CloudMail 登录密码 | 是 |
| `CLOUDMAIL_DOMAIN` | 临时邮箱域名（如 `@example.com`） | 是 |
| `CPA_URL` | CLIProxyAPI 地址 | 否（默认 `http://127.0.0.1:8317`） |
| `CPA_KEY` | CPA 管理密钥 | 是 |
| `API_KEY` | Web 面板 / API 鉴权密钥 | 否（首次启动自动生成） |
| `AUTO_CHECK_THRESHOLD` | 额度低于此百分比触发轮转 | 否（默认 `10`，可在面板修改） |
| `AUTO_CHECK_INTERVAL` | 巡检间隔（秒） | 否（默认 `300`） |
| `AUTO_CHECK_MIN_LOW` | 至少几个账号低于阈值才触发 | 否（默认 `2`） |

## 管理员登录

首次启动后在 Web 面板「设置」页或命令行完成主号登录：

```bash
uv run autoteam admin-login
uv run autoteam admin-login --email you@example.com
```

系统自动保存到 `state.json`（邮箱、session token、workspace ID 等）。

## 主号 Codex Sync

`main-codex-sync` 用于把管理员主号的 Codex 登录态单独同步到 CPA。

- **前置条件**：先完成 `admin-login`
- **交互方式**：命令行或 Web 都可以发起
- **同步结果**：成功后生成 `auths/codex-main-*.json`，并推送到 CPA
- **作用范围**：主号专用，不加入轮转池

```bash
uv run autoteam main-codex-sync
```

## 认证文件格式

兼容 CLIProxyAPI，文件名格式：`codex-{email}-{plan_type}-{hash}.json`

```json
{
  "type": "codex",
  "id_token": "eyJ...",
  "access_token": "eyJ...",
  "refresh_token": "rt_...",
  "account_id": "...",
  "email": "...",
  "expired": "2026-04-20T10:00:00Z",
  "last_refresh": "2026-04-10T10:00:00Z"
}
```

## 启动验证

每次启动会自动验证 CloudMail 和 CPA 的连通性：
- CloudMail：登录 → 创建测试邮箱 → 删除
- CPA：获取认证文件列表

验证失败会提示具体哪个环节有问题，配置有误时拒绝启动。
