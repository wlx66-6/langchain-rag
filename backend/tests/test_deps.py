"""core/deps.py 鉴权依赖测试：令牌类型/有效性校验与管理员权限判定。"""

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.core.deps import get_current_admin_user, get_current_user
from app.core.security import create_access_token, create_refresh_token


def _creds(token: str) -> HTTPAuthorizationCredentials:
    """构造一个「Authorization: Bearer <token>」解析后的凭据对象。"""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestGetCurrentUser:
    def test_valid_access_token(self, normal_user, db_session):
        token = create_access_token(normal_user.id)
        user = get_current_user(creds=_creds(token), db=db_session)
        assert user.id == normal_user.id

    def test_rejects_missing_credentials(self, db_session):
        # 请求头里没带 Authorization 时，bearer_scheme(auto_error=False) 返回 None
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=None, db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_refresh_token(self, normal_user, db_session):
        # 刷新令牌不能当访问令牌用
        token = create_refresh_token(normal_user.id)
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_creds(token), db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_garbage_token(self, db_session):
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_creds("garbage"), db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_token_signed_with_other_secret(self, normal_user, db_session):
        forged = jwt.encode(
            {"sub": str(normal_user.id), "type": "access"}, "wrong-secret", algorithm="HS256"
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_creds(forged), db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_deleted_user(self, db_session):
        # 令牌本身有效，但用户已不存在
        token = create_access_token(424242)
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_creds(token), db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_expired_token(self, normal_user, db_session, monkeypatch):
        monkeypatch.setattr(settings, "access_token_expire_minutes", -1)  # 立即过期
        token = create_access_token(normal_user.id)
        with pytest.raises(HTTPException) as exc:
            get_current_user(creds=_creds(token), db=db_session)
        assert exc.value.status_code == 401


class TestGetCurrentAdminUser:
    def test_admin_passes(self, admin_user):
        assert get_current_admin_user(user=admin_user).id == admin_user.id

    def test_normal_user_forbidden(self, normal_user):
        with pytest.raises(HTTPException) as exc:
            get_current_admin_user(user=normal_user)
        assert exc.value.status_code == 403


class TestOpenApiSecurityContract:
    """守住 /docs 页面的 Authorize 按钮可用。

    历史问题：这里曾用 `OAuth2PasswordBearer(tokenUrl="/api/auth/login")`。它会让 OpenAPI
    声明一条「OAuth2 密码流」，于是 Swagger 的 Authorize 按钮按表单去调登录接口——而登录
    接口收的是 JSON body，必然返回 422，等于 README 里推荐的调试入口是坏的。
    改用 HTTPBearer 后，Authorize 变成「直接粘贴 access_token」，与实际鉴权方式一致。
    """

    def test_security_scheme_is_http_bearer(self, client):
        schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]
        assert "OAuth2PasswordBearer" not in schemes
        assert schemes["HTTPBearer"]["type"] == "http"
        assert schemes["HTTPBearer"]["scheme"] == "bearer"

    def test_login_accepts_json_body(self, client):
        """HTTPBearer 方案成立的前提：登录接口收 JSON 而非 OAuth2 表单。"""
        r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        assert r.status_code == 401  # 凭据错误；若是 422 说明 body 格式不被接受

    def test_missing_authorization_header_returns_401(self, client):
        # 缺凭据必须是 401（而非 HTTPBearer 默认的 403）
        assert client.get("/api/auth/me").status_code == 401
