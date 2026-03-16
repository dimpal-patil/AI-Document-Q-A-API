import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.cache import cache_get, cache_set, make_cache_key
from app.models.models import Document, DocumentChunk, Question
from app.services.document_service import get_embedding, find_relevant_chunks, answer_question

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    top_k: int = 4  # number of chunks to retrieve


@router.post("/{document_id}/ask")
async def ask_question(
    document_id: str,
    payload: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Validate document
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if str(doc.owner_id) != current_user["user_id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    if doc.status != "ready":
        raise HTTPException(status_code=400, detail=f"Document is not ready yet. Status: {doc.status}")

    # Check Redis cache first
    cache_key = make_cache_key("qa", document_id, payload.question.lower().strip())
    cached = await cache_get(cache_key)
    if cached:
        return {**cached, "cached": True}

    # Get all chunks for this document
    chunks_result = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
    )
    chunks = chunks_result.scalars().all()

    if not chunks:
        raise HTTPException(status_code=400, detail="Document has no processable content")

    # Embed the question
    query_embedding = await get_embedding(payload.question)

    # Find most relevant chunks via cosine similarity
    chunk_dicts = [
        {"chunk_index": c.chunk_index, "content": c.content, "embedding": c.embedding}
        for c in chunks
    ]
    relevant_chunks = find_relevant_chunks(query_embedding, chunk_dicts, top_k=payload.top_k)

    # Ask GPT-4
    result_data = await answer_question(payload.question, relevant_chunks)

    # Save question to DB
    question_record = Question(
        document_id=uuid.UUID(document_id),
        user_id=uuid.UUID(current_user["user_id"]),
        question=payload.question,
        answer=result_data["answer"],
        source_chunks=result_data["source_chunks"],
        cached=False,
    )
    db.add(question_record)
    await db.flush()

    response = {
        "question_id": str(question_record.id),
        "question": payload.question,
        "answer": result_data["answer"],
        "source_chunks": result_data["source_chunks"],
        "model": result_data["model"],
        "tokens_used": result_data["tokens_used"],
        "cached": False,
    }

    # Cache the result
    await cache_set(cache_key, response)

    return response


@router.get("/{document_id}/history")
async def get_question_history(
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

    questions_result = await db.execute(
        select(Question)
        .where(Question.document_id == uuid.UUID(document_id))
        .order_by(Question.created_at.desc())
    )
    questions = questions_result.scalars().all()

    return [
        {
            "question_id": str(q.id),
            "question": q.question,
            "answer": q.answer,
            "source_chunks": q.source_chunks,
            "cached": q.cached,
            "asked_at": q.created_at.isoformat(),
        }
        for q in questions
    ]