"""pytest 全局夹具。

设计要点：
1. 在导入任何 app 模块之前先设置 JWT_SECRET 等环境变量——pydantic-settings 的
   读取优先级是「环境变量 > .env 文件」，因此这里能压过开发者本地的 backend/.env，
   保证测试环境用的是固定的测试密钥。
2. 用「临时 SQLite 文件 + 覆盖 get_db 依赖」把接口测试与真实数据库隔离，
   跑完自动随 tmp 目录销毁。
3. 用 monkeypatch 把检索、重排、向量库、大模型等外部依赖打桩，
   让路由测试不联网、不加载向量模型即可稳定运行。
"""

import os

# ---- 必须在 import app.* 之前执行 ----
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
os.environ.setdefault("ADMIN_PASSWORD", "")  # 测试里不使用全局管理员，避免污染

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.routers import chat as chat_router  # noqa: E402

# ============ 数据库夹具 ============


@pytest.fixture()
def db_engine(tmp_path):
    """每个测试用例一个全新的临时 SQLite 文件，跑完即弃。"""
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def TestingSessionLocal(db_engine):
    """绑定到临时库的 Session 工厂。"""
    return sessionmaker(bind=db_engine, autocommit=False, autoflush=False)


@pytest.fixture()
def db_session(TestingSessionLocal):
    """测试中直接操作数据库用的会话。"""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(TestingSessionLocal, monkeypatch):
    """隔离后的 TestClient：请求走临时库，不走真实的 data/app.db。

    注意不要用 `with TestClient(app)`——那会触发 lifespan（建真实表、建管理员账号），
    这些副作用与测试无关，反而会污染真实数据文件。
    """

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    # chat.py 的 _save_assistant_message 用独立 Session 落库，这里也指向同一个临时库
    monkeypatch.setattr(chat_router, "SessionLocal", TestingSessionLocal)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ============ 用户与鉴权夹具 ============


@pytest.fixture()
def make_user(db_session):
    """工厂：在临时库里造一个用户，返回 ORM 对象。"""

    def _make(username: str = "alice", password: str = "secret123", is_admin: bool = False) -> User:
        user = User(
            username=username,
            password_hash=hash_password(password),
            is_admin=is_admin,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


@pytest.fixture()
def normal_user(make_user):
    """普通用户，默认密码 secret123。"""
    return make_user(username="buyer", password="secret123", is_admin=False)


@pytest.fixture()
def admin_user(make_user):
    """管理员用户。"""
    return make_user(username="boss", password="secret123", is_admin=True)


@pytest.fixture()
def bearer():
    """便捷构造请求头：bearer(token) -> {"Authorization": "Bearer ..."}"""

    def _bearer(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _bearer


@pytest.fixture()
def normal_token(normal_user) -> str:
    return create_access_token(normal_user.id)


@pytest.fixture()
def admin_token(admin_user) -> str:
    return create_access_token(admin_user.id)


# ============ RAG / 向量库打桩夹具 ============


@pytest.fixture()
def stub_rag(monkeypatch):
    """把「改写 / 检索 / 重排 / 生成」全部打桩，让 /api/chat 无需网络即可跑通。

    - 生成（build_answer_chain）改走本地 MockChatModel，不发网络请求；
    - 检索固定返回一段假文档，避免加载 bge-m3 向量模型。
    """
    from langchain_core.documents import Document

    from app.config import settings
    from app.services import rag

    monkeypatch.setattr(settings, "mock_llm", True)

    async def _fake_rewrite(question, history):  # noqa: ANN001
        return question

    def _fake_retrieve(question):  # noqa: ANN001
        return [
            (
                Document(
                    page_content="X1 耳机单次充电最长续航 40 小时。",
                    metadata={"source": "商品说明.txt"},
                ),
                0.95,
            )
        ]

    monkeypatch.setattr(rag, "rewrite_question", _fake_rewrite)
    monkeypatch.setattr(rag, "retrieve_with_rerank", _fake_retrieve)


@pytest.fixture()
def stub_vectorstore(monkeypatch, tmp_path):
    """把向量库替换成内存假实现，并把上传目录指向临时目录。"""
    from app.config import settings
    from app.routers import knowledge

    class _FakeVectorStore:
        def __init__(self):
            self.added = []
            self.deleted = []

        def add_documents(self, docs):  # noqa: ANN001
            self.added.extend(docs)

        def delete(self, where=None):  # noqa: ANN001
            self.deleted.append(where)

    store = _FakeVectorStore()
    monkeypatch.setattr(knowledge, "get_vectorstore", lambda: store)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    return store
