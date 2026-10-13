"""请求 / 响应的数据结构定义（Pydantic）。"""
from datetime import datetime

from pydantic import BaseModel, Field

# ============ 账号相关 ============

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=72)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_admin: bool


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ============ 会话相关 ============

class ConversationCreate(BaseModel):
    title: str = "新会话"


class ConversationRename(BaseModel):
    title: str


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: str | None = None  # JSON 字符串，前端自行解析
    created_at: datetime

    model_config = {"from_attributes": True}


# ============ 问答相关 ============

class ChatRequest(BaseModel):
    conversation_id: int | None = None  # 为空表示新建会话
    content: str = Field(min_length=1)


# ============ 知识库相关 ============

class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}