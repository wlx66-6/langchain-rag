"""FastAPI 入口：启动时校验配置、建表并初始化管理员账号，挂载各路由。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User
from app.routers import auth, chat, knowledge

logger = logging.getLogger(__name__)


def seed_admin() -> None:
    """首次启动时创建管理员账号（账号与密码均来自配置，不再硬编码）。

    未配置 ADMIN_PASSWORD 时跳过建号并告警——宁可没有管理员账号，
    也不使用可被猜测的默认密码。
    """
    if not settings.admin_password:
        logger.warning(
            "未配置 ADMIN_PASSWORD，跳过管理员账号初始化。如需知识库管理功能，"
            "请在 backend/.env 中设置 ADMIN_USERNAME / ADMIN_PASSWORD。"
        )
        return

    db = SessionLocal()
    try:
        exists = (
            db.query(User).filter(User.username == settings.admin_username).first()
        )
        if not exists:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    is_admin=True,
                )
            )
            db.commit()
            logger.info("已创建管理员账号：%s", settings.admin_username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_startup_config()  # 必填配置缺失时直接失败，不静默降级
    Base.metadata.create_all(bind=engine)  # 自动建表
    seed_admin()
    yield


app = FastAPI(title="电商知识库问答系统", version="1.0.0", lifespan=lifespan)

# 允许的前端来源从配置读取（默认仅本机 5173），不再对全网放开
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(knowledge.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.qwen_model}