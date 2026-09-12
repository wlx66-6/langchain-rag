"""会话管理 + 问答接口（流式返回 + 引用片段）。"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import SessionLocal, get_db
from app.models import Conversation, Message, User
from app.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationOut,
    ConversationRename,
    MessageOut,
)
from app.services import rag

router = APIRouter(prefix="/api", tags=["chat"])


def _sse(data: dict) -> str:
    """封装一条 SSE 事件（前端按 data: {...} 逐行接收）。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_owned_conversation(conv_id: int, user: User, db: Session) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


# ============ 会话管理 ============

@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = Conversation(user_id=user.id, title=data.title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.patch("/conversations/{conv_id}", response_model=ConversationOut)
def rename_conversation(
    conv_id: int,
    data: ConversationRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_owned_conversation(conv_id, user, db)
    conv.title = data.title
    db.commit()
    db.refresh(conv)
    return conv


@router.delete("/conversations/{conv_id}")
def delete_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_owned_conversation(conv_id, user, db)
    db.delete(conv)
    db.commit()
    return {"message": "已删除"}


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def get_messages(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_conversation(conv_id, user, db)
    return (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )


# ============ 问答（核心） ============

@router.post("/chat")
async def chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1) 找到指定会话，或新建一个
    if data.conversation_id:
        conv = _get_owned_conversation(data.conversation_id, user, db)
    else:
        conv = Conversation(user_id=user.id, title=data.content[:20] or "新会话")
        db.add(conv)
        db.commit()
        db.refresh(conv)
    conv_id = conv.id

    # 2) 取最近几条历史，用于「追问改写」（理解“它多少钱”这种问题）
    history_rows = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.id.desc())
        .limit(6)
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]

    # 3) 先保存用户这一条提问
    db.add(Message(conversation_id=conv_id, role="user", content=data.content))
    db.commit()

    # 4) 追问改写 + 检索（在开始流式输出之前完成）
    question = data.content
    try:
        standalone = await rag.rewrite_question(question, history)
    except Exception:
        standalone = question  # 改写失败不影响主流程

    docs = await run_in_threadpool(rag.retrieve_with_rerank, standalone)
    context = rag.format_context(docs)
    sources = rag.build_sources(docs)

    async def event_stream():
        # 第一条：告知前端会话 ID（新建时会话可能刚创建）+ 引用片段
        yield _sse({"type": "start", "data": {"conversation_id": conv_id, "sources": sources}})

        # 再逐段推送回答
        parts: list[str] = []
        chain = rag.build_answer_chain()
        try:
            async for chunk in chain.astream({"context": context, "question": question}):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    parts.append(token)
                    yield _sse({"type": "token", "data": token})
        except Exception as exc:  # 生成失败时给前端一个明确提示
            yield _sse({"type": "error", "data": f"生成回答失败：{exc}"})
            return

        answer = "".join(parts)
        _save_assistant_message(conv_id, answer, sources)
        yield _sse({"type": "done"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _save_assistant_message(conv_id: int, answer: str, sources: list[dict]):
    """用独立的数据库会话保存客服回答，并刷新会话的更新时间。"""
    db = SessionLocal()
    try:
        db.add(
            Message(
                conversation_id=conv_id,
                role="assistant",
                content=answer,
                citations=json.dumps(sources, ensure_ascii=False),
            )
        )
        conv = db.get(Conversation, conv_id)
        if conv:
            conv.updated_at = datetime.now()
        db.commit()
    finally:
        db.close()