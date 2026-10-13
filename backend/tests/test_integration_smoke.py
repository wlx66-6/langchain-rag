"""集成冒烟测试：真实数据库 + 真实应用生命周期，覆盖账号体系与权限主流程。

与单元测试的区别：本文件**不使用**临时库与打桩，直接跑真实的应用启动流程
（建表、初始化管理员）与真实的 data/app.db，因此默认被 pytest.ini 标记跳过。
按需运行：

    cd backend
    ../venv/Scripts/python.exe -m pytest -m integration -v

前置条件：backend/.env 中已配置 JWT_SECRET；如需验管理员流程还需配置
ADMIN_USERNAME / ADMIN_PASSWORD。
"""

import random

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    if not settings.jwt_secret:
        pytest.skip("未配置 JWT_SECRET，跳过集成冒烟测试")
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers(client):
    if not settings.admin_password:
        pytest.skip("未配置 ADMIN_PASSWORD，跳过管理员相关断言")
    r = client.post(
        "/api/auth/login",
        json={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.fixture(scope="module")
def user_headers(client):
    username = f"smoke{random.randint(1000, 9999)}"
    r = client.post("/api/auth/register", json={"username": username, "password": "smoke123456"})
    assert r.status_code == 201, r.text
    # 重复注册应被拒
    dup = client.post("/api/auth/register", json={"username": username, "password": "smoke123456"})
    assert dup.status_code == 400

    r = client.post("/api/auth/login", json={"username": username, "password": "smoke123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_wrong_password_rejected(client, user_headers):
    # 用一个不存在的用户名 + 错密码，必然是 401
    r = client.post("/api/auth/login", json={"username": "no-such-user", "password": "whatever"})
    assert r.status_code == 401


def test_me(client, user_headers):
    r = client.get("/api/auth/me", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["username"].startswith("smoke")


def test_normal_user_cannot_manage_knowledge(client, user_headers):
    assert client.get("/api/knowledge/documents", headers=user_headers).status_code == 403


def test_admin_can_list_knowledge(client, admin_headers):
    r = client.get("/api/knowledge/documents", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_conversations_flow(client, user_headers):
    assert client.get("/api/conversations", headers=user_headers).status_code == 200


def test_change_password(client, user_headers):
    r = client.post(
        "/api/auth/change-password",
        json={"old_password": "smoke123456", "new_password": "smoke654321"},
        headers=user_headers,
    )
    assert r.status_code == 200
