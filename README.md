# 🤖 AI Document Q&A API

A production-ready REST API that lets users upload documents (PDF, DOCX, TXT) and ask natural language questions about them — powered by **GPT-4**, **FastAPI**, **PostgreSQL**, and **Redis**.

---

## ✨ Features

- 📄 **Document Upload** — supports PDF, DOCX, and TXT files up to 10MB
- 🧠 **GPT-4 Q&A** — answers questions grounded strictly in document content with source citations
- ⚡ **Redis Caching** — repeated questions return instantly without hitting the OpenAI API
- 🔐 **JWT Auth + RBAC** — secure user registration, login, and role-based access control
- 🔍 **Semantic Search** — uses OpenAI embeddings + cosine similarity to find relevant chunks
- 📦 **Fully Dockerized** — one command to run the full stack
- 🧪 **Test Suite** — unit and integration tests with pytest

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────┐
│   Client    │────▶│              FastAPI App                  │
└─────────────┘     │  ┌──────────┐  ┌──────────┐  ┌────────┐ │
                    │  │  /auth   │  │  /docs   │  │  /qa   │ │
                    │  └──────────┘  └──────────┘  └────────┘ │
                    └──────────────────────────────────────────┘
                           │               │              │
                    ┌──────▼──────┐ ┌──────▼──────┐ ┌────▼──────┐
                    │ PostgreSQL  │ │    Redis    │ │  OpenAI   │
                    │  (storage)  │ │   (cache)   │ │   GPT-4   │
                    └─────────────┘ └─────────────┘ └───────────┘
```

**Flow when asking a question:**
1. User uploads document → stored on disk, text extracted and chunked
2. Each chunk is embedded via `text-embedding-3-small` and stored in PostgreSQL
3. User asks a question → question is embedded → cosine similarity finds top-K chunks
4. Top chunks + question sent to GPT-4 → answer returned with source citations
5. Result cached in Redis for identical future queries

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone & configure
```bash
git clone https://github.com/your-username/ai-doc-qa.git
cd ai-doc-qa
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Run
```bash
docker-compose up --build
```

API is live at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

---

## 📡 API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Get JWT token |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload a document |
| GET | `/api/v1/documents/` | List your documents |
| GET | `/api/v1/documents/{id}` | Get document status |
| DELETE | `/api/v1/documents/{id}` | Delete a document |

### Questions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/questions/{doc_id}/ask` | Ask a question |
| GET | `/api/v1/questions/{doc_id}/history` | View Q&A history |

---

## 💡 Example Usage

```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "yourpassword"}'

# 2. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=you@example.com&password=yourpassword" | jq -r .access_token)

# 3. Upload a document
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@report.pdf"

# 4. Ask a question
curl -X POST http://localhost:8000/api/v1/questions/{document_id}/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key findings in this report?"}'
```

**Example response:**
```json
{
  "question": "What are the key findings in this report?",
  "answer": "According to Source 1, the key findings include... According to Source 3, the report also highlights...",
  "source_chunks": [0, 2, 5],
  "model": "gpt-4o",
  "tokens_used": 612,
  "cached": false
}
```

---

## 🧪 Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL + SQLAlchemy (async) |
| Cache | Redis |
| AI | OpenAI GPT-4o + text-embedding-3-small |
| Auth | JWT (python-jose) + bcrypt |
| Containers | Docker + Docker Compose |
| Testing | pytest + pytest-asyncio |

---

## 📁 Project Structure

```
ai-doc-qa/
├── app/
│   ├── api/
│   │   ├── auth.py          # Register & login endpoints
│   │   ├── documents.py     # Upload, list, delete documents
│   │   └── questions.py     # Ask questions, view history
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   ├── database.py      # Async SQLAlchemy engine & session
│   │   ├── security.py      # JWT, bcrypt, RBAC helpers
│   │   └── cache.py         # Redis cache helpers
│   ├── models/
│   │   └── models.py        # SQLAlchemy ORM models
│   ├── services/
│   │   └── document_service.py  # Text extraction, chunking, embeddings, GPT-4
│   └── main.py              # FastAPI app entry point
├── tests/
│   └── test_app.py          # Unit + integration tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## 👤 Author

**Dimpal Patil** — Python Backend Developer  
 • [GitHub](https://github.com/dimpal-patil)