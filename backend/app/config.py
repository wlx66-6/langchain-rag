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

    # ---- 本地向量化模型与检索参数 ----
    embedding_model: str = "BAAI/bge-m3"
    chunk_size: int = 500  # 单个文本片段的目标字符数
    chunk_overlap: int = 50  # 相邻片段保留的重叠字符数，避免语义被切断
    top_k: int = 4  # 每次检索返回的片段数

    # ---- 重排（rerank）：对候选片段精排，让引用更精准 ----
    rerank_model: str = "gte-rerank-v2"  # 百炼提供的重排模型
    rerank_candidates: int = 10  # 重排前召回的候选片段数
    rerank_top_n: int = 3  # 重排后最多保留的引用片段数
    rerank_min_score: float = 0.2  # 相关度及格线，低于该分视为不相关

    # ---- 压测开关 ----
    # 置为 True（启动前设环境变量 MOCK_LLM=1）时，问答接口改用「假大模型 + 跳过远程重排」，
    # 只跑本地骨架（SQLite + 词向量 + Chroma 检索），用于压力测试，不消耗大模型调用。日常保持 False。
    mock_llm: bool = False

    # ---- HuggingFace 下载镜像（国内直连 huggingface.co 较慢，默认走镜像加速）----
    hf_endpoint: str = "https://hf-mirror.com"

    # ---- 存储路径 ----
    data_dir: Path = BASE_DIR / "data"
    chroma_dir: Path = BASE_DIR / "data" / "chroma"
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    sqlite_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"
    max_upload_size: int = 20 * 1024 * 1024  # 单个上传文件的大小上限（字节），默认 20MB

    # ---- 安全 ----
    # JWT_SECRET 必须由 .env 提供，代码中不设默认值：启动时由 validate_startup_config()
    # 校验，缺失会明确报错，避免落入「可预测的假密钥」导致令牌可被伪造。
    jwt_secret: str = ""
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ---- 管理员初始账号（仅首次启动建号时使用；密码同样不设默认值）----
    admin_username: str = "admin"
    admin_password: str = ""

    # ---- CORS：允许访问的前端来源，多个用逗号分隔 ----
    cors_origins: str = "http://127.0.0.1:5173"
    cors_allow_credentials: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的 CORS 来源拆成去空白后的列表。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_startup_config(self) -> None:
        """启动时校验必填配置，缺失即抛错（绝不静默使用不安全默认值）。

        Raises:
            RuntimeError: 当 JWT_SECRET 未配置时。
        """
        if not self.jwt_secret:
            raise RuntimeError(
                "缺少必填配置 JWT_SECRET。请在 backend/.env 中设置一个随机长字符串，例如：\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(48))"\n'
                "再写入 backend/.env：JWT_SECRET=<上面输出的字符串>"
            )


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
