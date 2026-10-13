"""core/deps.py 鉴权依赖测试：令牌类型/有效性校验与管理员权限判定。"""

import jwt
import pytest
from fastapi import HTTPException

from app.config import settings
from app.core.deps import get_current_admin_user, get_current_user
from app.core.security import create_access_token, create_refresh_token


class TestGetCurrentUser:
    def test_valid_access_token(self, normal_user, db_session):
        token = create_access_token(normal_user.id)
        user = get_current_user(token=token, db=db_session)
        assert user.id == normal_user.id

    def test_rejects_refresh_token(self, normal_user, db_session):
        # 刷新令牌不能当访问令牌用
        token = create_refresh_token(normal_user.id)
        with pytest.raises(HTTPException) as exc:
            get_current_user(token=token, db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_garbage_token(self, db_session):
        with pytest.raises(HTTPException) as exc:
            get_current_user(token="garbage", db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_token_signed_with_other_secret(self, normal_user, db_session):
        forged = jwt.encode(
            {"sub": str(normal_user.id), "type": "access"}, "wrong-secret", algorithm="HS256"
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(token=forged, db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_deleted_user(self, db_session):
        # 令牌本身有效，但用户已不存在
        token = create_access_token(424242)
        with pytest.raises(HTTPException) as exc:
            get_current_user(token=token, db=db_session)
        assert exc.value.status_code == 401

    def test_rejects_expired_token(self, normal_user, db_session, monkeypatch):
        monkeypatch.setattr(settings, "access_token_expire_minutes", -1)  # 立即过期
        token = create_access_token(normal_user.id)
        with pytest.raises(HTTPException) as exc:
            get_current_user(token=token, db=db_session)
        assert exc.value.status_code == 401


class TestGetCurrentAdminUser:
    def test_admin_passes(self, admin_user):
        assert get_current_admin_user(user=admin_user).id == admin_user.id

    def test_normal_user_forbidden(self, normal_user):
        with pytest.raises(HTTPException) as exc:
            get_current_admin_user(user=normal_user)
        assert exc.value.status_code == 403
