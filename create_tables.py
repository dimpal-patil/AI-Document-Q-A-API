import asyncio
print("Step 1: importing database...")
from app.core.database import engine, Base
print("Step 2: importing models...")
from app.models.models import User, Document, DocumentChunk, Question
print("Step 3: tables registered:", list(Base.metadata.tables.keys()))

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully")

asyncio.run(create_tables())
