"""数据表定义：用户、会话、消息、知识库文档四张表。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now() -> datetime:
    return datetime.now()


class User(Base):
    """用户表：存账号、密码（加密后）、是否管理员。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    """会话表：一个用户可以有多个会话（类似微信群聊列表）。"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="新会话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """消息表：记录会话里的每条提问和回答。"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user=用户 / assistant=客服
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[str | None] = mapped_column(Text, nullable=True)  # 引用的知识库片段(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    conversation = relationship("Conversation", back_populates="messages")


class KnowledgeDocument(Base):
    """知识库文档表：记录每个上传入库的文档，方便管理员查看和删除。"""
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="ready")  # ready / failed
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)  # 切成了几段
    # 原文件在磁盘上的落盘路径：删文档时据此一并清理，避免留下无人认领的垃圾文件
    stored_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)