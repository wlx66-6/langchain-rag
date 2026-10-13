"""数据库连接：使用 SQLite + SQLAlchemy。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# check_same_thread=False 是 SQLite 专用开关：FastAPI 用线程池处理请求，
# 允许同一个数据文件被多个线程访问；pool_pre_ping=True 让连接在复用前先探活，
# 避免拿到已被 WAL 检查点或进程重启关闭的陈旧连接。
engine = create_engine(
    settings.sqlite_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """每条新连接都设置 WAL 与锁等待，缓解并发写入时的 database is locked。

    - journal_mode=WAL：读写不再互相阻塞，是 SQLite 支持并发读写的关键
    - busy_timeout=5000：写锁被占用时最多等 5 秒再报错，而不是立刻失败
    - synchronous=NORMAL：WAL 模式下的推荐值，兼顾安全与写入性能
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖：每个请求开一个数据库会话，用完自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
