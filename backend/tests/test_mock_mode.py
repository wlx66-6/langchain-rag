"""压测开关 mock_llm 的行为单元测试：假模型替换、改写跳过、重排跳过（纯逻辑，不联网）。"""

import asyncio

from langchain_core.documents import Document

from app.config import settings
from app.services import rag
from app.services.mock_llm import MockChatModel


def _doc(content: str, source: str = "x.txt") -> Document:
    return Document(page_content=content, metadata={"source": source})


class TestGetLlm:
    def test_mock_mode_returns_fake_model(self, monkeypatch):
        monkeypatch.setattr(settings, "mock_llm", True)
        assert isinstance(rag.get_llm(), MockChatModel)

    def test_normal_mode_returns_real_model(self, monkeypatch):
        # 正常模式下不返回假模型（真模型的具体类型这里不细化，避免依赖百炼网络）
        monkeypatch.setattr(settings, "mock_llm", False)
        # ChatTongyi 构造时会校验 API Key，这里给个占位值让测试不依赖本地 .env
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-placeholder-key")
        assert not isinstance(rag.get_llm(), MockChatModel)


class TestRewriteQuestion:
    def test_mock_mode_skips_rewrite(self, monkeypatch):
        monkeypatch.setattr(settings, "mock_llm", True)

        def _fail(*_a, **_k):
            raise AssertionError("mock 模式下不应调用 get_llm")

        monkeypatch.setattr(rag, "get_llm", _fail)

        question = "那有优惠吗"
        history = [
            {"role": "user", "content": "它多少钱"},
            {"role": "assistant", "content": "399 元"},
        ]
        assert asyncio.run(rag.rewrite_question(question, history)) == question

    def test_no_history_skips_rewrite(self, monkeypatch):
        monkeypatch.setattr(settings, "mock_llm", False)

        def _fail(*_a, **_k):
            raise AssertionError("无历史时不应调用大模型改写")

        monkeypatch.setattr(rag, "get_llm", _fail)

        question = "耳机续航多久？"
        assert asyncio.run(rag.rewrite_question(question, [])) == question


class TestRetrieveWithRerank:
    def test_mock_mode_skips_remote_rerank(self, monkeypatch):
        monkeypatch.setattr(settings, "mock_llm", True)
        monkeypatch.setattr(settings, "top_k", 4)

        docs = [(_doc(f"内容{i}", f"{i}.txt"), 0.5 - i * 0.01) for i in range(6)]
        monkeypatch.setattr(rag, "retrieve", lambda q, k=None: docs)

        def _rerank_fail(*_a, **_k):
            raise AssertionError("mock 模式下不应调用远程重排")

        monkeypatch.setattr(rag, "_rerank", _rerank_fail)

        out = rag.retrieve_with_rerank("某问题")
        # 只把去重后的候选截取前 top_k 段，不去调重排
        assert [d.page_content for d, _ in out] == ["内容0", "内容1", "内容2", "内容3"]

    def test_normal_mode_delegates_to_rerank(self, monkeypatch):
        monkeypatch.setattr(settings, "mock_llm", False)

        docs = [(_doc("内容0"), 0.5), (_doc("内容1"), 0.4)]
        monkeypatch.setattr(rag, "retrieve", lambda q, k=None: docs)

        called = {}

        def _fake_rerank(question, candidates):
            called["question"] = question
            called["candidates"] = candidates
            return candidates[:1]

        monkeypatch.setattr(rag, "_rerank", _fake_rerank)

        out = rag.retrieve_with_rerank("某问题")
        assert called["question"] == "某问题"
        assert len(called["candidates"]) == 2  # 去重后有 2 条候选交给重排
        assert len(out) == 1
        assert out[0][0].page_content == "内容0"
