# 常见问题

## 安装相关

### Playwright 安装失败

```bash
uv run playwright install chromium
uv run playwright install-deps chromium  # 安装系统依赖
```

### macOS 上 Playwright Sync API 报错

```
playwright._impl._errors.Error: It looks like you are using Playwright Sync API inside the asyncio loop.
```

设置环境变量：
```bash
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
uv run autoteam rotate
```

## 登录相关

### Codex OAuth 登录失败：未获取到 authorization code

常见原因：
1. **IP 被标记** — VPS 的 IP 被 OpenAI/Cloudflare 拦截，建议换住宅代理
2. **Cloudflare 验证** — 无头浏览器被检测，需要较新的 Chromium
3. **workspace 选择失败** — 页面结构变化，查看 `screenshots/codex_04_*.png` 截图

### 登录后 plan 显示 free 而不是 team

`state.json` 中的 `workspace_name` 或 `account_id` 不正确。检查：
```bash
cat state.json | python -m json.tool
```
确认 `account_id` 是 UUID 格式，`workspace_name` 是 Team 名称。

### 验证码一直获取失败

- 检查 CloudMail 是否正常（能否手动登录查看邮件）
- 检查邮箱域名是否正确（`CLOUDMAIL_DOMAIN`）
- 旧验证码会被自动跳过，等待新邮件到达

## 轮转相关

### rotate 没有补号

检查 `get_team_member_count` 返回值。如果返回 -1，说明 API 调用失败：
- 确认管理员已登录（`state.json` 有 session token）
- 确认 `account_id` 是有效的 UUID

### 旧号一直被复用但额度不够

旧号复用前会验证额度，如果验证返回 `auth_error`（token 失效），会参考 `last_quota` 和 `quota_resets_at` 判断。5h 重置时间过后会视为额度已恢复。

### Team 超员但没有清理

`rotate` 会自动清理超员成员。如果没生效，手动执行：
```bash
uv run autoteam cleanup 5  # 保留 5 个席位
```

## Docker 相关

### 容器一直重启

```bash
docker compose logs  # 查看错误原因
```

通常是配置缺失。编辑 `data/.env` 后重启。

### data 目录没有写权限

容器 entrypoint 会自动 `chmod -R 777 /app/data`。如果还有问题：
```bash
sudo chmod -R 777 data/
```

### 重建容器后配置丢失

确保 `docker-compose.yml` 中有 volume 挂载：
```yaml
volumes:
  - ./data:/app/data
```

## Web 面板相关

### 页面显示 "JSON parse error"

后端返回了非 JSON 响应（通常是 500 错误）。查看 Docker/终端日志定位具体错误。

### 操作按钮全部禁用

需要先在「设置」页完成管理员登录。

### 刷新后数据没更新

点击侧边栏底部的「刷新数据」按钮手动刷新。
