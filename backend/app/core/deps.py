"""权限依赖：从请求头里取出令牌，识别当前用户身份。"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models import User

# 前端请求头需带 Authorization: Bearer <access_token>。
#
# 这里用 HTTPBearer 而不是 OAuth2PasswordBearer：OAuth2 的密码流要求登录接口接收
# x-www-form-urlencoded 表单，而本项目的 /api/auth/login 收的是 JSON body——若用前者，
# /docs 页面的 Authorize 按钮会按表单去调登录接口并报 422，等于文档里给的调试入口是坏的。
# HTTPBearer 对应「直接粘贴一个 Bearer token」，与实际鉴权方式一致。
#
# auto_error=False：缺少凭据时不由 FastAPI 抛它默认的 403，而是走下面统一的 401 文案。
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录状态无效或已过期，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise cred_exc

    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        # 令牌无效属于预期内的鉴权失败，用 from None 掐断异常链，
        # 避免把 jwt 内部的解密细节带进日志
        raise cred_exc from None

    if payload.get("type") != "access":
        raise cred_exc

    user_id = payload.get("sub")
    if user_id is None:
        raise cred_exc

    user = db.get(User, int(user_id))
    if user is None:
        raise cred_exc
    return user


def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    """只有管理员才能使用（用于知识库管理接口）。"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以执行此操作")
    return user
