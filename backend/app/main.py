"""FastAPI 入口：启动时建表并内置管理员账号，挂载各路由。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User
from app.routers import auth, chat, knowledge


def seed_admin():
    """启动时确保存在管理员账号 admin / 123456。"""
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(
                User(
                    username="admin",
                    password_hash=hash_password("123456"),
                    is_admin=True,
                )
            )
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # 自动建表
    seed_admin()
    yield


app = FastAPI(title="电商知识库问答系统", version="1.0.0", lifespan=lifespan)

# 开发阶段放开跨域，方便前端直连；后续可用 Vite 代理替代
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(knowledge.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.qwen_model}