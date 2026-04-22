import pytest

from autoteam import account_ops


class _FakeChatGPT:
    def __init__(self, responses):
        self._responses = responses

    def _api_fetch(self, method, path):
        return self._responses[path]


def test_fetch_team_state_parses_members_and_invites(monkeypatch):
    monkeypatch.setattr(account_ops, "get_chatgpt_account_id", lambda: "acc-1")
    chatgpt = _FakeChatGPT(
        {
            "/backend-api/accounts/acc-1/users": {
                "status": 200,
                "body": '{"items":[{"email":"member@example.com"}]}',
            },
            "/backend-api/accounts/acc-1/invites": {
                "status": 200,
                "body": '{"invites":[{"email":"invite@example.com"}]}',
            },
        }
    )

    members, invites = account_ops.fetch_team_state(chatgpt)

    assert members == [{"email": "member@example.com"}]
    assert invites == [{"email": "invite@example.com"}]


def test_fetch_team_state_raises_readable_error_when_users_response_is_html(monkeypatch):
    monkeypatch.setattr(account_ops, "get_chatgpt_account_id", lambda: "acc-1")
    chatgpt = _FakeChatGPT(
        {
            "/backend-api/accounts/acc-1/users": {
                "status": 200,
                "body": "<!doctype html><html><body>login</body></html>",
            },
            "/backend-api/accounts/acc-1/invites": {
                "status": 200,
                "body": '{"invites":[]}',
            },
        }
    )

    with pytest.raises(RuntimeError, match="Team 成员接口返回了非 JSON 内容"):
        account_ops.fetch_team_state(chatgpt)


def test_fetch_team_state_raises_readable_error_when_users_auth_fails(monkeypatch):
    monkeypatch.setattr(account_ops, "get_chatgpt_account_id", lambda: "acc-1")
    chatgpt = _FakeChatGPT(
        {
            "/backend-api/accounts/acc-1/users": {
                "status": 403,
                "body": '{"detail":"forbidden"}',
            },
            "/backend-api/accounts/acc-1/invites": {
                "status": 200,
                "body": '{"invites":[]}',
            },
        }
    )

    with pytest.raises(RuntimeError, match="请重新完成管理员登录"):
        account_ops.fetch_team_state(chatgpt)
