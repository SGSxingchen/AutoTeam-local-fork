# Outlook / Hotmail 邮箱池接入设计

| 项 | 值 |
|---|---|
| 起草日期 | 2026-05-01 |
| 适用范围 | Free 账号注册流程(`free_register.py`)的邮箱来源切换 |
| 不在范围 | Team 邀请流程(`invite.py`)、Codex 主账号同步、Team 池轮转 |
| 状态 | Draft — 待用户复核 |

## 1. 背景与目标

### 1.1 现状

AutoTeam 现有的 Free 账号注册流程依赖 **CloudMail 临时邮箱**:

```
free_register.create_one_free_account
  └─ make_free_mail_client()                 # 硬编码 CloudMailClient
       └─ mail_client.create_temp_email()    # CloudMail 创建一次性临时邮箱
       └─ _register_direct_once(...)         # Playwright 在 chatgpt.com 直接注册
       └─ login_codex_via_browser(...)       # Codex OAuth,邮件 OTP 仍走 mail_client
       └─ save_auth_file + upload_to_cpa
```

CloudMail 临时邮箱注册成功率高、批量便宜,但存在以下限制:

- 域名一旦被 OpenAI 标记,该域下所有新邮箱都成废卡。
- CloudMail 服务可用性是单点。

### 1.2 目标

引入 **Outlook / Hotmail 邮箱池** 作为 Free 注册的备选邮箱来源:

- 用户在市场上以 `email----password----client_id----refresh_token` 4 段格式批量购买 Outlook 账户。
- Web UI 提供"邮箱池"页面用于批量导入、查看、单条测试与删除。
- Settings 页提供「Free 注册邮箱提供商」全局开关,切换 CloudMail / Outlook。
- 已实现的 CloudMail 流程不动一行代码;新增 `OutlookMailClient` 鸭子类型实现相同方法签名。
- Team 邀请流程(`invite.py`)完全不动。

### 1.3 非目标

- **不**支持自有 Outlook 账户的交互式 OAuth 授权(用户在 Azure 注册的应用本设计用不上)。
- **不**支持 Team 邀请流程使用 Outlook 邮箱。
- **不**做池账户的"用完后回收复用"—— 一旦 claim 后注册过 ChatGPT,该 Outlook 账户永久标记 used,不再 claim。
- **不**做 OAuth Authorization Code Flow / Playwright 登录自动化授权 —— 完全依赖卖家提供的 refresh_token。

## 2. 总体架构

```
┌─ Web 设置页 ──────────────────────────┐
│  Free 注册邮箱提供商: ○CloudMail ○Outlook │  ← 全局开关
└────┬─────────────────────────────────┘
     │ runtime_config: mail_provider = cloudmail | outlook
     ↓
┌─ free_register.py (修改 ~10 行) ──────┐
│  make_free_mail_client():              │
│    if mail_provider == 'outlook':      │
│      return OutlookMailClient()        │
│    return CloudMailClient(domain=...)  │
└────┬─────────────────────────────────┘
     │
     ├──► CloudMailClient (现有,不动)
     │
     └──► OutlookMailClient (新)
              ├─ outlook_pool.py     池 CRUD,文件锁,outlook_pool.json
              ├─ outlook_oauth.py    refresh_token → access_token,带缓存
              ├─ outlook_imap.py    XOAUTH2 短连接 + 邮件抓取
              └─ mail_utils.py       (新) 抽出 extract_verification_code 等纯函数
                                     CloudMail 也复用
```

### 2.1 关键设计决策

- **不引入 `MailProvider` Protocol / ABC**。CloudMailClient 已有的方法签名即事实接口;OutlookMailClient 实现相同方法名,鸭子类型即可。YAGNI。
- **Team 邀请流程(`invite.py`)零改动**。
- **CloudMailClient 零改动**(除了 import `mail_utils` 的小调整)。
- **`OutlookMailClient.create_temp_email()` 的语义重定义**:不"创建",而是"从池里 claim 一个 status=available 的账户,标记为 in_use,返回 `(email, email)`"。pool 的主键就是 email,占位 cloudmail_account_id 字段。
- **`delete_account(account_id)` 的 Outlook 语义**:回滚时调用,把池记录标记为 `error`(不放回 `available` —— 一旦在 ChatGPT 那侧尝试过注册,可能留下残留状态,再次 claim 风险高)。
- **client_id 跟着账户存**:虽然主流卖家都用同一个公共 ID `9e5f94bc-e8a4-4e73-b8be-63364c29d753`,但显式持久化以便未来 Microsoft 收紧时无缝换 ID。

## 3. 数据模型

### 3.1 `outlook_pool.json` 单条记录

```json
{
  "email": "qpzst27553129@hotmail.com",
  "password": "voxuh78829745",
  "client_id": "9e5f94bc-e8a4-4e73-b8be-63364c29d753",
  "refresh_token": "M.C528_BL2.0.U.-CjkIki!...EyI$",
  "aux_email": null,
  "status": "available",
  "added_at": 1730419200,
  "claimed_at": null,
  "used_at": null,
  "registered_chatgpt_email": null,
  "last_error": null
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `email` | str | 主键。规范化为小写。 |
| `password` | str | 邮箱密码。**当前流程不用**,为兼容卖家格式而存,留作未来手动登录场景。 |
| `client_id` | str | OAuth client_id,主流公共值见上。 |
| `refresh_token` | str | OAuth refresh_token,Microsoft 偶尔轮换,响应里返回新值时立刻持久化覆盖。 |
| `aux_email` | str \| null | 5 段格式时存,4 段格式留 null。当前流程不用。 |
| `status` | enum | `available` / `in_use` / `used` / `error` |
| `added_at` | int | UNIX 秒,导入时刻。 |
| `claimed_at` | int \| null | 最近一次 claim 时刻。 |
| `used_at` | int \| null | 转 `used` 状态的时刻。 |
| `registered_chatgpt_email` | str \| null | 这个 Outlook 邮箱注册出来的 ChatGPT 账号(通常等于 `email` 自己,但显式存以便未来引入"用 Outlook A 注册 ChatGPT B"的场景)。 |
| `last_error` | str \| null | 最近一次错误描述,UI hover 显示。 |

### 3.2 状态机

```
                    ┌──────────────────┐
                    │  (导入)            │
                    ↓                   │
                available ─claim────→ in_use ─注册成功─→ used
                    ↑                   │
                    │ reset(UI)         ├─ 注册失败 ─→ error
                    │                   │
                    └─────────────── error ←─ token 失效
```

- `claim_one()` 原子: 找最早 `available`,改成 `in_use`,保存,返回。
- `mark_used(email, registered_chatgpt_email)`: `in_use` → `used`,填 `used_at` 和 ChatGPT 邮箱。
- `mark_error(email, reason)`: 任意状态 → `error`,填 `last_error`。
- `reset(email)`(UI 操作): `error` 或 `in_use` → `available`,清 `last_error`。**`used` 不能重置**(避免重复消耗 ChatGPT 那边已留档的邮箱)。允许 `in_use` 重置是为了兜底"任务异常未及时释放"或"验证码超时但用户判断邮箱仍可用"的场景。
- `release(email)`(异常兜底): `in_use` → `available`,极少用,只在 claim 后立刻抛异常没机会执行后续逻辑时调用。
- `delete(email)`: 物理删除该条。

### 3.3 解析器

只支持 `----` 作为分隔符。按字段数分支:

| 段数 | 含义 |
|---|---|
| 4 | `email----password----client_id----refresh_token` ← 主流 |
| 5 | `email----password----aux_email----client_id----refresh_token` ← 部分卖家附带辅助邮箱 |
| 其它 | 报错并标行号,跳过该行 |

字段验证:
- email 必须含 `@`,规范化为小写。
- client_id 必须是 UUID 格式。
- refresh_token 长度 > 100(经验阈值,过短的多半是占位)。
- 不验证 password 格式(卖家格式各异)。

去重逻辑(导入时):
- 已存在于 `outlook_pool.json` → 跳过,计入 skipped。
- 已存在于 `free_accounts.json` 的 `email` 字段 → 跳过(避免与 Free 已注册账号冲突)。
- 已存在于 `accounts.json` 的 `email` 字段 → 跳过(避免与 Team 池冲突)。

## 4. 模块接口

### 4.1 `src/autoteam/outlook_pool.py`

```python
def load_pool() -> list[dict]: ...
def save_pool(rows: list[dict]) -> None: ...
def import_from_text(text: str) -> dict:
    """返回 {imported: int, skipped: int, errors: list[{line, reason}]}"""

def claim_one() -> dict | None:
    """文件锁内: 按 added_at 升序找首个 status=available 的记录 → 标 in_use 并填 claimed_at → 保存 → 返回。无可用返回 None。"""

def mark_used(email: str, registered_chatgpt_email: str) -> None: ...
def mark_error(email: str, reason: str) -> None: ...
def reset(email: str) -> bool: ...
def release(email: str) -> None: ...
def delete(email: str) -> bool: ...

def find(email: str) -> dict | None: ...
def stats() -> dict:
    """返回 {total, available, in_use, used, error}"""

def update_refresh_token(email: str, new_refresh_token: str) -> None:
    """OAuth 响应里有新的 refresh_token 时调用。"""
```

文件 IO 全部用 `fcntl.flock` 包住,避免 Web UI 导入与后台 claim 并发写。

### 4.2 `src/autoteam/outlook_oauth.py`

```python
class OutlookTokenRevokedError(Exception): ...
class OutlookOAuthError(Exception): ...

def get_access_token(record: dict) -> str:
    """从 record 的 refresh_token 换 access_token,内存缓存 1h。
    
    若响应包含新 refresh_token,调用 outlook_pool.update_refresh_token。
    invalid_grant 时调用 outlook_pool.mark_error 并抛 OutlookTokenRevokedError。
    """
```

实现:
- HTTP POST `https://login.microsoftonline.com/common/oauth2/v2.0/token`
- form-urlencoded body: `client_id`, `grant_type=refresh_token`, `refresh_token`, `scope=https://outlook.office.com/IMAP.AccessAsUser.All offline_access`
- 缓存: 进程内 dict `{email: (access_token, expiry_ts)}`,失效阈值 = expires_in - 60s。
- 不持久化 access_token(进程重启重换即可,成本可忽略)。

### 4.3 `src/autoteam/outlook_imap.py`

```python
class OutlookIMAP:
    """单个 Outlook 账户的短连接 IMAP 客户端。

    用法:
        with OutlookIMAP(email, access_token) as imap:
            emails = imap.search_emails(sender_keyword="openai", limit=10)
    """
    def __init__(self, email: str, access_token: str): ...
    def __enter__(self): ...
    def __exit__(self, *exc): ...

    def search_emails(self,
                      sender_keyword: str | None = None,
                      since_seconds: int | None = None,
                      limit: int = 10) -> list[dict]:
        """返回 CloudMail 兼容字段名的邮件 dict 列表。"""
```

实现:
- `imaplib.IMAP4_SSL("outlook.office365.com", 993)`
- XOAUTH2 鉴权:
  ```python
  auth_string = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
  imap.authenticate("XOAUTH2", lambda _: auth_string.encode())
  ```
- `imap.select("INBOX")` → `imap.search(None, *criteria)` 拼接 `FROM`/`SINCE`。
- `imap.fetch(uid, "(RFC822)")` → `email.message_from_bytes()` 解析。
- 输出字段名对齐 CloudMail:
  ```python
  {
    "emailId": uid,           # IMAP UID,用作去重 key
    "subject": ...,
    "sendEmail": from_addr,   # 注意驼峰
    "text": plain_text_body,
    "content": html_body,
    "accountId": email,       # 占位
  }
  ```

### 4.4 `src/autoteam/mail_utils.py` (新)

把 `cloudmail.py` 里两个静态方法搬过来,改为模块级纯函数:

```python
def extract_verification_code(email_data: dict) -> str | None: ...
def extract_invite_link(email_data: dict) -> str | None: ...
def html_to_visible_text(html: str) -> str: ...
```

CloudMailClient 改 import 引用,功能等价,无行为变化。OutlookMailClient 也用这套。

### 4.5 `src/autoteam/outlook_mail.py` (新,鸭子类型实现)

```python
class OutlookMailClient:
    """与 CloudMailClient 鸭子类型兼容的 Outlook 邮箱客户端。"""

    def login(self) -> None:
        """noop。保留方法以兼容 free_register 的调用约定。"""

    def create_temp_email(self, prefix: str | None = None) -> tuple[str, str]:
        """从池里 claim 一个,返回 (email_as_account_id, email)。
        
        prefix 参数被忽略 —— 池里邮箱固定。
        """

    def search_emails_by_recipient(self, to_email, size=10, account_id=None) -> list[dict]:
        """转发到 IMAP。"""

    def delete_account(self, account_id: str) -> dict:
        """account_id 在 Outlook 语义下就是 email。回滚 → mark_error。"""

    def delete_emails_for(self, to_email: str) -> int:
        """noop,IMAP 删邮件意义不大;返回 0。"""

    # extract_verification_code / extract_invite_link
    # → 透传到 mail_utils
```

### 4.6 `src/autoteam/free_register.py` 的修改点

```python
# 原:
def make_free_mail_client():
    domain = get_cloudmail_free_domain()
    if not domain:
        raise RuntimeError("CLOUDMAIL_FREE_DOMAIN not configured")
    client = CloudMailClient(domain=domain)
    client.login()
    return client

# 改后:
def make_free_mail_client():
    from autoteam.runtime_config import get_mail_provider

    if get_mail_provider() == "outlook":
        from autoteam.outlook_mail import OutlookMailClient
        return OutlookMailClient()

    domain = get_cloudmail_free_domain()
    if not domain:
        raise RuntimeError("CLOUDMAIL_FREE_DOMAIN not configured")
    client = CloudMailClient(domain=domain)
    client.login()
    return client
```

`create_one_free_account` 内的成功分支额外加一行:

```python
# 在 add_free_account 之后,如果当前 provider 是 outlook,标 used:
if get_mail_provider() == "outlook":
    from autoteam.outlook_pool import mark_used
    mark_used(email, registered_chatgpt_email=email)
```

回滚分支不变 —— `_rollback_cloudmail` 调用 `mail_client.delete_account(account_id)`,Outlook 实现里就是 `mark_error`。

## 5. Web UI

### 5.1 邮箱池页面 (`web/src/components/MailPoolPage.vue`)

路由 `/mail-pool`,加入 `Sidebar.vue`。

**布局**:
```
┌─ 顶部统计卡片 ────────────────────────────────────┐
│  总数 124    可用 89    使用中 0    已用 32    异常 3 │
└──────────────────────────────────────────────────┘

┌─ 批量导入 (折叠,默认收起) ────────────────────────┐
│  [textarea: 12 行高,粘贴 4 段格式]                  │
│  placeholder: email----password----client_id----refresh_token │
│  [导入] [清空]                                      │
└──────────────────────────────────────────────────┘

┌─ 账户列表 ───────────────────────────────────────┐
│  筛选: [全部] [可用] [已用] [异常]   搜索: [____]    │
│                                                    │
│  邮箱            状态     添加     已注册 ChatGPT  操作 │
│  abc@hotmail.com 🟢可用   2小时前  -              [测试][删除] │
│  def@hotmail.com 🔵使用中 1分钟前  -              [删除] │
│  ghi@hotmail.com ⚪已用   昨天     ghi@hotmail.com -    │
│  jkl@hotmail.com 🔴异常   3天前    -              [重置][删除] │
│                                                    │
│  分页: < 1 2 3 ... >                               │
└──────────────────────────────────────────────────┘
```

**导入交互**:
- 点击"导入"后同步等待响应(本地操作快)。
- toast: `成功 87 / 跳过(已存在)12 / 解析失败 1`。
- 失败行展开显示行号 + reason(`第 14 行: client_id 不是 UUID 格式`)。

**单条操作**:
- 「测试」: 调 `POST /api/outlook/pool/test/{email}`,同步等待 ~3s,弹 toast 显示连接结果。**不**改 status。
- 「重置」: `error` 或 `in_use` 状态可见,确认弹窗 → `POST /api/outlook/pool/reset/{email}`。`used` 不显示。
- 「删除」: 确认弹窗 → `DELETE /api/outlook/pool/{email}`。

### 5.2 Settings 页改动 (`web/src/components/Settings.vue`)

新增「Free 注册」分区(若已有则在其内追加):

```
┌─ Free 注册 ───────────────────────────────┐
│  邮箱提供商                                │
│   ◉ CloudMail        (域名 xxxx.com)      │
│   ○ Outlook          (池可用 89 个 →跳转) │
│                                           │
│  CloudMail Free 域名:  [xxxx.com_____]    │
└──────────────────────────────────────────┘
```

切到 Outlook 但池里 `available=0` 时,选项下方红字提示「池已空,请先导入账户」并禁用保存按钮。

### 5.3 Dashboard 卡片(选做)

`Dashboard.vue` 顶部状态行加一个"Outlook 池"小卡片,显示 `可用 89 / 总 124`,点击跳邮箱池页。**实施后置**,不阻塞主功能。

## 6. API 端点

全部要 Bearer auth,挂在 `src/autoteam/api.py`。返回值用现有 ApiResponse 风格(参考 `/api/free/*`)。

| 方法 | 路径 | body / query | 返回 |
|---|---|---|---|
| `GET` | `/api/outlook/pool` | `?status=&q=&page=1&size=50` | `{rows, total, stats}` |
| `POST` | `/api/outlook/pool/import` | `{text: str}` | `{imported, skipped, errors: [{line, reason}]}` |
| `POST` | `/api/outlook/pool/test/{email}` | — | `{ok: bool, error?: str}` |
| `POST` | `/api/outlook/pool/reset/{email}` | — | `{ok}` |
| `DELETE` | `/api/outlook/pool/{email}` | — | `{ok}` |
| `GET` | `/api/outlook/pool/stats` | — | `{total, available, in_use, used, error}` |

「测试」和「导入」是同步调用,不进后台任务队列(本地 IO + 单次 IMAP 连接,几秒内返回)。

`runtime_config` 增加 `mail_provider` 字段(取值 `cloudmail` | `outlook`,默认 `cloudmail`),通过 `GET / PUT /api/runtime-config` 现有端点读写。

## 7. 错误处理

| 场景 | 行为 |
|---|---|
| 池空(`claim_one()` 返回 None) | `OutlookMailClient.create_temp_email` 抛 `RuntimeError("Outlook 池里没有可用账户")`,Free 注册任务返回 failed,reason 透传到 UI |
| refresh_token 被吊销 (`invalid_grant`) | `mark_error(email, "refresh_token_revoked")`;抛 `OutlookTokenRevokedError`;Free 注册任务整体失败(**不自动 retry 下一个池账户**,避免静默消耗多个) |
| OAuth 网络异常(非 4xx) | 抛 `OutlookOAuthError`,**不**改 status,任务失败,下次 claim 还能用 |
| IMAP 连接 / SELECT 失败 | 重试 3 次,仍失败 → `mark_error(email, "imap_connect_failed")`,任务失败 |
| IMAP 鉴权失败(token 过期但缓存还认为有效) | 缓存清除,重新换 access_token 再试一次;仍失败 → `mark_error` |
| 验证码邮件超时未到(超过 `MAIL_TIMEOUT`) | 任务返回 failed,**保持 in_use**(不 mark_error,人工排查后可手动 reset 回 available) |
| 注册成功 | `mark_used(email, registered_chatgpt_email=email)` |

## 8. 安全与运维考量

- **`outlook_pool.json` 含敏感数据**(密码 + refresh_token)。和 `accounts.json` / `free_accounts.json` 保密等级相同,Docker volume 挂载即可,不额外加密。
- **refresh_token 不写日志**。日志中只显示前后 8 字符 + `...`。
- **API 端点全部 Bearer auth**(沿用现有 `API_KEY`)。
- **导入接口不限速**,但解析失败行计入响应,不会因为单条数据破坏整个 batch。
- **没有审计日志**(项目其它部分也没有,保持一致)。

## 9. 测试策略

项目当前无自动化测试套件(`CLAUDE.md` 明确说明)。本设计跟随项目惯例:

- **手动 happy path**:
  1. 准备 5 个真实 Outlook 账户(已知 refresh_token 有效)。
  2. Web UI 导入 → 检查统计 5 个 available。
  3. Settings 切到 Outlook → 触发一次 Free 注册。
  4. 检查池中该账户变 used,`free_accounts.json` 新增一条。
  5. 检查 CPA 上传成功。

- **手动 error path**:
  1. 导入 1 个故意写错 refresh_token 的账户 → 触发 Free 注册 → 期望: 该账户 mark_error,任务 failed,UI 显示 reason。
  2. 池空时切到 Outlook 触发注册 → 期望: 任务立刻 failed,UI 提示池空。
  3. Settings 切回 CloudMail 走原流程 → 期望: 行为完全等同当前。

- **解析器单元覆盖**(可选,作为 ruff/pyright 之外唯一的"半自动测试"): 在 `outlook_pool.py` 末尾加 `if __name__ == "__main__":` 块,跑几个 fixture 字符串验证 imported/skipped/errors 计数。

## 10. 迁移与回滚

- **零数据迁移**: 全新文件 `outlook_pool.json`,既有 `accounts.json` / `free_accounts.json` 不动。
- **回滚**: Settings 切回 CloudMail,Outlook 流程完全闲置。要彻底卸载就删除新文件 + 新模块 + Web UI 路由,修复 `make_free_mail_client` 回原状。所有改动局限在新文件 + 1 处 `make_free_mail_client` 修改 + 1 处 Settings UI。

## 11. 范围边界与遗留事项

**当前不做,留作后续**:

1. **自有少量 Outlook 账户的交互式 OAuth**(用户在 Azure 注册的 `e045aaa2-...` App)。如果未来要做,新增第二种导入入口"用我的 Azure App 做 OAuth 授权"即可,池数据结构兼容(只是 client_id 字段填用户自己的)。
2. **Outlook 账户在 Team 邀请流程中使用**。若未来要做,`invite.py::run` 里把 `mail_client = CloudMailClient()` 改成走 provider 选择即可。
3. **多副本部署下的池并发**。当前 `fcntl.flock` 仅保护单进程内的多线程并发(FastAPI + 后台任务线程),如果未来出现多副本部署,需要换成 Redis 分布式锁或外部数据库。
4. **refresh_token 主动续期**。当前是懒求值(用到时才换 access_token);若卖家提供的 refresh_token 有 90 天闲置失效,长期不用的池账户可能批量过期。若发现这问题,加一个 cron 任务定期 ping 一次。
5. **Dashboard 的 Outlook 池卡片**(§5.3),非阻塞,可后置。

## 12. 实现文件清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/autoteam/outlook_pool.py` | 新增 | 池 CRUD + 文件锁 |
| `src/autoteam/outlook_oauth.py` | 新增 | refresh_token → access_token,缓存 |
| `src/autoteam/outlook_imap.py` | 新增 | IMAP XOAUTH2 短连接 |
| `src/autoteam/outlook_mail.py` | 新增 | OutlookMailClient 鸭子类型 |
| `src/autoteam/mail_utils.py` | 新增 | 抽 extract_verification_code 等纯函数 |
| `src/autoteam/cloudmail.py` | 改 | 改用 mail_utils 的纯函数;不变行为 |
| `src/autoteam/free_register.py` | 改 | `make_free_mail_client` 加 provider 分支;成功分支加 mark_used |
| `src/autoteam/runtime_config.py` | 改 | 新增 `mail_provider` 字段 |
| `src/autoteam/api.py` | 改 | 新增 6 个 Outlook 池端点 |
| `web/src/components/MailPoolPage.vue` | 新增 | 邮箱池页面 |
| `web/src/components/Settings.vue` | 改 | 新增 Free 注册 / 邮箱提供商分区 |
| `web/src/components/Sidebar.vue` | 改 | 新增邮箱池入口 |
| `web/src/api.js` | 改 | 新增 6 个端点的 fetch 函数 |
| `web/src/App.vue` | 改 | 新增路由 `/mail-pool` |

预计代码量:Python ~600 行(含注释和 docstring),Vue ~400 行。
