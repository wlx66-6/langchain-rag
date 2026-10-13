"""向量数据库：ChromaDB 的读写（存到本地磁盘，重启不丢）。"""
from functools import lru_cache

from langchain_chroma import Chroma

from app.config import settings
from app.services.embeddings import get_embeddings


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    """返回向量库实例。

    进程内缓存（lru_cache）：Chroma 客户端 + 向量模型加载都很重，
    每个请求都新建一次会白白增加延迟与内存占用。配置变更后重启进程即可生效。
    """
    return Chroma(
        collection_name="knowledge",
        embedding_function=get_embeddings(),
        persist_directory=str(settings.chroma_dir),
    )