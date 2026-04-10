"""ChatGPT Team API 客户端 - 通过 Playwright 绕过 Cloudflare 调用内部 API"""
import autoteam.display  # noqa: F401

import json
import time
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright

from autoteam.config import CHATGPT_ACCOUNT_ID

PROJECT_ROOT = Path(__file__).parent.parent.parent
BASE_DIR = PROJECT_ROOT
SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"


class ChatGPTTeamAPI:
    """通过 Playwright 浏览器内 fetch 调用 ChatGPT 内部 API"""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.access_token = None
        self.account_id = CHATGPT_ACCOUNT_ID
        self.oai_device_id = str(uuid.uuid4())

    def start(self):
        """启动浏览器，注入 cookies，获取 access token"""
        SCREENSHOT_DIR.mkdir(exist_ok=True)

        # 读取 session cookies
        session_file = BASE_DIR / "session"
        if not session_file.exists():
            raise FileNotFoundError("请先把 ChatGPT session token 写入 ./session 文件")
        session_token = session_file.read_text().strip()

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        )
        self.page = self.context.new_page()

        # 先访问 chatgpt.com 过 Cloudflare
        print("[ChatGPT] 访问 chatgpt.com 过 Cloudflare...")
        self.page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        for i in range(12):
            html = self.page.content()[:1000].lower()
            if "verify you are human" not in html and "challenge" not in self.page.url:
                break
            print(f"  等待 Cloudflare... ({i*5}s)")
            time.sleep(5)

        # 注入 session cookie（分片格式）
        # 检测 token 长度，超过 3800 就分片
        if len(session_token) > 3800:
            part0 = session_token[:3800]
            part1 = session_token[3800:]
            cookies = [
                {
                    "name": "__Secure-next-auth.session-token.0",
                    "value": part0,
                    "domain": "chatgpt.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
                {
                    "name": "__Secure-next-auth.session-token.1",
                    "value": part1,
                    "domain": "chatgpt.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
            ]
        else:
            cookies = [{
                "name": "__Secure-next-auth.session-token",
                "value": session_token,
                "domain": "chatgpt.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }]

        # 加上 account cookie
        cookies.append({
            "name": "_account",
            "value": self.account_id,
            "domain": "chatgpt.com",
            "path": "/",
            "secure": True,
            "sameSite": "Lax",
        })
        cookies.append({
            "name": "oai-did",
            "value": self.oai_device_id,
            "domain": "chatgpt.com",
            "path": "/",
            "secure": True,
            "sameSite": "Lax",
        })

        self.context.add_cookies(cookies)
        print("[ChatGPT] 已注入 session cookies")

        # 获取 access token
        self._fetch_access_token()

        # 自动检测 account_id 和 workspace_name（如果未配置）
        self._auto_detect_workspace()

    def _auto_detect_workspace(self):
        """自动获取 workspace 名称（需要 CHATGPT_ACCOUNT_ID 已配置）"""
        from autoteam import config

        if config.CHATGPT_WORKSPACE_NAME:
            return  # 已配置

        if not config.CHATGPT_ACCOUNT_ID:
            print("[ChatGPT] ⚠️  请在 .env 中配置 CHATGPT_ACCOUNT_ID")
            return

        # 用 account_id 调 API 获取 workspace 信息
        result = self._api_fetch("GET", f"/backend-api/accounts/{self.account_id}/invites")
        # invites 接口不返回名称，换用 settings
        result = self.page.evaluate('''async (accountId) => {
            try {
                const resp = await fetch("/backend-api/accounts/" + accountId + "/settings", {
                    headers: { "chatgpt-account-id": accountId }
                });
                return await resp.json();
            } catch(e) { return null; }
        }''', self.account_id)

        if result and result.get("workspace_name"):
            config.CHATGPT_WORKSPACE_NAME = result["workspace_name"]
            print(f"[ChatGPT] 自动检测到 workspace 名称: {result['workspace_name']}")
            return

        # fallback: 从 admin 页面提取 workspace 名称
        try:
            self.page.goto("https://chatgpt.com/admin", wait_until="domcontentloaded", timeout=30000)
            import time as _t
            _t.sleep(5)
            # workspace 名称通常是 admin 页面侧边栏中的大标题
            name = self.page.evaluate('''() => {
                // 找侧边栏或页面标题中的 workspace 名称
                // admin 页面结构：侧边栏有 workspace 名称作为标题
                const headings = document.querySelectorAll('h1, h2, h3, [class*="title"], [class*="name"]');
                for (const h of headings) {
                    const text = h.textContent.trim();
                    // 跳过通用标题
                    if (text && text.length < 50 && text.length > 1
                        && !["常规", "成员", "设置", "General", "Members", "Settings"].includes(text)) {
                        return text;
                    }
                }
                return null;
            }''')
            if name:
                config.CHATGPT_WORKSPACE_NAME = name
                print(f"[ChatGPT] 自动检测到 workspace 名称: {name}")
                return
        except Exception:
            pass

        print("[ChatGPT] ⚠️  未能自动获取 workspace 名称，请在 .env 中配置 CHATGPT_WORKSPACE_NAME")

    def _fetch_access_token(self):
        """通过浏览器 fetch 获取 access token"""
        result = self.page.evaluate('''async () => {
            try {
                const resp = await fetch("/api/auth/session");
                const data = await resp.json();
                return { ok: true, data: data };
            } catch(e) {
                // session 接口可能不返回 token，试 /backend-api/me
                return { ok: false, error: e.message };
            }
        }''')

        if result.get("ok") and "accessToken" in result.get("data", {}):
            self.access_token = result["data"]["accessToken"]
            print("[ChatGPT] 已获取 access token")
            return

        # 尝试通过 sentinel chat requirements 获取 token
        # 先试试 /backend-api/sentinel/chat-requirements
        result2 = self.page.evaluate('''async () => {
            try {
                const resp = await fetch("/backend-api/sentinel/chat-requirements", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({})
                });
                return { status: resp.status, text: await resp.text() };
            } catch(e) {
                return { error: e.message };
            }
        }''')

        # 如果以上都拿不到，用 session 文件里可能有的 bearer token
        bearer_file = BASE_DIR / "bearer_token"
        if bearer_file.exists():
            self.access_token = bearer_file.read_text().strip()
            print("[ChatGPT] 从 bearer_token 文件加载 access token")
            return

        # 最后手段：导航到 chatgpt.com 让前端 JS 获取 token，然后从 localStorage 读取
        print("[ChatGPT] 尝试通过页面获取 access token...")
        self.page.goto("https://chatgpt.com/", wait_until="networkidle", timeout=60000)
        time.sleep(10)

        token = self.page.evaluate('''() => {
            // 尝试多种方式
            try {
                const keys = Object.keys(localStorage);
                for (const key of keys) {
                    const val = localStorage.getItem(key);
                    if (val && val.includes("eyJ") && val.length > 500) {
                        return val;
                    }
                }
            } catch(e) {}

            // 尝试从 cookie 读取
            try {
                const cookies = document.cookie.split(";");
                for (const c of cookies) {
                    if (c.trim().startsWith("oai-sc=")) {
                        return null; // not the right one
                    }
                }
            } catch(e) {}
            return null;
        }''')

        if token:
            self.access_token = token
            print("[ChatGPT] 从页面获取到 access token")
        else:
            print("[ChatGPT] 警告: 未能获取 access token，将尝试无 token 调用")

    def _api_fetch(self, method, path, body=None):
        """在浏览器内用 fetch 调用 ChatGPT API"""
        headers_js = {
            "Content-Type": "application/json",
            "chatgpt-account-id": self.account_id,
            "oai-device-id": self.oai_device_id,
            "oai-language": "en-US",
        }
        if self.access_token:
            headers_js["authorization"] = f"Bearer {self.access_token}"

        js_code = '''async ([method, url, headers, body]) => {
            try {
                const opts = { method, headers };
                if (body) opts.body = body;
                const resp = await fetch(url, opts);
                const text = await resp.text();
                return { status: resp.status, body: text };
            } catch(e) {
                return { status: 0, body: e.message };
            }
        }'''

        result = self.page.evaluate(
            js_code,
            [method, f"https://chatgpt.com{path}", headers_js, json.dumps(body) if body else None],
        )
        return result

    def invite_member(self, email, seat_type="usage_based"):
        """邀请邮箱加入 Team。新账号用 usage_based 绕过限制，旧账号用 default。"""
        path = f"/backend-api/accounts/{self.account_id}/invites"
        body = {
            "email_addresses": [email],
            "role": "standard-user",
            "seat_type": seat_type,
            "resend_emails": True,
        }

        print(f"[ChatGPT] 发送邀请到 {email} (seat_type={seat_type})...")
        result = self._api_fetch("POST", path, body)

        status = result["status"]
        resp_body = result["body"]

        print(f"[ChatGPT] 响应状态: {status}")

        try:
            data = json.loads(resp_body)
            print(f"[ChatGPT] 响应内容: {json.dumps(data, indent=2)[:500]}")
        except Exception:
            data = resp_body
            print(f"[ChatGPT] 响应内容: {resp_body[:500]}")

        # 新账号用 usage_based 绕过后，需要改回 default
        if status == 200 and seat_type == "usage_based" and isinstance(data, dict):
            invites = data.get("account_invites", [])
            for inv in invites:
                invite_id = inv.get("id")
                if invite_id:
                    self._update_invite_seat_type(invite_id, "default")

        return status, data

    def _update_invite_seat_type(self, invite_id, seat_type):
        """修改 pending invite 的 seat_type"""
        path = f"/backend-api/accounts/{self.account_id}/invites/{invite_id}"
        body = {"seat_type": seat_type}

        print(f"[ChatGPT] 修改邀请 seat_type -> {seat_type}...")
        result = self._api_fetch("PATCH", path, body)

        if result["status"] == 200:
            print(f"[ChatGPT] ✅ seat_type 已改为 {seat_type}")
        else:
            print(f"[ChatGPT] ❌ 修改 seat_type 失败: {result['status']} {result['body'][:200]}")

    def list_invites(self):
        """获取当前邀请列表"""
        path = f"/backend-api/accounts/{self.account_id}/invites"
        result = self._api_fetch("GET", path)
        try:
            return json.loads(result["body"])
        except Exception:
            return result["body"]

    def stop(self):
        """关闭浏览器"""
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self.browser = None
        self.playwright = None
