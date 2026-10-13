"""会话管理 + 问答接口（流式返回 + 引用片段）。"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# 对外统一的失败文案：绝不把原始异常（可能含文件路径、密钥、内网地址）吐给前端，
# 详情只写进服务端日志。
_GENERATION_FAILED = "回答生成失败，请稍后重试"
_FAILED_ANSWER = "（回答生成失败，请稍后重试）"
_INTERRUPTED_ANSWER = "（回答已中断）"


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
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 200))
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
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_conversation(conv_id, user, db)
    return (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )


# ============ 问答（核心） ============


async def _client_gone(request: Request) -> bool:
    """判断客户端是否已断开；判断本身出错时按「未断开」处理，不能因此中断回答。"""
    try:
        return await request.is_disconnected()
    except Exception:  # pragma: no cover - 仅在底层连接异常时触发
        return False


def _persist_assistant_message(conv_id: int, answer: str, sources: list[dict]) -> None:
    """用独立的短生命周期会话保存客服回答，并刷新会话更新时间。

    独立会话的原因：StreamingResponse 的生成器在请求级依赖（db）已经关闭之后仍在运行，
    复用那个 Session 会踩到「会话已关闭 / 跨线程」的坑。落库失败只记日志，
    不能反过来把已经流给用户的回答变成报错。
    """
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
    except Exception:
        db.rollback()
        logger.exception("保存客服回答失败 conversation_id=%s", conv_id)
    finally:
        db.close()


@router.post("/chat")
async def chat(
    data: ChatRequest,
    request: Request,
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
        logger.warning("追问改写失败，改用原始问题 conversation_id=%s", conv_id, exc_info=True)
        standalone = question

    docs = await run_in_threadpool(rag.retrieve_with_rerank, standalone)
    context = rag.format_context(docs)
    sources = rag.build_sources(docs)

    async def event_stream():
        # 第一条：告知前端会话 ID（新建时会话可能刚创建）+ 引用片段
        yield _sse({"type": "start", "data": {"conversation_id": conv_id, "sources": sources}})

        parts: list[str] = []
        try:
            chain = rag.build_answer_chain()
            async for chunk in chain.astream({"context": context, "question": question}):
                # 客户端中途关闭页面或切换会话时及时收手，不继续消耗模型调用
                if await _client_gone(request):
                    logger.info("客户端已断开，停止生成 conversation_id=%s", conv_id)
                    _persist_assistant_message(
                        conv_id, "".join(parts) or _INTERRUPTED_ANSWER, sources
                    )
                    return
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    parts.append(token)
                    yield _sse({"type": "token", "data": token})
        except asyncio.CancelledError:
            # 服务端取消任务（常见于客户端断开）：同样补一条记录，避免会话里留下悬空的提问
            logger.info("生成任务被取消 conversation_id=%s", conv_id)
            _persist_assistant_message(conv_id, "".join(parts) or _INTERRUPTED_ANSWER, sources)
            raise
        except Exception:
            # 详情只进日志；对外只给统一文案 + 机器可读的 code
            logger.exception("生成回答失败 conversation_id=%s", conv_id)
            _persist_assistant_message(conv_id, "".join(parts) or _FAILED_ANSWER, sources)
            yield _sse({"type": "error", "code": "generation_failed", "data": _GENERATION_FAILED})
            return

        _persist_assistant_message(conv_id, "".join(parts), sources)
        yield _sse({"type": "done"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
