"""向量数据库：ChromaDB 的读写（存到本地磁盘，重启不丢）。"""
from langchain_chroma import Chroma

from app.config import settings
from app.services.embeddings import get_embeddings


def get_vectorstore() -> Chroma:
    return Chroma(
        collection_name="knowledge",
        embedding_function=get_embeddings(),
        persist_directory=str(settings.chroma_dir),
    )