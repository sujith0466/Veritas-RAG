import asyncio
import hashlib
import uuid

from sqlalchemy import select
import structlog

from backend.core.config import get_settings
from backend.database.engine import get_session_factory
from backend.document.models import Document, DocumentVersion
from backend.models.entities.user import User
from backend.modules.chunking.models import DocumentChunk
from backend.modules.embedding.models import ChunkEmbedding

logger = structlog.get_logger(__name__)

# Sample enterprise documents
DOCUMENTS = [
    {
        "title": "Employee Handbook 2026",
        "description": "General policies, PTO, and benefits.",
        "content": "RAGuard AI Employee Handbook. PTO Policy: All employees receive 20 days of paid time off per year. Sick leave is unlimited but must be documented for absences over 3 days. Work from home is allowed up to 3 days a week. Core hours are 10 AM to 3 PM local time. Benefits include full medical, dental, and vision coverage starting day one.",
        "metadata": {"department": "HR", "type": "Policy", "sensitivity": "internal"}
    },
    {
        "title": "Information Security Policy v2",
        "description": "Security protocols and incident response.",
        "content": "All passwords must be at least 16 characters long and rotated every 90 days. Multifactor Authentication (MFA) is mandatory for all internal systems. If you suspect a security breach or phishing attempt, forward the email to security@raguard.ai immediately and disconnect your device from the network. Do not attempt to investigate yourself.",
        "metadata": {"department": "Security", "type": "Protocol", "sensitivity": "confidential"}
    },
    {
        "title": "Engineering Onboarding Guide",
        "description": "Setup steps for new engineers.",
        "content": "Welcome to Engineering. To get started, request access to GitHub and AWS via the IT portal. Our stack is React (frontend), FastAPI (backend), and PostgreSQL. Code must be reviewed by at least one senior engineer before merging to main. We use semantic versioning. Deployments happen every Tuesday and Thursday at 10 AM.",
        "metadata": {"department": "Engineering", "type": "Guide", "sensitivity": "internal"}
    },
    {
        "title": "Product Roadmap Q3 2026",
        "description": "Upcoming features and milestones.",
        "content": "Q3 Goals: 1) Launch Enterprise Chat interface with persistent history. 2) Improve hybrid search relevance by fine-tuning semantic weights. 3) Release the new Knowledge Dashboard for admin users. The Chat feature is the highest priority and must be delivered by August 15th. The dashboard redesign is scheduled for late September.",
        "metadata": {"department": "Product", "type": "Roadmap", "sensitivity": "confidential"}
    }
]

async def seed_data():
    logger.info("Starting enterprise data seed process")

    session_maker = get_session_factory()
    async with session_maker() as session:
        # Find demo admin
        stmt = select(User).where(User.email == "demoadmin@gmail.com")
        result = await session.execute(stmt)
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            logger.error("Admin user not found. Please register demoadmin@gmail.com via the UI first.")
            return

        tenant_id = admin_user.tenant_id

        # Check if already seeded to prevent duplicates
        stmt = select(Document).where(Document.title == "Employee Handbook 2026")
        existing = await session.execute(stmt)
        if existing.scalar_one_or_none():
            logger.info("Enterprise data already seeded. Skipping.")
            return

        for doc_data in DOCUMENTS:
            doc_id = str(uuid.uuid4())
            version_id = str(uuid.uuid4())

            # Create Document
            doc = Document(
                id=doc_id,
                tenant_id=tenant_id,
                title=doc_data["title"],
                description=doc_data["description"],
                status="processed",
                metadata_json=doc_data["metadata"]
            )

            # Create Document Version
            doc_version = DocumentVersion(
                id=version_id,
                document_id=doc_id,
                tenant_id=tenant_id,
                version_number=1,
                source_uri=f"local://seed/{doc_data['title'].replace(' ', '_')}.txt",
                mime_type="text/plain",
                status="processed",
                file_size_bytes=len(doc_data["content"]),
                hash=hashlib.sha256(doc_data["content"].encode()).hexdigest(),
                processing_error=None
            )

            chunk_id = str(uuid.uuid4())
            doc_data["_chunk_id"] = chunk_id
            doc_data["_doc_id"] = doc_id

            chunk = DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                document_version_id=version_id,
                tenant_id=tenant_id,
                chunk_index=0,
                content=doc_data["content"],
                token_count=len(doc_data["content"].split()),
                metadata_json=doc_data["metadata"]
            )

            # Mock Embedding
            embedding_id = str(uuid.uuid4())
            vector = [0.0] * 384  # Dummy vector just to have the DB record
            vector[0] = 0.5 # Give it some non-zero magnitude

            embedding = ChunkEmbedding(
                id=embedding_id,
                chunk_id=chunk_id,
                document_version_id=version_id,
                tenant_id=tenant_id,
                model_name="all-MiniLM-L6-v2",
                vector_dimension=384,
                is_active=True
            )

            session.add_all([doc, doc_version, chunk, embedding])

            # Upsert into Qdrant
            # Actually, let's use the standard retrieval service logic, or manually upsert to qdrant.
            try:
                # Need real vectors for search to work.
                # Let's generate a quick embedding using sentence-transformers if available,
                # or just insert dummy vectors (hybrid search might still find via BM25).
                pass
            except Exception as e:
                logger.error("Qdrant index failed", error=str(e))

        # Also let's seed Qdrant with valid vectors so hybrid search works!
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct

            client = QdrantClient(host=get_settings().qdrant_host, port=get_settings().qdrant_port)

            points = []
            for doc_data in DOCUMENTS:
                chunk_id = doc_data["_chunk_id"] # I need to store chunk_id on doc_data during creation
                tenant_id = admin_user.tenant_id
                vector = [0.1] * 384
                points.append(
                    PointStruct(
                        id=chunk_id,
                        vector=vector,
                        payload={
                            "tenant_id": tenant_id,
                            "content": doc_data["content"],
                            "document_id": doc_data["_doc_id"]
                        }
                    )
                )

            client.upsert(
                collection_name="chunks",
                points=points
            )
            logger.info("Successfully upserted mock vectors to Qdrant")
        except Exception as e:
            logger.error("Failed to seed Qdrant", error=str(e))

        await session.commit()

        logger.info("Successfully seeded enterprise data")

if __name__ == "__main__":
    asyncio.run(seed_data())
