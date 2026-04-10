"""CPA (CLIProxyAPI) 认证文件同步 - 保持本地 codex 认证文件与 CPA 一致"""

import json
import requests
from pathlib import Path
from autoteam.config import CPA_URL, CPA_KEY

PROJECT_ROOT = Path(__file__).parent.parent.parent
AUTH_DIR = PROJECT_ROOT / "auths"


def _headers():
    return {"Authorization": f"Bearer {CPA_KEY}"}


def list_cpa_files():
    """获取 CPA 中所有认证文件"""
    resp = requests.get(f"{CPA_URL}/v0/management/auth-files", headers=_headers(), timeout=10)
    if resp.status_code != 200:
        print(f"[CPA] 获取文件列表失败: {resp.status_code}")
        return []
    data = resp.json()
    return data.get("files", [])


def upload_to_cpa(filepath):
    """上传认证文件到 CPA"""
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"[CPA] 文件不存在: {filepath}")
        return False

    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{CPA_URL}/v0/management/auth-files",
            headers=_headers(),
            files={"file": (filepath.name, f, "application/json")},
            timeout=10,
        )

    if resp.status_code == 200:
        print(f"[CPA] ✅ 已上传: {filepath.name}")
        return True
    else:
        print(f"[CPA] ❌ 上传失败: {resp.status_code} {resp.text[:200]}")
        return False


def delete_from_cpa(name):
    """从 CPA 删除认证文件"""
    resp = requests.delete(
        f"{CPA_URL}/v0/management/auth-files",
        headers=_headers(),
        params={"name": name},
        timeout=10,
    )
    if resp.status_code == 200:
        print(f"[CPA] ✅ 已删除: {name}")
        return True
    else:
        print(f"[CPA] ❌ 删除失败: {resp.status_code} {resp.text[:200]}")
        return False


def sync_to_cpa():
    """
    同步本地认证文件到 CPA，只同步 active 状态的账号。
    - active 且 CPA 没有 → 上传
    - CPA 有但不是 active（或本地已删除）→ 从 CPA 删除
    """
    from autoteam.accounts import load_accounts, save_accounts, STATUS_ACTIVE

    accounts = load_accounts()
    local_emails = {a["email"].lower() for a in accounts}

    # 修复断裂的 auth_file 路径
    changed = False
    for acc in accounts:
        auth_path = acc.get("auth_file")
        if auth_path and not Path(auth_path).exists():
            matches = list(AUTH_DIR.glob(f"codex-{acc['email']}-*.json"))
            if matches:
                acc["auth_file"] = str(matches[0].resolve())
                changed = True
    if changed:
        save_accounts(accounts)

    # active 账号的认证文件
    active_files = {}
    for acc in accounts:
        if acc["status"] == STATUS_ACTIVE and acc.get("auth_file"):
            path = Path(acc["auth_file"])
            if path.exists():
                active_files[path.name] = path

    # CPA 认证文件
    cpa_files = list_cpa_files()
    cpa_names = {f["name"]: f for f in cpa_files}

    print(f"\nactive 认证文件: {len(active_files)}")
    print(f"CPA  认证文件: {len(cpa_files)}")

    # 上传：active 有但 CPA 没有
    uploaded = 0
    for name, path in active_files.items():
        if name not in cpa_names:
            print(f"\n上传: {name}")
            if upload_to_cpa(path):
                uploaded += 1

    # 删除：CPA 中有但不在 active 列表的（仅限本地管理的账号）
    deleted = 0
    for name, cpa_file in cpa_names.items():
        email = cpa_file.get("email", "").lower()
        if email in local_emails and name not in active_files:
            print(f"\n删除非 active 文件: {name} ({email})")
            if delete_from_cpa(name):
                deleted += 1

    print(f"\n同步完成: 上传 {uploaded}, 删除 {deleted}")

    # 最终状态
    final_cpa = list_cpa_files()
    final_local_managed = [f for f in final_cpa if f.get("email", "").lower() in local_emails]
    print(f"CPA 中本地管理的认证文件: {len(final_local_managed)}")
    print(f"本地 active 认证文件: {len(active_files)}")
