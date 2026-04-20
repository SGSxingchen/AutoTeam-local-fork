import threading

from autoteam import api


def test_finish_admin_login_keeps_main_codex_pending_when_code_required(monkeypatch):
    events = []

    class FakeAdminLoginAPI:
        def complete_admin_login(self):
            events.append("admin_complete")
            return {
                "email": "owner@example.com",
                "session_token": "session-token",
                "account_id": "acc-1",
                "workspace_name": "Idapro",
            }

        def stop(self):
            events.append("admin_stop")

    class FakeMainCodexSyncFlow:
        def __init__(self):
            events.append("main_init")

        def start(self):
            events.append("main_start")
            return {"step": "code_required", "detail": None}

        def stop(self):
            events.append("main_stop")

    lock = threading.Lock()
    assert lock.acquire(blocking=False) is True

    monkeypatch.setattr(api, "_playwright_lock", lock)
    monkeypatch.setattr(api, "_admin_login_api", FakeAdminLoginAPI())
    monkeypatch.setattr(api, "_admin_login_step", "workspace_required")
    monkeypatch.setattr(api, "_main_codex_flow", None)
    monkeypatch.setattr(api, "_main_codex_step", None)
    monkeypatch.setattr(api._pw_executor, "run", lambda func, *args, **kwargs: func(*args, **kwargs))
    monkeypatch.setattr("autoteam.codex_auth.MainCodexSyncFlow", FakeMainCodexSyncFlow)

    result = api._finish_admin_login({"step": "completed"})

    assert result["status"] == "completed"
    assert result["info"]["main_auth_pending"] is True
    assert result["info"]["main_auth_step"] == "code_required"
    assert result["codex"] == {"in_progress": True, "step": "code_required"}
    assert api._main_codex_flow is not None
    assert api._main_codex_step == "code_required"
    assert api._admin_login_api is None
    assert api._admin_login_step is None
    assert lock.locked() is True
    assert events == ["admin_complete", "admin_stop", "main_init", "main_start"]

    api._main_codex_flow = None
    api._main_codex_step = None
    if lock.locked():
        lock.release()


def test_finish_admin_login_finishes_main_codex_sync_when_no_extra_step_needed(monkeypatch):
    events = []

    class FakeAdminLoginAPI:
        def complete_admin_login(self):
            events.append("admin_complete")
            return {
                "email": "owner@example.com",
                "session_token": "session-token",
                "account_id": "acc-1",
                "workspace_name": "Idapro",
            }

        def stop(self):
            events.append("admin_stop")

    class FakeMainCodexSyncFlow:
        def __init__(self):
            events.append("main_init")

        def start(self):
            events.append("main_start")
            return {"step": "completed", "detail": None}

        def complete(self):
            events.append("main_complete")
            return {"email": "owner@example.com", "auth_file": "/tmp/codex-main.json", "plan_type": "team"}

        def stop(self):
            events.append("main_stop")

    lock = threading.Lock()
    assert lock.acquire(blocking=False) is True

    monkeypatch.setattr(api, "_playwright_lock", lock)
    monkeypatch.setattr(api, "_admin_login_api", FakeAdminLoginAPI())
    monkeypatch.setattr(api, "_admin_login_step", "workspace_required")
    monkeypatch.setattr(api, "_main_codex_flow", None)
    monkeypatch.setattr(api, "_main_codex_step", None)
    monkeypatch.setattr(api._pw_executor, "run", lambda func, *args, **kwargs: func(*args, **kwargs))
    monkeypatch.setattr("autoteam.codex_auth.MainCodexSyncFlow", FakeMainCodexSyncFlow)

    result = api._finish_admin_login({"step": "completed"})

    assert result["status"] == "completed"
    assert result["info"]["main_auth"] == {
        "email": "owner@example.com",
        "auth_file": "/tmp/codex-main.json",
        "plan_type": "team",
    }
    assert result["codex"] == {"in_progress": False, "step": None}
    assert api._main_codex_flow is None
    assert api._main_codex_step is None
    assert api._admin_login_api is None
    assert api._admin_login_step is None
    assert lock.locked() is False
    assert events == ["admin_complete", "admin_stop", "main_init", "main_start", "main_complete", "main_stop"]
