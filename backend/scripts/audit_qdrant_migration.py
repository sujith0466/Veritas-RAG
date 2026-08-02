import asyncio
from collections import defaultdict

import structlog

from backend.core.config import get_settings
from backend.vector_db.client import get_qdrant_client

logger = structlog.get_logger(__name__)

class Severity:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class CollectionClass:
    PROD = "Production Tenant Collection"
    DEFAULT = "Default Tenant Collection"
    LEGACY = "Legacy Collection"
    TEST = "Test Collection"
    UNKNOWN = "Unknown"

def classify_collection(coll_name: str) -> str:
    name_lower = coll_name.lower()
    if "test" in name_lower:
        return CollectionClass.TEST
    if "knowledge_" in name_lower or coll_name == "default_tenant_chunks":
        return CollectionClass.LEGACY
    if "default_tenant" in name_lower:
        return CollectionClass.DEFAULT
    if coll_name.startswith("raguard_tenant_") or coll_name.startswith("raguard_"):
        return CollectionClass.PROD
    return CollectionClass.UNKNOWN

async def run_audit():
    """Run a read-only migration audit on all Qdrant collections."""
    print("==========================================================")
    print("          PHASE 2.5 — QDRANT MIGRATION AUDIT              ")
    print("==========================================================")
    print("[INFO] Operating in strict READ-ONLY diagnostic mode.")

    settings = get_settings()
    client = get_qdrant_client()

    try:
        collections_response = await client.get_collections()
        collections = [c.name for c in collections_response.collections]
    except Exception as e:
        print(f"[ERROR] Failed to connect to Qdrant: {e}")
        print("\nProduction Migration Ready: NO")
        print("Full Server Migration Ready: NO")
        return

    print(f"\n1. Existing Collections: {len(collections)}")

    classifications = defaultdict(list)
    for c in collections:
        cls = classify_collection(c)
        classifications[cls].append(c)

    print("\nCollection Classification:")
    for cls_name, colls in classifications.items():
        print(f"\n   [{cls_name}] ({len(colls)} collections):")
        for c in colls:
            print(f"      - {c}")

    all_tenant_ids = set()

    # Store issues as tuples (collection_name, message)
    issues_by_severity = {
        Severity.CRITICAL: [],
        Severity.HIGH: [],
        Severity.MEDIUM: [],
        Severity.LOW: [],
        Severity.INFO: []
    }

    for coll_name in collections:
        try:
            coll_info = await client.get_collection(coll_name)
            vector_count = coll_info.vectors_count
        except Exception as e:
            issues_by_severity[Severity.CRITICAL].append((coll_name, f"Could not read collection {coll_name}: {e}"))
            continue

        print(f"\nAnalyzing Collection: {coll_name} ({vector_count} vectors)")

        if vector_count == 0:
            issues_by_severity[Severity.LOW].append((coll_name, f"Collection '{coll_name}' is empty."))
            continue

        offset = None

        vectors_missing_tenant = 0
        tenant_ids_in_coll = set()
        duplicate_vectors = 0
        invalid_payloads = 0
        dimension_set = set()

        seen_ids = set()

        while True:
            records, next_page_offset = await client.scroll(
                collection_name=coll_name,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=True
            )

            for record in records:
                tenant_id = record.payload.get("tenant_id") if record.payload else None
                if not tenant_id:
                    vectors_missing_tenant += 1
                else:
                    tenant_ids_in_coll.add(str(tenant_id))
                    all_tenant_ids.add(str(tenant_id))

                if record.id in seen_ids:
                    duplicate_vectors += 1
                seen_ids.add(record.id)

                if not isinstance(record.payload, dict) or ("document_id" not in record.payload and "chunk_index" not in record.payload):
                    invalid_payloads += 1

                if record.vector:
                    if isinstance(record.vector, dict):
                        for vec_name, vec_val in record.vector.items():
                            dimension_set.add(len(vec_val))
                    else:
                        dimension_set.add(len(record.vector))

            if next_page_offset is None:
                break
            offset = next_page_offset

        print(f"   - Vector count: {vector_count}")
        print(f"   - Tenant IDs discovered: {len(tenant_ids_in_coll)} {list(tenant_ids_in_coll)[:5]}")
        print(f"   - Vectors missing tenant_id: {vectors_missing_tenant}")
        print(f"   - Duplicate vector entries: {duplicate_vectors}")
        print(f"   - Invalid payloads: {invalid_payloads}")
        print(f"   - Embedding dimensions: {list(dimension_set)}")

        if vectors_missing_tenant > 0:
            issues_by_severity[Severity.CRITICAL].append((coll_name, f"Collection '{coll_name}' has {vectors_missing_tenant} vectors missing 'tenant_id'"))

        if invalid_payloads > 0:
            issues_by_severity[Severity.CRITICAL].append((coll_name, f"Collection '{coll_name}' has {invalid_payloads} corrupted or invalid payloads"))

        if len(dimension_set) > 1:
            issues_by_severity[Severity.HIGH].append((coll_name, f"Collection '{coll_name}' has mixed embedding dimensions: {list(dimension_set)}"))

        if len(tenant_ids_in_coll) == 0 and vectors_missing_tenant > 0:
            issues_by_severity[Severity.HIGH].append((coll_name, f"Collection '{coll_name}' has unknown ownership (no tenant IDs found)"))

        if classify_collection(coll_name) == CollectionClass.LEGACY:
            issues_by_severity[Severity.MEDIUM].append((coll_name, f"Collection '{coll_name}' uses legacy naming conventions"))

        if duplicate_vectors > 0:
            issues_by_severity[Severity.LOW].append((coll_name, f"Collection '{coll_name}' has {duplicate_vectors} duplicate vectors"))

    estimated_destinations = [settings.qdrant.collection_name(t) for t in all_tenant_ids]
    issues_by_severity[Severity.INFO].append((None, f"Estimated Destination Collections needed: {len(estimated_destinations)}"))
    issues_by_severity[Severity.INFO].append((None, f"Total Unique Tenants Discovered: {len(all_tenant_ids)}"))

    print("\n==========================================================")
    print("                 MIGRATION AUDIT ISSUES                   ")
    print("==========================================================")

    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        issues = issues_by_severity[severity]
        print(f"\n[{severity}] ({len(issues)} findings)")
        for _, msg in issues:
            print(f"   - {msg}")

    print("\n==========================================================")
    print("                 EXCLUDED COLLECTIONS                     ")
    print("==========================================================")

    excluded_classes = [CollectionClass.LEGACY, CollectionClass.TEST, CollectionClass.UNKNOWN]
    has_excluded = False

    for cls in excluded_classes:
        for c in classifications[cls]:
            has_excluded = True
            print(f"\nCollection:\n{c}")
            print(f"\nClassification:\n{cls}")
            if cls == CollectionClass.TEST:
                print("\nReason:\nLegacy QA / temporary testing")
                print("\nRecommended Action:\nManual review or delete before production migration")
            elif cls == CollectionClass.LEGACY:
                print("\nReason:\nDeprecated collection naming format")
                print("\nRecommended Action:\nManual review or delete before production migration")
            else:
                print("\nReason:\nDoes not match any known ownership patterns")
                print("\nRecommended Action:\nInvestigate ownership or delete before production migration")

    if not has_excluded:
        print("\nNo collections excluded from production scope.")

    print("\n==========================================================")
    print("                 MIGRATION SCOPE SUMMARY                  ")
    print("==========================================================")

    print(f"\nProduction Collections:\n{len(classifications.get(CollectionClass.PROD, []))}")
    print(f"\nDefault Collections:\n{len(classifications.get(CollectionClass.DEFAULT, []))}")
    print(f"\nLegacy Collections:\n{len(classifications.get(CollectionClass.LEGACY, []))}")
    print(f"\nTest Collections:\n{len(classifications.get(CollectionClass.TEST, []))}")
    print(f"\nUnknown Collections:\n{len(classifications.get(CollectionClass.UNKNOWN, []))}")

    print("\n==========================================================")

    production_scoped_classes = {CollectionClass.PROD, CollectionClass.DEFAULT}

    has_prod_critical = False
    has_any_critical = False

    for coll_name, msg in issues_by_severity[Severity.CRITICAL]:
        has_any_critical = True
        if coll_name and classify_collection(coll_name) in production_scoped_classes:
            has_prod_critical = True

    prod_ready = "YES" if not has_prod_critical else "NO"
    full_ready = "YES" if not has_any_critical else "NO"

    print(f"\nProduction Migration Ready:\n{prod_ready}")
    print(f"\nFull Server Migration Ready:\n{full_ready}")

    if has_any_critical:
        print("\nBlocking Issues:")
        for coll_name, msg in issues_by_severity[Severity.CRITICAL]:
            scope = "PRODUCTION" if coll_name and classify_collection(coll_name) in production_scoped_classes else "EXCLUDED"
            print(f"   - [BLOCKER - {scope}] {msg}")

    print("\n==========================================================")

if __name__ == "__main__":
    asyncio.run(run_audit())
