from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import documents, questions, auth
from app.core.config import settings

app = FastAPI(
    title="AI Document Q&A API",
    description="Upload documents and ask questions using GPT-4",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questions"])


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}