import asyncio
import asyncpg
import os

async def fix():
    url = os.environ['ALEMBIC_DATABASE_URL']
    conn = await asyncpg.connect(url)
    tables = [
        'query_analytics_records',
        'document_chunks',
        'chunk_embeddings',
        'health_scan_jobs',
        'retrieval_query_logs',
        'audit_logs',
        'documents',
    ]
    for t in tables:
        try:
            await conn.execute(
                f'ALTER TABLE {t} ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE'
            )
            print(f'Fixed: {t}')
        except Exception as e:
            print(f'Skip {t}: {e}')
    await conn.close()
    print("Done.")

asyncio.run(fix())
