"""全局配置：从 backend/.env 读取百炼 API Key、模型名、路径等。"""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend 目录的绝对路径（本文件位于 backend/app/config.py）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 阿里云百炼 / 通义千问 ----
    dashscope_api_key: str = ""
    qwen_model: str = "qwen-plus"  # qwen-plus / qwen-turbo / qwen-max

    # ---- 本地向量化模型 ----
    embedding_model: str = "BAAI/bge-m3"
    chunk_size: int = 500       # 每段文字大约多少字
    chunk_overlap: int = 50     # 段落之间保留多少字重叠，防止意思被切断
    top_k: int = 4              # 每次检索返回多少段相关内容

    # ---- 重排（rerank）：让引用更精准，只留最贴题的那几条 ----
    rerank_model: str = "gte-rerank-v2"   # 百炼自带的重排模型
    rerank_candidates: int = 10           # 重排前先海选多少段候选
    rerank_top_n: int = 3                 # 重排后最多保留几条引用
    rerank_min_score: float = 0.2         # 相关度及格线（低于此分视为不相关）

    # ---- 压测开关 ----
    # 置为 True 时（启动前设环境变量 MOCK_LLM=1），问答接口改用「假大模型 + 跳过远程重排」，
    # 只跑本地骨架（SQLite + 词向量 + Chroma 检索），用于压力测试，不花钱、不碰百炼。日常保持 False。
    mock_llm: bool = False

    # ---- HuggingFace 下载镜像（国内访问 huggingface.co 慢，默认走镜像加速） ----
    hf_endpoint: str = "https://hf-mirror.com"

    # ---- 存储路径 ----
    data_dir: Path = BASE_DIR / "data"
    chroma_dir: Path = BASE_DIR / "data" / "chroma"
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    sqlite_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"

    # ---- 安全 ----
    # 说明：生产环境请改成随机长字符串；本机演示可用默认值
    jwt_secret: str = "graduation-project-rag-secret-change-me"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


settings = Settings()

# 确保数据目录存在
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.chroma_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)

# 把百炼 API Key 导出为环境变量，让 LangChain 的通义千问组件能自动读取
if settings.dashscope_api_key and not os.environ.get("DASHSCOPE_API_KEY"):
    os.environ["DASHSCOPE_API_KEY"] = settings.dashscope_api_key

# 设置 HuggingFace 下载镜像（用于加快 bge-m3 模型的下载）
if settings.hf_endpoint and not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = settings.hf_endpoint