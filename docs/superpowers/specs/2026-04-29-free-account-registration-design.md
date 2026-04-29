# Free 账号自动注册功能 - 设计文档

**日期**：2026-04-29
**状态**：待实施

## 背景与目标

当前 AutoTeam 的自动注册流程仅支持 ChatGPT **Team** 账号：通过 CloudMail 临时邮箱 + Playwright 完成邀请/直接注册，再走 Codex OAuth 拿到 token，最终参与 Team 席位轮转。

本次新增功能：**支持 ChatGPT Free 账号的批量自动注册**，作为 Team 注册的"平行轨"。

### 关键约束

1. **域名隔离**：Free 账号必须使用与 Team 不同的域名邮箱。如果复用 Team 域名（已配置自动加入 Team workspace），新注册的账号会被自动拉进 Team。
2. **不参与轮转**：Free 账号没有像 Team 那样的"额度耗尽 → 移出 → standby"机制。Free 额度用完只能换新号。
3. **同步 CPA**：Free 的 Codex auth 文件需与 Team auth 一起进入 CPA 的 `auths/` 池，统一被 CLIProxyAPI 调用。
4. **可管理**：Web 面板要能查看列表、批量创建、单条删除、单条手动刷新 Codex token。

## 范围（Scope）

### In Scope

- 独立的 `free_accounts.json` 持久化文件（与 `accounts.json` 完全分离）
- 独立的 `CLOUDMAIL_FREE_DOMAIN` 环境变量
- 浏览器自动化复用现有 `_register_direct_once`（manager.py），Codex OAuth 复用 `login_codex_via_browser`（codex_auth.py）
- CLI 子命令 `autoteam add-free [N]`，N 默认 1，最大 50
- Web 页面 + 4 个 API 端点
- `sync_to_cpa()` 扩展：合并 Team active + 全部 Free auth 文件
- 失败回滚（Codex OAuth 失败 → 删 CloudMail 临时邮箱、不写 free_accounts.json）
- 防御兜底：`bundle.plan_type != "free"` 时回滚（提醒用户域名配错）
- 单元测试覆盖编排逻辑与 CRUD

### Out of Scope

- 自动检测 Free Codex 额度耗尽 / 自动清理（用户明确不要，只提供手动删除）
- 自动升级 Plus / 关联付款
- 批量删除 / 批量刷新（先做单条；批量后续按需加）
- Free 账号参与轮转 / standby（Free 没有这套语义）
- 如果用户既有 Team 又有 Free 域名，要不要校验它们必须不同（复杂度高，暂不做）

## 整体架构

Free 注册作为 Team 注册的**平行轨**：

```
┌─────────────────────────────────────────────────────────┐
│  现有：accounts.json (Team)        新增：free_accounts.json│
│  ├─ 邀请注册 / 直接注册             ├─ 直接注册（独立域名）  │
│  ├─ 状态机 active/exhausted/...     ├─ 无状态机             │
│  ├─ 轮转 / 额度检测 / standby       ├─ 不参与轮转            │
│  └─ Codex OAuth → auth file         └─ Codex OAuth → auth   │
│                       ↓                          ↓           │
│                    sync_to_cpa()  ← 合并两表      │           │
│                              ↓                                │
│                        CPA auths/                            │
└─────────────────────────────────────────────────────────┘
```

**复用 (不改动)**：
- `_register_direct_once`（manager.py）— 注册编排（"Accept invite" 已在 try/except 里，对 Free 是 no-op）
- `login_codex_via_browser`（codex_auth.py）— OAuth 流程，plan-agnostic
- `save_auth_file`（codex_auth.py）— 文件名格式 `codex-{email}-{plan_type}-{hash}.json` 已支持 plan_type=free
- `upload_to_cpa` / `delete_from_cpa`（cpa_sync.py）

**反向 import 权衡**：`free_register.py` 会 `from autoteam.manager import _register_direct_once`，依赖方向不太理想（一般是 manager 调下层模块），但 `_register_direct_once` 带十几个 helper 函数（`_detect_direct_register_step`、`_complete_direct_about_you` 等），完整抽出来到独立模块代价大。**先反向 import，后续如需清理再抽公共**。

## 模块划分

### 后端

| 文件 | 状态 | 作用 |
|------|------|------|
| `src/autoteam/free_accounts.py` | 新增 | `free_accounts.json` 的 CRUD |
| `src/autoteam/free_register.py` | 新增 | 单个/批量 Free 注册编排；删除清理；Codex 刷新 |
| `src/autoteam/cloudmail.py` | 改动 | `CloudMailClient(domain=None)` 加可选入参；`create_temp_email` 用入参覆盖默认 `CLOUDMAIL_DOMAIN` |
| `src/autoteam/config.py` | 改动 | 加 `CLOUDMAIL_FREE_DOMAIN`（缺失则功能不可用） |
| `src/autoteam/cpa_sync.py` | 改动 | `sync_to_cpa()` 合并两表的 auth 文件 |
| `src/autoteam/manager.py` | 改动 | 加 `cmd_add_free(N)` + CLI 子命令 `add-free` |
| `src/autoteam/api.py` | 改动 | 加 4 个 `/api/free/*` 端点 |
| `.env.example` | 改动 | 加 `CLOUDMAIL_FREE_DOMAIN=` 注释引导 |

### 前端

| 文件 | 状态 | 作用 |
|------|------|------|
| `web/src/components/FreePage.vue` | 新增 | 列表 + 批量创建 + 单条删除/刷新 |
| `web/src/components/Sidebar.vue` | 改动 | 加 "Free 账号" 入口 |
| `web/src/App.vue` | 改动 | 路由/视图切换接入 Free 页面 |
| `web/src/api.js` | 改动 | 加 4 个客户端方法 |

### 不动的

`accounts.py`、`account_ops.py`、`chatgpt_api.py`、`invite.py`、`manual_account.py`、`admin_state.py`、`setup_wizard.py`、轮转/quota/standby 全套逻辑。

## 数据格式

### `free_accounts.json`

位置：项目根，与 `accounts.json` 同级。

```json
[
  {
    "email": "tmp-abc12345@freedom.com",
    "password": "Tmp_<uuid12>!",
    "cloudmail_account_id": 12345,
    "plan_type": "free",
    "auth_file": "/abs/path/auths/codex-tmp-abc12345@freedom.com-free-7a3f9.json",
    "created_at": 1730000000.0,
    "last_refreshed_at": null,
    "last_error": null
  }
]
```

字段说明：

- 没有 `status`：Free 不参与状态机
- 没有 `quota_*`：不主动检测耗尽
- `last_refreshed_at`：手动刷新 Codex 的时间戳；首次注册时可为 null
- `last_error`：上次刷新/创建失败的简短错误（UI 显示）

### Email 唯一性校验

`add_free_account()` 调用前校验：

- 如果 email 已在 `accounts.json`（任何 status） → 拒绝，抛 `ValueError("email already in team accounts")`
- 如果 email 已在 `free_accounts.json` → 拒绝（重复）

理论上不会发生（域名都不同），但作为防御。

## 数据流

### 批量创建（核心流程）

```python
# 入口: POST /api/free/accounts {"count": N}  →  202 + task_id
# 任务体 (Playwright 单实例锁串行):

free_mail = CloudMailClient(domain=CLOUDMAIL_FREE_DOMAIN)
free_mail.login()

succeeded, failed = [], []
for i in range(N):
    account_id = None
    try:
        # 1) 拿独立域名的临时邮箱
        account_id, email = free_mail.create_temp_email()
        password = f"Tmp_{uuid.uuid4().hex[:12]}!"

        # 2) 浏览器跑 ChatGPT 注册（最多 3 次重试，复用现有逻辑）
        ok = _register_direct_once(free_mail, email, password,
                                   cloudmail_account_id=account_id)
        if not ok:
            failed.append({"email": email, "reason": "register_failed_3x"})
            free_mail.delete_account(account_id)
            continue

        # 3) Codex OAuth
        bundle = login_codex_via_browser(email, password, mail_client=free_mail)
        if not bundle:
            failed.append({"email": email, "reason": "codex_oauth_failed"})
            free_mail.delete_account(account_id)
            continue

        # 4) 防御兜底：plan_type 必须是 free
        if bundle.get("plan_type") != "free":
            failed.append({"email": email, "reason": "plan_type_mismatch"})
            free_mail.delete_account(account_id)
            continue

        # 5) 落盘
        auth_file = save_auth_file(bundle)
        add_free_account(email=email, password=password,
                         cloudmail_account_id=account_id,
                         auth_file=str(auth_file),
                         plan_type=bundle["plan_type"])

        # 6) 推 CPA（失败不视为整体失败：保留本地记录，下次 sync 会补上）
        try:
            upload_to_cpa(auth_file)
        except Exception as exc:
            logger.warning("[Free] CPA 上传失败但保留本地: %s (%s)", email, exc)

        succeeded.append(email)

    except Exception as exc:
        failed.append({"email": email if 'email' in locals() else None,
                       "reason": f"unexpected: {exc}"})
        if account_id:
            try:
                free_mail.delete_account(account_id)
            except Exception:
                pass

return {"succeeded": succeeded, "failed": failed}
```

### 单条删除

```python
# DELETE /api/free/accounts/{email}  →  202 + task_id
# 任务体（幂等）:

acc = find_free_account(email)
if not acc:
    raise NotFound(404)

# 各步独立 try/except，已不存在视为成功
auth_path = acc.get("auth_file")
if auth_path:
    delete_from_cpa(Path(auth_path).name)        # CPA
    Path(auth_path).unlink(missing_ok=True)      # 本地 auth

if acc.get("cloudmail_account_id"):
    free_mail.delete_account(acc["cloudmail_account_id"])  # CloudMail

delete_free_account(email)                       # 摘除条目
```

### 单条刷新 Codex token

```python
# POST /api/free/accounts/{email}/refresh  →  202 + task_id

acc = find_free_account(email)
bundle = login_codex_via_browser(acc["email"], acc["password"],
                                 mail_client=free_mail)
if not bundle:
    update_free_account(email, last_error="codex_oauth_failed")
    raise TaskFailed

if bundle.get("plan_type") != "free":
    # 不应发生，但记录
    update_free_account(email, last_error="plan_type_mismatch")
    raise TaskFailed

new_path = save_auth_file(bundle)         # 同名覆盖
upload_to_cpa(new_path)                   # CPA 覆盖
update_free_account(email,
                    auth_file=str(new_path),
                    last_refreshed_at=time.time(),
                    last_error=None)
```

## CPA 同步改动

`sync_to_cpa()`（cpa_sync.py:518）现状：只把 `accounts.json` 中 `status==active` 的 auth 文件作为"应当存在于 CPA"的集合，CPA 中本地已知 email 但不在该集合的会被删除。

**改动**：在构建 `active_files` 和 `local_emails` 时合并 `free_accounts.json` 全部条目。

```python
# 合并后逻辑（伪代码）
active_files = {}
local_emails = set()

# Team
for acc in load_accounts():
    if acc["status"] == STATUS_ACTIVE and acc.get("auth_file"):
        local_emails.add(acc["email"].lower())
        path = Path(acc["auth_file"])
        if path.exists():
            active_files[path.name] = path

# Free（无状态机，全部都属于"应当上传"）
for facc in load_free_accounts():
    if facc.get("auth_file"):
        local_emails.add(facc["email"].lower())
        path = Path(facc["auth_file"])
        if path.exists():
            active_files[path.name] = path

# 后续上传/删除逻辑保持不变
```

**边界条件**：
- 同 email 同时在两表 → email 唯一性校验已阻止
- Free 条目 `auth_file` 不在 → 跳过上传，但 email 仍计入 `local_emails`，避免 CPA 上同名文件被误删

## API 契约

| 方法 | 路径 | 同步/异步 | 说明 |
|------|------|------|------|
| GET | `/api/free/accounts` | 同步 | 列表（含 `auth_file_exists`），不返回 password |
| POST | `/api/free/accounts` | 异步 (202+task_id) | 体 `{count: N}`，1≤N≤50 |
| DELETE | `/api/free/accounts/{email}` | 异步 (202+task_id) | 串行删 CPA + auth + CloudMail + 条目 |
| POST | `/api/free/accounts/{email}/refresh` | 异步 (202+task_id) | 重跑 OAuth → 覆盖 auth → 重传 CPA |

**响应格式**：

```json
// GET 响应
[
  {
    "email": "...",
    "plan_type": "free",
    "created_at": 1730000000.0,
    "last_refreshed_at": null,
    "last_error": null,
    "auth_file_exists": true
  }
]

// 批量创建任务结果
{
  "succeeded": ["email1", "email2"],
  "failed": [
    {"email": "email3", "reason": "codex_oauth_failed"},
    {"email": "email4", "reason": "register_failed_3x"}
  ]
}
```

**未配置降级**：未设置 `CLOUDMAIL_FREE_DOMAIN` 时，`/api/free/*` 全部返回 503 `{"enabled": false, "reason": "CLOUDMAIL_FREE_DOMAIN not set"}`。前端检测到 `enabled=false` 时整个 Free 页面变灰、给出引导文案。

**鉴权与并发**：复用现有 `api.py` 的 Bearer/`?key=` 中间件 + 单 Playwright 锁。任何使用浏览器的端点遇到锁占用返回 409。

## CLI 子命令

```bash
uv run autoteam add-free [N]    # N 默认 1，最大 50
```

实现：

```python
# manager.py
sub.add_parser("add-free", help="批量注册 Free 账号").add_argument(
    "count", type=int, nargs="?", default=1, help="数量（默认 1，最大 50）"
)

elif args.command == "add-free":
    cmd_add_free(args.count)

def cmd_add_free(count: int):
    if not CLOUDMAIL_FREE_DOMAIN:
        logger.error("[Free] 未配置 CLOUDMAIL_FREE_DOMAIN")
        sys.exit(1)
    if not (1 <= count <= 50):
        logger.error("[Free] 数量需在 1..50")
        sys.exit(1)

    result = create_free_accounts_batch(count)  # 来自 free_register.py
    sync_to_cpa()
    logger.info("[Free] 完成: 成功 %d, 失败 %d",
                len(result["succeeded"]), len(result["failed"]))
```

## 前端 UI

新页面 `FreePage.vue`，参考 `PoolPage.vue` 风格：

```
┌──────────────────────────────────────────────┐
│  Free 账号管理                  [刷新列表]      │
│                                                │
│  数量: [_5_]  [批量创建]   任务: 进行中…        │
├──────────────────────────────────────────────┤
│ 邮箱            创建时间    刷新时间   auth  操作│
│ tmp-a@xx.com    04-29 10:30  --        ✅   [刷新][删除]│
│ tmp-b@xx.com    04-29 10:32  04-29...  ✅   [刷新][删除]│
│ tmp-c@xx.com    04-29 10:35  --        ❌   [刷新][删除]│
└──────────────────────────────────────────────┘
```

**交互**：

- **批量创建**：输入 1-50 → 提交 → 顶部"任务进行中"，轮询 task → 完成后 toast `succeeded N / failed M`，自动刷列表
- **单条刷新**：触发 task；运行期间该行操作按钮 disable
- **单条删除**：弹确认（"将同时删除 CPA / 本地 auth / CloudMail 临时邮箱"）→ 触发 task

**未配置降级**：`enabled=false` 时整个页面置灰，提示"请在 .env 配置 `CLOUDMAIL_FREE_DOMAIN`"。

**Sidebar / 路由**：在 `Sidebar.vue` 紧跟 PoolPage 后加入口；按 `App.vue` 现有视图切换模式接入。

## 错误处理与边界

| 失败点 | 处理 |
|--------|------|
| CloudMail 创建邮箱失败 | 抛异常给上层；该次失败 |
| Cloudflare 卡死 / 注册 3 次重试失败 | 删 CloudMail 邮箱，continue |
| Codex OAuth 失败 | 删 CloudMail 邮箱，不写 free_accounts，continue |
| `bundle.plan_type != "free"` | 删 CloudMail 邮箱，不写 free_accounts，continue（提醒用户域名错） |
| Codex 成功但 CPA 上传失败 | **保留 free_accounts 记录**，下次 sync 自动补上 |

**删除接口的幂等**：CPA / auth / CloudMail 任何一步遇到"已不存在"都视为成功；只有条目找不到才 404。

**刷新接口的失败**：浏览器 OAuth 失败 → 写 `last_error`，**不**删旧 auth 文件，返回任务 failed。

## 测试计划

### 单元测试（新增）

- `tests/unit/test_free_accounts.py`
  - CRUD 操作（tmp_path 隔离）
  - email 唯一性校验（与 accounts.json 互斥）
- `tests/unit/test_free_register.py`
  - mock 浏览器流程，测编排逻辑
  - Codex OAuth 成功 → 完整写盘 + CPA
  - Codex OAuth 失败 → 不写 free_accounts，调 `mail_client.delete_account`
  - `plan_type=team` → 走回滚分支
  - 批量循环：1 成功 + 1 失败 → 结果体正确
- `tests/unit/test_cpa_sync.py`（扩展）
  - 同时有 active team + free → 都进 active_files
  - free 条目缺 auth_file → 跳过上传但保留 local_emails

### 手动验证（必做）

1. 配 `CLOUDMAIL_FREE_DOMAIN=@another-domain.com`
2. CLI: `uv run autoteam add-free 1` → 验证 plan_type=free 的 auth + CPA 上传
3. CLI: `uv run autoteam add-free 3` → 验证批量串行 + 失败不阻塞
4. Web: `uv run autoteam api` → Free 页面创建 2 个 / 刷新 1 个 / 删除 1 个，验证 CPA 同步
5. **关键回归**：`autoteam rotate` 跑一次，确认 Team 轮转完全无影响

## 工作量估算

| 模块 | 大致行数 | 风险 |
|------|---------|------|
| `free_accounts.py` | ~80 | 低 |
| `free_register.py` | ~150 | 中（错误处理分支多） |
| `cloudmail.py` | ~5 | 低 |
| `config.py` | ~2 | 低 |
| `cpa_sync.py` | ~15 | 中（边界条件易回归） |
| `manager.py` | ~30 | 低 |
| `api.py` | ~80 | 低 |
| `FreePage.vue` | ~250 | 中 |
| `Sidebar.vue` / `App.vue` / `api.js` | ~30 | 低 |
| 单元测试 | ~250 | 低 |

## 主要风险

- **`_register_direct_once` 对 Free 的兼容性**：理论上"Accept invite"分支已在 try/except，对 Free 是 no-op，但实际 ChatGPT Free 注册的最终落地页 URL 与"自动加入 workspace"略有不同；实施时需要实际跑一遍验证 success 判定还成立。
- **CPA 同步的合并逻辑**：要确保不误删 Team 的非 active auth（这块有 standby/exhausted 概念）。`local_emails` 与 `active_files` 必须正确区分。
- **域名隔离的用户责任**：CloudMail 的 Team domain 与 Free domain 必须真不同；UI 与 `.env.example` 都要给清晰说明。`plan_type != free` 的兜底是最后一道防线。

## 配置示例

`.env` 增量：

```
# Free 账号注册的独立域名（必须与 CLOUDMAIL_DOMAIN 不同，否则会被自动加入 Team）
CLOUDMAIL_FREE_DOMAIN=@freedom-only.example.com
```
