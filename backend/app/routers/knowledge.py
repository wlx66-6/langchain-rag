"""知识库管理接口（仅管理员可用）：上传、列表、删除文档。"""
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

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)
):
    return (
        db.query(KnowledgeDocument)
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    ext = loader.check_allowed(file.filename)

    # 保存原始文件到 uploads 目录
    save_path = Path(settings.upload_dir) / f"{uuid4().hex}{ext}"
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 先建一条文档记录
    doc = KnowledgeDocument(
        filename=file.filename, file_type=ext.lstrip("."), status="ready"
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
            c.metadata["doc_id"] = doc.id          # 便于按文档删除
        if chunks:
            get_vectorstore().add_documents(chunks)

        doc.chunk_count = len(chunks)
        doc.status = "ready"
        db.commit()
        db.refresh(doc)
    except Exception as exc:
        doc.status = "failed"
        db.commit()
        # 删除可能已写入的一部分向量，避免残留半截数据
        try:
            get_vectorstore().delete(where={"doc_id": doc.id})
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"文档入库失败：{exc}")

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

    # 删除向量库里属于该文档的所有片段
    try:
        get_vectorstore().delete(where={"doc_id": doc_id})
    except Exception:
        pass

    db.delete(doc)
    db.commit()
    return {"message": "已删除"}