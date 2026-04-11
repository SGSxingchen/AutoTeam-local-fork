# AutoTeam

ChatGPT Team 账号自动轮转管理工具。自动创建账号、注册、获取 Codex 认证、检查额度、轮换用完的账号，并同步认证文件到 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)。

## 功能

- **自动注册** - 创建临时邮箱，注册 ChatGPT 账号，自动填写验证码/个人信息
- **Codex OAuth** - 自动完成 Codex 登录，保存 CPA 兼容的认证文件
- **额度检查** - 检测 Codex 5h 额度是否用完，token 过期自动刷新/重新登录
- **智能轮转** - 额度用完自动移出，优先复用旧账号，万不得已才创建新号
- **CPA 同步** - 认证文件自动上传/删除，只同步 active 账号
- **Team 管理** - 自动补满/清理成员，同步 Team 实际状态

## 安装

```bash
# 一键安装
bash setup.sh

# 或手动
uv sync
uv run playwright install chromium
```

## 配置

复制 `.env.example` 为 `.env`，填入实际值：

```bash
cp .env.example .env
```

需要配置：
- **CloudMail** - 临时邮箱服务地址和凭据
- **ChatGPT** - Team Account ID（从 ChatGPT admin 页面获取）
- **CPA** - CLIProxyAPI 地址和管理密钥
- **session** - ChatGPT 管理员的 `__Secure-next-auth.session-token`（拼接 .0 和 .1）写入 `session` 文件

## 使用

```bash
uv run autoteam <command> [args]
```

### 命令

| 命令 | 说明 |
|------|------|
| `status` | 查看所有账号状态（自动同步 Team 实际成员） |
| `check` | 检查 active 账号额度，token 失效自动重新登录 |
| `rotate [N]` | 智能轮转：检查额度 -> 移出用完的 -> 复用旧号 -> 补满到 N 个（默认 5） |
| `add` | 手动添加一个新账号 |
| `fill [N]` | 补满 Team 成员到 N 个（默认 5） |
| `cleanup [N]` | 清理多余成员到 N 个（只移除本地管理的） |
| `sync` | 手动同步认证文件到 CPA |

### 典型用法

```bash
# 一键轮转（日常使用，推荐）
uv run autoteam rotate

# 查看当前状态
uv run autoteam status

# 手动同步到 CPA
uv run autoteam sync
```

## 轮转逻辑

```
rotate 执行流程:

1. 同步 Team 实际成员状态
2. 检查所有 active 账号额度
   - 额度可用 -> 不动
   - 额度用完 -> 标记 exhausted
   - token 失效 -> 自动重新 Codex 登录
3. 移出 exhausted 账号
4. 统计空缺数
5. 优先复用 standby 中额度已恢复的旧账号
6. 有旧号等恢复中且 Team 仍有可用账号 -> 等待，不创建
7. 所有账号都不可用 -> 才创建新账号
8. 同步认证文件到 CPA
```

## 账号状态

| 状态 | 含义 |
|------|------|
| `active` | 在 Team 中，额度可用 |
| `exhausted` | 在 Team 中，额度用完 |
| `standby` | 已移出 Team，等待额度恢复后复用 |
| `pending` | 已创建，等待注册完成 |

## 文件结构

```
autoteam/
├── pyproject.toml          # 项目配置 + 依赖
├── setup.sh                # 一键安装
├── README.md
├── .env.example            # 配置模板
├── .env                    # 实际配置（不提交）
├── session                 # ChatGPT session token（不提交）
├── accounts.json           # 账号数据（不提交）
├── auths/                  # Codex 认证文件（不提交）
└── src/autoteam/
    ├── __init__.py
    ├── __main__.py          # python -m autoteam
    ├── manager.py           # CLI 入口，所有命令
    ├── config.py            # 配置加载（从 .env）
    ├── display.py           # 虚拟显示器自动设置
    ├── accounts.py          # 账号池持久化管理
    ├── chatgpt_api.py       # ChatGPT 内部 API
    ├── cloudmail.py         # CloudMail API 客户端
    ├── codex_auth.py        # Codex OAuth + token 管理
    ├── cpa_sync.py          # CPA 认证文件同步
    └── invite.py            # 注册流程自动化
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

## 依赖

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (包管理)
- Playwright (Chromium)
- xvfb (Linux 无头服务器)
- CloudMail 实例（Cloudflare Workers 邮箱服务）

## 友情链接

感谢 **LinuxDo** 社区的支持！

[![LinuxDo](https://img.shields.io/badge/社区-LinuxDo-blue?style=for-the-badge)](https://linux.do/)
