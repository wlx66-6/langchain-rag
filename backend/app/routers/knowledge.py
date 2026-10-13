"""知识库管理接口（仅管理员可用）：上传、列表、删除文档。"""

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_admin_user
from app.database import get_db
from app.models import KnowledgeDocument, User
from app.schemas import DocumentOut
from app.services import loader, splitter
from app.services.vectorstore import get_vectorstore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

_CHUNK_SIZE = 1024 * 1024  # 分块读取上传文件，避免大文件一次性撑爆内存


async def _read_upload(file: UploadFile) -> bytes:
    """分块读取上传内容，一旦超过上限立刻拒绝，不把整个文件读进内存。

    Raises:
        HTTPException: 文件超过 settings.max_upload_size 时返回 413。
    """
    limit = settings.max_upload_size
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"文件过大，单个文件最大 {limit // (1024 * 1024)} MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _cleanup_vectors(doc_id: int) -> None:
    """删除某文档在向量库里的全部片段；失败只记日志，不阻断主流程。"""
    try:
        get_vectorstore().delete(where={"doc_id": doc_id})
    except Exception:
        logger.warning("删除向量失败，可能残留孤儿向量 doc_id=%s", doc_id, exc_info=True)


def _remove_stored_file(stored_path: str | None) -> None:
    """删除文档对应的物理文件；文件不存在视为成功。"""
    if not stored_path:
        return
    try:
        Path(stored_path).unlink(missing_ok=True)
    except OSError:
        logger.warning("删除物理文件失败 path=%s", stored_path, exc_info=True)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(KnowledgeDocument)
        .order_by(KnowledgeDocument.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 200))
        .all()
    )


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    try:
        ext = loader.check_allowed(file.filename or "")
    except ValueError as exc:
        # 不支持的格式属于用户输入问题，返回 400 而不是让它冒泡成 500
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    content = await _read_upload(file)

    # 保存原始文件到 uploads 目录（文件名用随机串，避免同名覆盖与路径穿越）
    save_path = Path(settings.upload_dir) / f"{uuid4().hex}{ext}"
    save_path.write_bytes(content)

    # 先建一条文档记录
    doc = KnowledgeDocument(
        filename=file.filename,
        file_type=ext.lstrip("."),
        status="ready",
        stored_path=str(save_path),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 解析 → 切块 → 向量化 → 入库
    try:
        raw_docs = loader.load_file(save_path, file.filename)
        chunks = splitter.split_documents(raw_docs)
        for c in chunks:
            c.metadata["source"] = file.filename  # 引用时展示的文件名
            c.metadata["doc_id"] = doc.id  # 便于按文档删除
        if chunks:
            get_vectorstore().add_documents(chunks)

        doc.chunk_count = len(chunks)
        doc.status = "ready"
        db.commit()
        db.refresh(doc)
    except Exception as exc:
        logger.exception("文档入库失败 doc_id=%s filename=%s", doc.id, file.filename)
        doc.status = "failed"
        db.commit()
        # 删除可能已写入的一部分向量，避免残留半截数据
        _cleanup_vectors(doc.id)
        # 详情只进日志，对外给统一文案，避免把内部路径/堆栈暴露给前端
        raise HTTPException(status_code=500, detail="文档入库失败，请检查文件内容后重试") from exc

    return doc


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 向量、物理文件、数据库记录三者一起清理，避免留下孤儿数据
    _cleanup_vectors(doc_id)
    _remove_stored_file(doc.stored_path)

    db.delete(doc)
    db.commit()
    return {"message": "已删除"}
