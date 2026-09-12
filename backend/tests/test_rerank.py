"""rag.py 的 _rerank 单元测试：重排的打分筛选、及格线兜底、异常回退（mock 掉远程重排，不联网）。"""
from http import HTTPStatus

import dashscope
import pytest
from langchain_core.documents import Document

from app.config import settings
from app.services.rag import _rerank


def _doc(content: str, source: str = "x.txt") -> Document:
    return Document(page_content=content, metadata={"source": source})


# ---- 构造 dashscope.TextReRank.call 的假返回对象 ----
class _R:
    """模拟重排返回的单条打分结果：index 指向候选下标、relevance_score 是相关度。"""

    def __init__(self, index, score):
        self.index = index
        self.relevance_score = score


class _Resp:
    def __init__(self, status_code, results=None):
        self.status_code = status_code
        self.output = type("_Out", (), {"results": results or []})()


@pytest.fixture(autouse=True)
def _pin_rerank_params(monkeypatch):
    """固定及格线/保留条数，避免被 .env 里不同的 rerank_min_score 影响断言。"""
    monkeypatch.setattr(settings, "rerank_min_score", 0.2)
    monkeypatch.setattr(settings, "rerank_top_n", 3)


class TestRerankFallback:
    def test_all_below_threshold_keeps_most_relevant_one(self, monkeypatch):
        """核心 bug 修复：及格线把候选筛空时，兜底保留最相关的第一名（避免「有答案却说找不到」）。"""
        docs = [
            (_doc("商品A介绍", "a.txt"), 0.9),
            (_doc("商品B介绍", "b.txt"), 0.8),
            (_doc("商品C介绍", "c.txt"), 0.7),
        ]
        # 重排给的分都在及格线 0.2 以下：最高的是 index=1 的 0.15
        fake = _Resp(HTTPStatus.OK, [_R(1, 0.15), _R(0, 0.10), _R(2, 0.05)])
        monkeypatch.setattr(dashscope.TextReRank, "call", lambda **kw: fake)

        out = _rerank("某问题", docs)
        assert len(out) == 1
        assert out[0][0].page_content == "商品B介绍"  # 保留了 score 最高的 index=1
        assert out[0][1] == 0.15

    def test_keeps_above_threshold_sorted_and_capped(self, monkeypatch):
        docs = [(_doc("A"), 0.5), (_doc("B"), 0.5), (_doc("C"), 0.5), (_doc("D"), 0.5)]
        # 及格线 0.2：D=0.9、B=0.7、C=0.5 及格；A=0.1 不及格被剔除
        fake = _Resp(HTTPStatus.OK, [_R(3, 0.9), _R(0, 0.1), _R(1, 0.7), _R(2, 0.5)])
        monkeypatch.setattr(dashscope.TextReRank, "call", lambda **kw: fake)

        out = _rerank("某问题", docs)
        assert [d.page_content for d, _ in out] == ["D", "B", "C"]  # 按分从高到低

    def test_empty_needs_no_rerank(self, monkeypatch):
        # 空候选列表直接返回空，不应触发重排调用
        assert _rerank("某问题", []) == []


class TestRerankFallbackPaths:
    def test_status_not_ok_returns_dedup_original(self, monkeypatch):
        docs = [(_doc("重复内容", "a.txt"), 0.5), (_doc("重复内容", "b.txt"), 0.5), (_doc("独有内容", "c.txt"), 0.5)]
        monkeypatch.setattr(dashscope.TextReRank, "call", lambda **kw: _Resp(500))

        out = _rerank("某问题", docs)
        # 退回「仅去重」的原始顺序
        assert [d.page_content for d, _ in out] == ["重复内容", "独有内容"]
        assert out[0][0].metadata["source"] == "a.txt"

    def test_no_scores_returned_returns_dedup_original(self, monkeypatch):
        docs = [(_doc("重复内容", "a.txt"), 0.5), (_doc("重复内容", "b.txt"), 0.5)]
        monkeypatch.setattr(dashscope.TextReRank, "call", lambda **kw: _Resp(HTTPStatus.OK, []))

        out = _rerank("某问题", docs)
        assert len(out) == 1
        assert out[0][0].metadata["source"] == "a.txt"

    def test_exception_returns_dedup_original(self, monkeypatch):
        docs = [(_doc("重复内容", "a.txt"), 0.5), (_doc("重复内容", "b.txt"), 0.5)]

        def boom(**kw):
            raise RuntimeError("网络挂了")

        monkeypatch.setattr(dashscope.TextReRank, "call", boom)

        out = _rerank("某问题", docs)
        assert len(out) == 1
        assert out[0][0].metadata["source"] == "a.txt"