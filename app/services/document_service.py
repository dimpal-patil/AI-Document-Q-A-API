import os
import uuid
import math
from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

CHUNK_SIZE = 800      # characters per chunk
CHUNK_OVERLAP = 100   # overlap between chunks


# ── Text extraction ──────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    import pypdf
    text = ""
    with open(file_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text.strip()


def extract_text_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def extract_text_from_docx(file_path: str) -> str:
    import docx
    doc = docx.Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs if para.text).strip()


def extract_text(file_path: str, file_type: str) -> str:
    extractors = {
        "pdf": extract_text_from_pdf,
        "txt": extract_text_from_txt,
        "docx": extract_text_from_docx,
    }
    extractor = extractors.get(file_type)
    if not extractor:
        raise ValueError(f"Unsupported file type: {file_type}")
    return extractor(file_path)


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks for better context retrieval."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # Try to break at a sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            if last_period > chunk_size // 2:
                end = start + last_period + 1
                chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if c]


# ── Embeddings ───────────────────────────────────────────────────────────────

async def get_embedding(text: str) -> list[float]:
    response = await client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Get embeddings for multiple texts in one API call."""
    response = await client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


# ── Similarity search ─────────────────────────────────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_relevant_chunks(
    query_embedding: list[float],
    chunks: list[dict],  # [{"index": int, "content": str, "embedding": list}]
    top_k: int = 4,
) -> list[dict]:
    scored = [
        {**chunk, "score": cosine_similarity(query_embedding, chunk["embedding"])}
        for chunk in chunks
        if chunk.get("embedding")
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ── GPT-4 Q&A ─────────────────────────────────────────────────────────────────

async def answer_question(question: str, context_chunks: list[dict]) -> dict:
    context = "\n\n---\n\n".join(
        f"[Source {i+1}]\n{chunk['content']}"
        for i, chunk in enumerate(context_chunks)
    )

    system_prompt = """You are a helpful assistant that answers questions based strictly on the provided document context.

Rules:
- Answer only from the provided context. Do not use outside knowledge.
- If the answer is not in the context, say "I couldn't find this information in the document."
- Always cite which source(s) you used (e.g. "According to Source 1...").
- Be concise and accurate."""

    user_prompt = f"""Context from document:
{context}

Question: {question}

Answer:"""

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )

    answer = response.choices[0].message.content
    source_indices = [chunk["chunk_index"] for chunk in context_chunks]

    return {
        "answer": answer,
        "source_chunks": source_indices,
        "model": settings.OPENAI_MODEL,
        "tokens_used": response.usage.total_tokens,
    }