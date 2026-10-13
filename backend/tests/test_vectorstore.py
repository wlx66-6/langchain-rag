"""vectorstore.py 的单元测试：确认向量库实例被进程内缓存（不会每个请求重造）。

真实的 Chroma 客户端与向量模型都很重，这里把 Chroma 与 get_embeddings 换成假实现，
只验证「缓存」这一行为本身。
"""

import pytest

from app.services import vectorstore


@pytest.fixture
def _fake_chroma(monkeypatch):
    """替换向量库构造与向量模型，返回「被调用了几次」的计数器。"""
    calls = {"n": 0}

    class _FakeChroma:
        def __init__(self, **kwargs):
            calls["n"] += 1
            self.kwargs = kwargs

    monkeypatch.setattr(vectorstore, "Chroma", _FakeChroma)
    monkeypatch.setattr(vectorstore, "get_embeddings", lambda: object())
    vectorstore.get_vectorstore.cache_clear()
    yield calls
    # 用例结束后清掉缓存，避免污染其它用例
    vectorstore.get_vectorstore.cache_clear()


class TestGetVectorstore:
    def test_returns_cached_instance(self, _fake_chroma):
        first = vectorstore.get_vectorstore()
        second = vectorstore.get_vectorstore()
        assert first is second
        assert _fake_chroma["n"] == 1  # 只构造了一次

    def test_cache_clear_rebuilds(self, _fake_chroma):
        first = vectorstore.get_vectorstore()
        vectorstore.get_vectorstore.cache_clear()
        second = vectorstore.get_vectorstore()
        assert first is not second
        assert _fake_chroma["n"] == 2
