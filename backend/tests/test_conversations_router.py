"""/api/conversations 路由测试：增删改查与「只能操作自己会话」的归属校验。"""

import pytest

from app.core.security import create_access_token
from app.models import Conversation, Message


@pytest.fixture()
def conv(client, normal_token, bearer):
    """建一个属于普通用户的会话，返回其 JSON。"""
    r = client.post(
        "/api/conversations",
        json={"title": "第一个会话"},
        headers=bearer(normal_token),
    )
    assert r.status_code == 201
    return r.json()


class TestCreateAndList:
    def test_create_returns_conversation(self, conv):
        assert conv["title"] == "第一个会话"
        assert "id" in conv

    def test_list_only_returns_own(
        self, client, normal_token, bearer, db_session, normal_user, admin_user
    ):
        db_session.add(Conversation(user_id=normal_user.id, title="我的"))
        db_session.add(Conversation(user_id=admin_user.id, title="别人的"))
        db_session.commit()

        r = client.get("/api/conversations", headers=bearer(normal_token))
        assert r.status_code == 200
        titles = [c["title"] for c in r.json()]
        assert "我的" in titles
        assert "别人的" not in titles

    def test_list_requires_auth(self, client):
        assert client.get("/api/conversations").status_code == 401


class TestRenameAndDelete:
    def test_rename_own(self, client, conv, normal_token, bearer):
        r = client.patch(
            f"/api/conversations/{conv['id']}",
            json={"title": "改个名"},
            headers=bearer(normal_token),
        )
        assert r.status_code == 200
        assert r.json()["title"] == "改个名"

    def test_rename_others_forbidden_as_404(
        self, client, normal_user, bearer, db_session, admin_user
    ):
        # 管理员名下的会话，被普通用户尝试重命名 → 一律当作「不存在」
        other = Conversation(user_id=admin_user.id, title="别人的")
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        r = client.patch(
            f"/api/conversations/{other.id}",
            json={"title": "偷改"},
            headers=bearer(create_access_token(normal_user.id)),
        )
        assert r.status_code == 404

    def test_delete_own(self, client, conv, normal_token, bearer):
        r = client.delete(f"/api/conversations/{conv['id']}", headers=bearer(normal_token))
        assert r.status_code == 200
        assert client.get("/api/conversations", headers=bearer(normal_token)).json() == []

    def test_delete_missing_returns_404(self, client, normal_token, bearer):
        r = client.delete("/api/conversations/999999", headers=bearer(normal_token))
        assert r.status_code == 404


class TestMessages:
    def test_get_messages_in_order(self, client, conv, normal_token, bearer, db_session):
        db_session.add(Message(conversation_id=conv["id"], role="user", content="你好"))
        db_session.add(Message(conversation_id=conv["id"], role="assistant", content="您好"))
        db_session.commit()

        r = client.get(f"/api/conversations/{conv['id']}/messages", headers=bearer(normal_token))
        assert r.status_code == 200
        assert [m["role"] for m in r.json()] == ["user", "assistant"]

    def test_get_messages_missing_conversation_404(self, client, normal_token, bearer):
        r = client.get("/api/conversations/999999/messages", headers=bearer(normal_token))
        assert r.status_code == 404
