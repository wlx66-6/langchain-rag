"""splitter.py 的单元测试：文本切块。"""
from langchain_core.documents import Document

from app.services.splitter import split_documents


def test_short_text_stays_single_chunk():
    doc = Document(page_content="很短的一句话。")
    chunks = split_documents([doc])
    assert len(chunks) == 1
    assert chunks[0].page_content == "很短的一句话。"


def test_long_text_splits_into_multiple_chunks():
    text = "市场对这款产品的反馈良好。" * 200  # 远超 chunk_size
    doc = Document(page_content=text)
    chunks = split_documents([doc])
    assert len(chunks) > 1
    assert all(c.page_content for c in chunks)  # 每块都非空


def test_metadata_is_preserved_across_chunks():
    doc = Document(
        page_content="内容A。" * 100,
        metadata={"source": "售后.txt", "doc_id": 7},
    )
    chunks = split_documents([doc])
    assert chunks
    assert all(c.metadata["source"] == "售后.txt" for c in chunks)
    assert all(c.metadata["doc_id"] == 7 for c in chunks)