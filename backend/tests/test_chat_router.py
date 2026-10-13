"""/api/chat 流式问答路由测试：SSE 事件序列、会话归属、消息落库。

检索/改写/生成全部由 `stub_rag` 打桩，不联网、不加载向量模型。
"""
import json

from app.models import Conversation


def _stream_chat(client, headers, content, conversation_id=None):
    """发起一次流式问答，把 SSE 事件解析成列表返回。"""
    events = []
    with client.stream(
        "POST",
        "/api/chat",
        json={"conversation_id": conversation_id, "content": content},
        headers=headers,
    ) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line and line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


def _types(events):
    return [e["type"] for e in events]


class TestChatStream:
    def test_new_conversation_streams_full_sequence(self, client, normal_token, bearer, stub_rag):
        events = _stream_chat(client, bearer(normal_token), "耳机续航多久？")

        assert events[0]["type"] == "start"
        assert events[0]["data"]["conversation_id"]
        assert events[0]["data"]["sources"]  # 带上了引用片段
        assert events[-1]["type"] == "done"
        # 中间是若干 token 事件，拼起来就是完整回答
        tokens = [e["data"] for e in events if e["type"] == "token"]
        assert tokens and "".join(tokens).strip()

    def test_start_event_carries_sources(self, client, normal_token, bearer, stub_rag):
        events = _stream_chat(client, bearer(normal_token), "问题")
        sources = events[0]["data"]["sources"]
        assert sources[0]["source"] == "商品说明.txt"

    def test_reuse_existing_conversation(self, client, normal_token, bearer, stub_rag, db_session, normal_user):
        conv = Conversation(user_id=normal_user.id, title="已有会话")
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        events = _stream_chat(client, bearer(normal_token), "再问一句", conversation_id=conv.id)
        assert events[0]["data"]["conversation_id"] == conv.id

    def test_other_users_conversation_404(self, client, normal_token, bearer, stub_rag, db_session, admin_user):
        conv = Conversation(user_id=admin_user.id, title="别人的")
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        r = client.post(
            "/api/chat",
            json={"conversation_id": conv.id, "content": "偷看"},
            headers=bearer(normal_token),
        )
        assert r.status_code == 404

    def test_requires_auth(self, client):
        r = client.post("/api/chat", json={"conversation_id": None, "content": "你好"})
        assert r.status_code == 401

    def test_empty_content_rejected(self, client, normal_token, bearer):
        r = client.post("/api/chat", json={"conversation_id": None, "content": ""}, headers=bearer(normal_token))
        assert r.status_code == 422


class TestChatPersistence:
    def test_user_and_assistant_messages_saved(self, client, normal_token, bearer, stub_rag):
        events = _stream_chat(client, bearer(normal_token), "续航多久？")
        conv_id = events[0]["data"]["conversation_id"]

        msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=bearer(normal_token)).json()
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "续航多久？"

    def test_assistant_message_has_citations(self, client, normal_token, bearer, stub_rag):
        events = _stream_chat(client, bearer(normal_token), "续航多久？")
        conv_id = events[0]["data"]["conversation_id"]

        msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=bearer(normal_token)).json()
        citations = json.loads(msgs[1]["citations"])
        assert citations[0]["source"] == "商品说明.txt"

    def test_conversation_title_from_first_question(self, client, normal_token, bearer, stub_rag):
        events = _stream_chat(client, bearer(normal_token), "耳机续航多久？")
        conv_id = events[0]["data"]["conversation_id"]

        convs = client.get("/api/conversations", headers=bearer(normal_token)).json()
        assert convs[0]["id"] == conv_id
        assert convs[0]["title"] == "耳机续航多久？"


class _BoomChain:
    """一个 astream 立即抛错的假链，用来模拟生成阶段崩溃。"""

    def __init__(self, message: str = "模拟模型异常"):
        self._message = message

    def astream(self, _input):  # noqa: ANN001
        message = self._message

        async def _gen():
            raise RuntimeError(message)
            yield  # pragma: no cover  —— 让 _gen 成为生成器

        return _gen()


class _PartialBoomChain:
    """先吐两段正常内容，再抛错，用来验证「已生成的部分内容会被保存」。"""

    def astream(self, _input):  # noqa: ANN001
        async def _gen():
            from langchain_core.messages import AIMessageChunk

            yield AIMessageChunk(content="已经")
            yield AIMessageChunk(content="生成的一半")
            raise RuntimeError("模拟模型中途异常")

        return _gen()


class TestChatFailure:
    def test_generation_error_emits_error_event(self, client, normal_token, bearer, stub_rag, monkeypatch):
        """生成阶段抛异常时，应向前端推一条 error 事件而不是让连接静默中断。"""
        from app.services import rag

        monkeypatch.setattr(rag, "build_answer_chain", lambda: _BoomChain())

        events = _stream_chat(client, bearer(normal_token), "会失败的问题")
        assert "error" in _types(events)
        assert "done" not in _types(events)

    def test_error_event_is_desensitized(self, client, normal_token, bearer, stub_rag, monkeypatch):
        """错误事件不能把原始异常（可能含路径/密钥）透给前端，只给统一文案 + code。"""
        from app.services import rag

        secret = "C:/secret/path/api_key=sk-abcdef123456"
        monkeypatch.setattr(rag, "build_answer_chain", lambda: _BoomChain(secret))

        events = _stream_chat(client, bearer(normal_token), "会失败的问题")
        error = next(e for e in events if e["type"] == "error")

        assert error["code"] == "generation_failed"
        assert error["data"] == "回答生成失败，请稍后重试"
        assert secret not in json.dumps(events, ensure_ascii=False)

    def test_failure_still_persists_assistant_message(self, client, normal_token, bearer, stub_rag, monkeypatch):
        """生成失败也要落一条客服消息，避免会话里留下悬空的提问。"""
        from app.services import rag

        monkeypatch.setattr(rag, "build_answer_chain", lambda: _BoomChain())

        events = _stream_chat(client, bearer(normal_token), "会失败的问题")
        conv_id = events[0]["data"]["conversation_id"]

        msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=bearer(normal_token)).json()
        assert [m["role"] for m in msgs] == ["user", "assistant"]

    def test_failure_keeps_partial_answer(self, client, normal_token, bearer, stub_rag, monkeypatch):
        """中途失败时，已经把内容流出去的这一部分不能丢。"""
        from app.services import rag

        monkeypatch.setattr(rag, "build_answer_chain", lambda: _PartialBoomChain())

        events = _stream_chat(client, bearer(normal_token), "会中途失败的问题")
        conv_id = events[0]["data"]["conversation_id"]

        msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=bearer(normal_token)).json()
        assert msgs[1]["content"] == "已经生成的一半"