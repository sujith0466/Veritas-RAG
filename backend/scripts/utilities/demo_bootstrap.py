"""Demo Bootstrap Script.

Single command to prepare the certification environment.
Handles idempotent Supabase registration, local DB synchronization,
and enterprise data ingestion via the real REST API.
"""

import argparse
import asyncio
import os
import sys

import httpx

from backend.core.config import get_settings

# The Enterprise Data to ingest
DOCUMENTS = {
    "hr_policy.txt": (
        "RAGuard Employee PTO Policy\n\n"
        "Full-time employees accrue 15 days of PTO per year. PTO requests "
        "must be submitted 2 weeks in advance for vacations longer than 3 days. "
        "Unused PTO (up to 5 days) rolls over to the next calendar year."
    ),
    "security_guidelines.txt": (
        "Information Security Standards\n\n"
        "All production access requires MFA. Database credentials must be rotated "
        "every 90 days. Commits to the main branch require at least one approving "
        "code review. Customer PII must be encrypted at rest using AES-256."
    ),
    "product_roadmap.txt": (
        "Q3 Product Roadmap\n\n"
        "1. Launch Document Intelligence V2 (July)\n"
        "2. SOC2 Type II Certification (August)\n"
        "3. Hybrid Search Integration with Qdrant (September)\n"
        "Priorities are subject to change based on enterprise customer feedback."
    ),
    "engineering_handbook.txt": (
        "Engineering Best Practices\n\n"
        "We use Python 3.13 and FastAPI for all backend services. Code is formatted "
        "with black and linted with ruff. Our primary database is PostgreSQL 15, "
        "accessed via SQLAlchemy 2.0 async sessions."
    ),
}

async def bootstrap(force: bool, seed_only: bool, verify: bool):
    print("🚀 Starting RAGuard AI Demo Bootstrap...")

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")
    api_url = "http://127.0.0.1:8000"

    if not supabase_url or not supabase_service_key or not supabase_anon_key:
        print("❌ Error: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_ANON_KEY must be set.")
        sys.exit(1)

    admin_headers = {
        "apikey": supabase_service_key,
        "Authorization": f"Bearer {supabase_service_key}",
        "Content-Type": "application/json",
    }

    anon_headers = {
        "apikey": supabase_anon_key,
        "Authorization": f"Bearer {supabase_anon_key}",
        "Content-Type": "application/json",
    }

    # 1. Accounts Setup
    accounts = [
        {"email": "demoadmin@gmail.com", "password": "ChangeMe123!", "role": "admin", "tenant": "demo-tenant-1"},
        {"email": "demo@gmail.com", "password": "ChangeMe123!", "role": "viewer", "tenant": "demo-tenant-1"}
    ]

    jwts = {}

    if not seed_only:
        print("\n=== Provisioning Identity (Supabase) ===")
        async with httpx.AsyncClient() as client:
            for acc in accounts:
                email = acc["email"]
                print(f"Checking {email}...")

                # Check if exists
                exists = False
                resp = await client.get(f"{supabase_url}/auth/v1/admin/users", headers=admin_headers)
                if resp.status_code == 200:
                    users = resp.json().get("users", [])
                    if any(u.get("email") == email for u in users):
                        exists = True

                if exists:
                    print(f"ℹ️ {email} already exists in Supabase, reusing.")
                else:
                    # Create user
                    create_payload = {
                        "email": email,
                        "password": acc["password"],
                        "email_confirm": True,
                        "user_metadata": {
                            "role": acc["role"],
                            "tenant_id": acc["tenant"]
                        }
                    }
                    create_resp = await client.post(
                        f"{supabase_url}/auth/v1/admin/users",
                        headers=admin_headers,
                        json=create_payload
                    )
                    if create_resp.status_code in (200, 201):
                        print(f"✅ Created {email}")
                    elif create_resp.status_code == 422:
                        print(f"ℹ️ {email} already exists (422).")
                    else:
                        print(f"❌ Failed to create {email}: {create_resp.text}")
                        sys.exit(1)

                # Sign in to get JWT
                auth_resp = await client.post(
                    f"{supabase_url}/auth/v1/token?grant_type=password",
                    headers=anon_headers,
                    json={"email": email, "password": acc["password"]}
                )
                if auth_resp.status_code == 200:
                    token = auth_resp.json()["access_token"]
                    jwts[email] = token
                    print(f"✅ Authenticated as {email}")
                else:
                    print(f"❌ Failed to login as {email}: {auth_resp.text}")
                    sys.exit(1)

        print("\n=== Synchronizing Local Database ===")
        async with httpx.AsyncClient(base_url=api_url, timeout=30.0) as client:
            for email, token in jwts.items():
                resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 200:
                    print(f"✅ Synced local record for {email}")
                else:
                    print(f"❌ Failed to sync local record for {email}: {resp.text}")
                    sys.exit(1)

    # 2. Seeding Enterprise Data via Real API
    print("\n=== Seeding Enterprise Data ===")
    if not jwts:
        # If seed_only, we need to login as demoadmin to upload.
        async with httpx.AsyncClient() as client:
            auth_resp = await client.post(
                f"{supabase_url}/auth/v1/token?grant_type=password",
                headers=anon_headers,
                json={"email": "demoadmin@gmail.com", "password": "ChangeMe123!"}
            )
            if auth_resp.status_code == 200:
                jwts["demoadmin@gmail.com"] = auth_resp.json()["access_token"]
            else:
                print(f"❌ Failed to login to seed data: {auth_resp.text}")
                sys.exit(1)

    admin_token = jwts["demoadmin@gmail.com"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    async with httpx.AsyncClient(base_url=api_url, timeout=30.0) as client:
        # Check existing documents to avoid duplicates unless --force
        existing_docs = []
        if not force:
            resp = await client.get("/api/v1/documents", headers=headers)
            if resp.status_code == 200:
                existing_docs = [d["filename"] for d in resp.json()["data"]["items"]]

        uploaded_ids = []
        for filename, content in DOCUMENTS.items():
            if filename in existing_docs and not force:
                print(f"ℹ️ Skipping {filename} (already exists). Use --force to upload anyway.")
                continue

            print(f"Uploading {filename}...")
            files = {'file': (filename, content.encode('utf-8'), 'text/plain')}
            resp = await client.post("/api/v1/documents/upload", headers=headers, files=files)
            if resp.status_code == 202:
                doc_id = resp.json()["data"]["document_id"]
                uploaded_ids.append(doc_id)
                print(f"✅ Uploaded {filename} -> {doc_id}")
            else:
                print(f"❌ Failed to upload {filename}: {resp.text}")

        # Wait for processing
        if uploaded_ids:
            print("\nWaiting for ingestion pipeline to complete...")
            for doc_id in uploaded_ids:
                status = "PENDING"
                attempts = 0
                while status not in ("PROCESSED", "FAILED") and attempts < 30:
                    resp = await client.get(f"/api/v1/documents/{doc_id}/status", headers=headers)
                    if resp.status_code == 200:
                        status = resp.json()["data"]["status"]
                    await asyncio.sleep(2)
                    attempts += 1

                if status == "PROCESSED":
                    print(f"✅ Document {doc_id} processed successfully.")

                    # 1. Chunking
                    print(f"Triggering chunking for {doc_id}...")
                    resp = await client.post(f"/api/v1/chunks/process/{doc_id}?async_mode=false", headers=headers)
                    if resp.status_code in (200, 202):
                        print(f"✅ Chunked {doc_id}")
                    else:
                        print(f"❌ Failed to chunk {doc_id}: {resp.text}")
                        continue

                    # 2. Embedding
                    print(f"Triggering embedding for {doc_id}...")
                    doc_resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
                    version_id = doc_resp.json()["data"]["latest_version_id"]

                    embed_payload = {
                        "document_id": doc_id,
                        "document_version_id": version_id,
                        "provider": "local",
                        "model_name": "BAAI/bge-large-en-v1.5",
                        "batch_size": 100,
                        "force_reembed": True
                    }
                    resp = await client.post("/api/v1/embeddings/jobs", headers=headers, json=embed_payload)
                    if resp.status_code == 202:
                        job_id = resp.json()["data"]["job_id"]
                        emb_status = "PENDING"
                        emb_attempts = 0
                        while emb_status not in ("COMPLETED", "FAILED") and emb_attempts < 30:
                            e_resp = await client.get(f"/api/v1/embeddings/jobs/{job_id}", headers=headers, timeout=120.0)
                            if e_resp.status_code == 200:
                                emb_status = e_resp.json()["data"]["status"]
                            await asyncio.sleep(2)
                            emb_attempts += 1
                        if emb_status == "COMPLETED":
                            print(f"✅ Embedded {doc_id}")
                        else:
                            print(f"❌ Failed to embed {doc_id}: {emb_status}")
                            continue
                    else:
                        print(f"❌ Failed to start embedding for {doc_id}: {resp.text}")
                        continue

                    # 3. Vector Sync
                    print(f"Triggering vector sync for {doc_id}...")
                    sync_payload = {
                        "document_id": doc_id,
                        "collection_name": get_settings().qdrant.collection_name(tenant_id)
                    }
                    resp = await client.post(f"/api/v1/vectors/sync/{version_id}", headers=headers, json=sync_payload)
                    if resp.status_code == 202:
                        print(f"✅ Triggered vector sync for {doc_id}")
                        # Wait for sync
                        sync_status = "PENDING"
                        sync_attempts = 0
                        while sync_status not in ("COMPLETED", "FAILED") and sync_attempts < 30:
                            s_resp = await client.get(f"/api/v1/vectors/document/{doc_id}", headers=headers)
                            if s_resp.status_code == 200:
                                records = s_resp.json()["data"]
                                if records:
                                    sync_status = records[0]["status"]
                            await asyncio.sleep(2)
                            sync_attempts += 1
                        if sync_status == "COMPLETED":
                            print(f"✅ Synced vectors for {doc_id} to Qdrant")
                        else:
                            print(f"❌ Failed to sync vectors for {doc_id}: {sync_status}")
                    else:
                        print(f"❌ Failed to trigger vector sync for {doc_id}: {resp.text}")

                else:
                    print(f"❌ Document {doc_id} processing failed or timed out. Status: {status}")
        else:
            print("No new documents to process.")

    # 3. Validation / Metrics
    if verify or force:
        print("\n=== Validation & Metrics ===")
        print("Note: Run `test_certification.py` for comprehensive tests. Bootstrap complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAGuard Demo Bootstrap")
    parser.add_argument("--force", action="store_true", help="Force recreate documents even if they exist")
    parser.add_argument("--seed-only", action="store_true", help="Skip user creation, only seed documents")
    parser.add_argument("--verify", action="store_true", help="Run extra verification queries")
    args = parser.parse_args()

    asyncio.run(bootstrap(args.force, args.seed_only, args.verify))
