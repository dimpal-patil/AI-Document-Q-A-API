import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.models import Document, DocumentChunk
from app.services.document_service import (
    extract_text, chunk_text, get_embeddings_batch
)

router = APIRouter()


async def process_document(document_id: str, file_path: str, file_type: str):
    """Background task: extract text, chunk, embed, store."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
        doc = result.scalar_one_or_none()
        if not doc:
            return

        try:
            # Extract text
            text = extract_text(file_path, file_type)
            if not text:
                doc.status = "failed"
                await db.commit()
                return

            # Chunk text
            chunks = chunk_text(text)

            # Get embeddings in batch (efficient — one API call)
            embeddings = await get_embeddings_batch(chunks)

            # Store chunks with embeddings
            for i, (chunk_text_content, embedding) in enumerate(zip(chunks, embeddings)):
                chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk_text_content,
                    embedding=embedding,
                )
                db.add(chunk)

            doc.status = "ready"
            doc.chunk_count = len(chunks)
            await db.commit()

        except Exception as e:
            doc.status = "failed"
            await db.commit()


@router.post("/upload", status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Validate file type
    ext = file.filename.split(".")[-1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed. Use: {settings.ALLOWED_EXTENSIONS}")

    # Validate file size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB")

    # Save file to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Create DB record
    doc = Document(
        owner_id=uuid.UUID(current_user["user_id"]),
        filename=safe_filename,
        original_filename=file.filename,
        file_type=ext,
        file_size=len(content),
        status="processing",
    )
    db.add(doc)
    await db.flush()

    # Kick off background processing
    background_tasks.add_task(process_document, str(doc.id), file_path, ext)

    return {
        "document_id": str(doc.id),
        "filename": file.filename,
        "status": "processing",
        "message": "Document uploaded. Processing in background — check status before asking questions.",
    }


@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.owner_id == uuid.UUID(current_user["user_id"]))
    )
    docs = result.scalars().all()
    return [
        {
            "document_id": str(d.id),
            "filename": d.original_filename,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "file_type": d.file_type,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if str(doc.owner_id) != current_user["user_id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "document_id": str(doc.id),
        "filename": doc.original_filename,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "file_size": doc.file_size,
        "file_type": doc.file_type,
        "created_at": doc.created_at.isoformat(),
    }


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if str(doc.owner_id) != current_user["user_id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete file from disk
    file_path = os.path.join(settings.UPLOAD_DIR, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    await db.delete(doc)