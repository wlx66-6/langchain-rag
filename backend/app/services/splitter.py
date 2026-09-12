"""文本切块：把长篇文档切成一小段一小段，方便检索和引用。"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

# 按中文常见的断句标点优先切分，其次换行、空格
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


def split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=_SEPARATORS,
    )
    return splitter.split_documents(docs)