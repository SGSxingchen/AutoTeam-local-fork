# 工作原理

## 轮转流程

```
                    ┌─────────────┐
                    │  同步 Team   │
                    │  实际状态    │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  检查所有    │
                    │ active 额度  │
                    └──────┬──────┘
                           ▼
              ┌────────────┴────────────┐
              ▼                         ▼
        额度 ≥ 阈值 ✅          额度 < 阈值 ❌
        保持不动                  移出 Team
                                       │
                           ┌───────────┴───────────┐
                           ▼                       ▼
                    旧号额度 ≥ 阈值？         全部不可用？
                     验证后复用 ♻️           创建新号 🆕
                           │                       │
                           └───────────┬───────────┘
                                       ▼
                                ┌─────────────┐
                                │  同步到 CPA  │
                                └─────────────┘
```

## 账号状态机

```
  ┌──────────┐  额度<阈值  ┌───────────┐   移出Team   ┌──────────┐
  │  active  │ ──────────→ │ exhausted  │ ──────────→ │ standby  │
  └──────────┘             └───────────┘              └────┬─────┘
       ▲                                                   │
       └──────── 额度恢复（验证通过），重新加入 ───────────┘
```

| 状态 | 含义 |
|------|------|
| `active` | 在 Team 中，额度高于阈值 |
| `exhausted` | 在 Team 中，额度低于阈值，等待移出 |
| `standby` | 已移出 Team，等待额度恢复后复用（复用前验证） |
| `pending` | 已创建，等待注册完成 |

## 项目结构

```
autoteam/
├── pyproject.toml              # 项目配置 + 依赖
├── setup.sh                    # 一键安装脚本
├── Dockerfile                  # Docker 镜像
├── docker-compose.yml          # Docker Compose
├── .env.example                # 配置模板
├── .pre-commit-config.yaml     # pre-commit (ruff lint + format)
├── ruff.toml                   # ruff 配置
├── .github/workflows/          # GitHub Actions CI
├── docs/                       # 文档
├── src/autoteam/
│   ├── manager.py              # CLI 入口，所有命令
│   ├── api.py                  # HTTP API + 鉴权 + 自动巡检
│   ├── setup_wizard.py         # 首次配置向导 + 连通性验证
│   ├── admin_state.py          # 管理员状态管理 (state.json)
│   ├── config.py               # 配置加载（从 .env）
│   ├── display.py              # 虚拟显示器自动设置
│   ├── accounts.py             # 账号池持久化管理
│   ├── account_ops.py          # 账号删除/清理操作
│   ├── chatgpt_api.py          # ChatGPT 内部 API + 管理员登录
│   ├── cloudmail.py            # CloudMail API 客户端
│   ├── codex_auth.py           # Codex OAuth + token + 主号同步
│   ├── cpa_sync.py             # CPA 认证文件同步
│   ├── invite.py               # 注册流程自动化
│   └── web/dist/               # 前端构建产物（已内置）
└── web/                        # 前端源码（Vue 3 + Vite + Tailwind）
    ├── src/
    │   ├── App.vue             # 主组件 + 鉴权 + 路由
    │   ├── api.js              # API 调用封装
    │   └── components/         # 页面组件
    ├── package.json
    └── vite.config.js
```

## 依赖

| 依赖 | 用途 |
|------|------|
| [Python 3.10+](https://python.org) | 运行环境 |
| [uv](https://docs.astral.sh/uv/) | 包管理 |
| [Playwright](https://playwright.dev) | 浏览器自动化 (Chromium) |
| [FastAPI](https://fastapi.tiangolo.com) | HTTP API 框架 |
| [Rich](https://rich.readthedocs.io) | 终端美化输出 |
| [Vue 3](https://vuejs.org) | Web 管理面板 |
| [Tailwind CSS](https://tailwindcss.com) | 前端样式 |
| xvfb | Linux 无头服务器虚拟显示 |
| [CloudMail](https://github.com/maillab/cloud-mail) | 临时邮箱服务 |
| [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) | Codex 代理 |

## 前端开发

```bash
cd web
npm install
npm run dev       # Vite dev server :5173，自动代理 /api → :8787
npm run build     # 构建产物输出到 src/autoteam/web/dist/
```
