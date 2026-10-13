"""/api/auth 路由测试：注册、登录、刷新令牌、改密码、当前用户（走临时库，不联网）。"""
from app.core.security import create_access_token, create_refresh_token


class TestRegister:
    def test_register_success(self, client):
        r = client.post("/api/auth/register", json={"username": "newbie", "password": "abc123"})
        assert r.status_code == 201
        body = r.json()
        assert body["username"] == "newbie"
        assert body["is_admin"] is False
        assert "password" not in body  # 绝不回传任何密码字段

    def test_register_duplicate_username(self, client, normal_user):
        r = client.post(
            "/api/auth/register",
            json={"username": normal_user.username, "password": "abc123"},
        )
        assert r.status_code == 400
        assert "占用" in r.json()["detail"]

    def test_register_too_short_password(self, client):
        r = client.post("/api/auth/register", json={"username": "shorty", "password": "123"})
        assert r.status_code == 422  # 由 Pydantic 校验拦下

    def test_register_too_short_username(self, client):
        r = client.post("/api/auth/register", json={"username": "x", "password": "abc123"})
        assert r.status_code == 422


class TestLogin:
    def test_login_success(self, client, normal_user):
        r = client.post(
            "/api/auth/login",
            json={"username": normal_user.username, "password": "secret123"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"
        assert body["is_admin"] is False

    def test_admin_login_reports_admin(self, client, admin_user):
        r = client.post(
            "/api/auth/login",
            json={"username": admin_user.username, "password": "secret123"},
        )
        assert r.status_code == 200
        assert r.json()["is_admin"] is True

    def test_login_wrong_password(self, client, normal_user):
        r = client.post(
            "/api/auth/login",
            json={"username": normal_user.username, "password": "wrong-password"},
        )
        assert r.status_code == 401
        assert "用户名或密码错误" in r.json()["detail"]

    def test_login_unknown_user(self, client):
        r = client.post("/api/auth/login", json={"username": "ghost", "password": "abc123"})
        assert r.status_code == 401


class TestRefresh:
    def test_refresh_success(self, client, normal_user):
        token = create_refresh_token(normal_user.id)
        r = client.post("/api/auth/refresh", json={"refresh_token": token})
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_refresh_rejects_access_token(self, client, normal_user):
        # 用「访问令牌」冒充刷新令牌应被拒（服务端校验 type == refresh）
        token = create_access_token(normal_user.id)
        r = client.post("/api/auth/refresh", json={"refresh_token": token})
        assert r.status_code == 401

    def test_refresh_rejects_garbage(self, client):
        r = client.post("/api/auth/refresh", json={"refresh_token": "not-a-jwt"})
        assert r.status_code == 401

    def test_refresh_unknown_user(self, client):
        token = create_refresh_token(999999)
        r = client.post("/api/auth/refresh", json={"refresh_token": token})
        assert r.status_code == 401
        assert "用户不存在" in r.json()["detail"]


class TestMe:
    def test_me_with_valid_token(self, client, normal_user, normal_token, bearer):
        r = client.get("/api/auth/me", headers=bearer(normal_token))
        assert r.status_code == 200
        assert r.json()["username"] == normal_user.username

    def test_me_without_token(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_with_garbage_token(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401


class TestChangePassword:
    def test_change_password_and_relogin(self, client, normal_user, normal_token, bearer):
        r = client.post(
            "/api/auth/change-password",
            json={"old_password": "secret123", "new_password": "brand-new-123"},
            headers=bearer(normal_token),
        )
        assert r.status_code == 200
        assert "成功" in r.json()["message"]

        # 旧密码失效、新密码可登录
        assert client.post(
            "/api/auth/login",
            json={"username": normal_user.username, "password": "secret123"},
        ).status_code == 401
        assert client.post(
            "/api/auth/login",
            json={"username": normal_user.username, "password": "brand-new-123"},
        ).status_code == 200

    def test_change_password_wrong_old(self, client, normal_token, bearer):
        r = client.post(
            "/api/auth/change-password",
            json={"old_password": "nope1234", "new_password": "brand-new-123"},
            headers=bearer(normal_token),
        )
        assert r.status_code == 400
        assert "原密码错误" in r.json()["detail"]

    def test_change_password_requires_login(self, client):
        r = client.post(
            "/api/auth/change-password",
            json={"old_password": "secret123", "new_password": "brand-new-123"},
        )
        assert r.status_code == 401