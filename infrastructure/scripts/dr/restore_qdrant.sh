#!/usr/bin/env bash
# ==============================================================================
# Disaster Recovery — Qdrant Vector Collection Restoration Script
#
# Usage:
#   ./restore_qdrant.sh <collection_name> <snapshot_name_or_url> [--confirm]
#
# Environment variables:
#   QDRANT_HOST (default: localhost)
#   QDRANT_PORT (default: 6333)
#   QDRANT_API_KEY (optional)
#   ENVIRONMENT (default: development)
# ==============================================================================

set -euo pipefail

COLLECTION_NAME="${1:-knowledge}"
SNAPSHOT_SOURCE="${2:-}"
CONFIRM_FLAG="${3:-}"

QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_API_KEY="${QDRANT_API_KEY:-}"
ENVIRONMENT="${ENVIRONMENT:-development}"

BASE_URL="http://${QDRANT_HOST}:${QDRANT_PORT}"

# 1. Argument validation
if [[ -z "$SNAPSHOT_SOURCE" ]]; then
    echo "[-] ERROR: Missing snapshot source argument." >&2
    echo "    Usage: $0 <collection_name> <snapshot_name_or_url> [--confirm]" >&2
    exit 1
fi

# 2. Production safety guard
if [[ "$ENVIRONMENT" == "production" ]] && [[ "$CONFIRM_FLAG" != "--confirm" ]]; then
    echo "[!] CAUTION: ENVIRONMENT is set to 'production'." >&2
    echo "    To execute snapshot restoration in production, pass '--confirm'." >&2
    exit 1
fi

echo "============================================================"
echo " Starting Qdrant Collection Restoration"
echo " Target Endpoint:   $BASE_URL"
echo " Collection:        $COLLECTION_NAME"
echo " Snapshot Source:   $SNAPSHOT_SOURCE"
echo " Env:               $ENVIRONMENT"
echo "============================================================"

AUTH_HEADER=()
if [[ -n "$QDRANT_API_KEY" ]]; then
    AUTH_HEADER=(-H "api-key: $QDRANT_API_KEY")
fi

# 3. Connectivity check
echo "[*] Checking Qdrant cluster health..."
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${AUTH_HEADER[@]}" "${BASE_URL}/healthz" || echo "000")
if [[ "$HEALTH_STATUS" != "200" ]]; then
    echo "[-] ERROR: Qdrant health check failed with HTTP code $HEALTH_STATUS at $BASE_URL" >&2
    exit 2
fi

# 4. Trigger recovery from snapshot
echo "[*] Restoring collection '$COLLECTION_NAME' from snapshot..."
RECOVER_PAYLOAD=$(cat <<EOF
{
    "location": "$SNAPSHOT_SOURCE"
}
EOF
)

RECOVER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    "${AUTH_HEADER[@]}" \
    -d "$RECOVER_PAYLOAD" \
    "${BASE_URL}/collections/${COLLECTION_NAME}/snapshots/recover")

if [[ "$RECOVER_STATUS" != "200" && "$RECOVER_STATUS" != "202" ]]; then
    echo "[-] ERROR: Snapshot recovery failed with HTTP code $RECOVER_STATUS" >&2
    exit 3
fi

# 5. Verify collection status
echo "[*] Verifying collection health after recovery..."
COLLECTION_INFO=$(curl -s -f "${AUTH_HEADER[@]}" "${BASE_URL}/collections/${COLLECTION_NAME}" || echo "{}")

if echo "$COLLECTION_INFO" | grep -q '"status":"green"'; then
    echo "[+] SUCCESS: Qdrant collection '$COLLECTION_NAME' restored and healthy (status: green)."
elif echo "$COLLECTION_INFO" | grep -q '"status":"ok"'; then
    echo "[+] SUCCESS: Qdrant collection '$COLLECTION_NAME' restored and healthy (status: ok)."
else
    echo "[!] WARNING: Collection restored but status is not optimal: $COLLECTION_INFO"
fi
