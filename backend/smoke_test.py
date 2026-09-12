"""冒烟测试：验证账号体系、权限、数据库等核心流程（不涉及大模型/向量模型）。"""
import random

from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as client:
    # 健康检查
    r = client.get("/api/health")
    print("health:", r.status_code, r.json())

    # 注册一个新用户
    uname = f"test{random.randint(1000, 9999)}"
    r = client.post("/api/auth/register", json={"username": uname, "password": "test123456"})
    print("register:", r.status_code, r.json().get("username"))

    # 重复注册应报 400
    r = client.post("/api/auth/register", json={"username": uname, "password": "x123456"})
    print("duplicate register (期望400):", r.status_code)

    # 管理员登录
    r = client.post("/api/auth/login", json={"username": "admin", "password": "123456"})
    print("admin login:", r.status_code, "is_admin=", r.json().get("is_admin"))
    admin_token = r.json()["access_token"]

    # 普通用户登录
    r = client.post("/api/auth/login", json={"username": uname, "password": "test123456"})
    print("normal login:", r.status_code, "is_admin=", r.json().get("is_admin"))
    normal_token = r.json()["access_token"]

    # 错误密码应报 401
    r = client.post("/api/auth/login", json={"username": uname, "password": "wrongpass"})
    print("wrong password (期望401):", r.status_code)

    # 当前用户信息
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {normal_token}"})
    print("me:", r.status_code, r.json().get("username"))

    # 管理员能看知识库列表
    r = client.get("/api/knowledge/documents", headers={"Authorization": f"Bearer {admin_token}"})
    print("admin knowledge list:", r.status_code, r.json())

    # 普通用户访问知识库应 403
    r = client.get("/api/knowledge/documents", headers={"Authorization": f"Bearer {normal_token}"})
    print("normal knowledge (期望403):", r.status_code)

    # 会话列表
    r = client.get("/api/conversations", headers={"Authorization": f"Bearer {normal_token}"})
    print("conversations:", r.status_code, r.json())

    # 改密码
    r = client.post(
        "/api/auth/change-password",
        json={"old_password": "test123456", "new_password": "new123456"},
        headers={"Authorization": f"Bearer {normal_token}"},
    )
    print("change password:", r.status_code, r.json())

    # 用新密码登录
    r = client.post("/api/auth/login", json={"username": uname, "password": "new123456"})
    print("login with new password:", r.status_code)

print("\n=== 冒烟测试结束 ===")