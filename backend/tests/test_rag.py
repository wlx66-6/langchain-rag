"""rag.py 的单元测试：引用格式化等纯逻辑（不涉及大模型/向量库）。"""

from langchain_core.documents import Document

from app.services.rag import _dedup, _format_history, build_sources, format_context


def _doc(content: str, source: str = "a.txt") -> Document:
    return Document(page_content=content, metadata={"source": source})


class TestFormatContext:
    def test_empty(self):
        assert format_context([]) == ""

    def test_single_doc(self):
        out = format_context([(_doc("内容A"), 0.1)])
        assert out == "[1]（来源：a.txt）\n内容A"

    def test_multiple_docs_are_numbered(self):
        out = format_context([(_doc("内容A"), 0.1), (_doc("内容B"), 0.2)])
        assert "[1]（来源：a.txt）\n内容A" in out
        assert "[2]（来源：a.txt）\n内容B" in out

    def test_missing_source_falls_back(self):
        doc = Document(page_content="内容", metadata={})
        out = format_context([(doc, 0.1)])
        assert "未知来源" in out


class TestBuildSources:
    def test_extracts_source_and_content(self):
        assert build_sources([(_doc("内容A"), 0.1)]) == [{"source": "a.txt", "content": "内容A"}]

    def test_missing_source_falls_back(self):
        doc = Document(page_content="内容", metadata={})
        sources = build_sources([(doc, 0.1)])
        assert sources[0]["source"] == "未知来源"
        assert sources[0]["content"] == "内容"


class TestFormatHistory:
    def test_empty_history(self):
        assert _format_history([]) == "（无历史对话）"

    def test_user_and_assistant_roles(self):
        history = [
            {"role": "user", "content": "它多少钱"},
            {"role": "assistant", "content": "399 元"},
        ]
        out = _format_history(history)
        assert "用户：它多少钱" in out
        assert "客服：399 元" in out


class TestDedup:
    def test_removes_identical_content(self):
        docs = [(_doc("内容A"), 0.1), (_doc("内容A"), 0.2), (_doc("内容B"), 0.3)]
        out = _dedup(docs)
        assert len(out) == 2
        assert out[0][0].page_content == "内容A"
        assert out[1][0].page_content == "内容B"

    def test_keeps_first_occurrence_within_same_source(self):
        """同一份文件里的重复片段只留第一处。"""
        out = _dedup([(_doc("重复", "a.txt"), 0.1), (_doc("重复", "a.txt"), 0.9)])
        assert len(out) == 1
        assert out[0][0].metadata["source"] == "a.txt"

    def test_same_content_from_different_sources_both_kept(self):
        """不同文件里出现一模一样的句子是常见的（例如两份文档写了同一句售后条款），
        不能因为内容相同就把其中一份的引用删掉。"""
        out = _dedup([(_doc("重复", "a.txt"), 0.1), (_doc("重复", "b.txt"), 0.9)])
        assert len(out) == 2
        assert [d.metadata["source"] for d, _ in out] == ["a.txt", "b.txt"]

    def test_skips_whitespace_only(self):
        out = _dedup([(_doc("   "), 0.1), (_doc("内容"), 0.2)])
        assert len(out) == 1
        assert out[0][0].page_content == "内容"
