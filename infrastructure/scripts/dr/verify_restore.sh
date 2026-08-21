#!/usr/bin/env bash
# ==============================================================================
# Disaster Recovery — Post-Restore Health & Integrity Verification Script
#
# Usage:
#   ./verify_restore.sh [API_BASE_URL]
#
# Environment variables:
#   API_BASE_URL (default: http://localhost:8000)
#   MAX_RETRIES (default: 10)
#   RETRY_DELAY (default: 3)
# ==============================================================================

set -euo pipefail

API_BASE_URL="${1:-${API_BASE_URL:-http://localhost:8000}}"
MAX_RETRIES="${MAX_RETRIES:-10}"
RETRY_DELAY="${RETRY_DELAY:-3}"

echo "============================================================"
echo " Starting Post-Restore System Verification"
echo " Target API: $API_BASE_URL"
echo "============================================================"

# 1. Probe liveness endpoint
echo "[*] Step 1/3: Validating application liveness (/health/live)..."
LIVENESS_OK=false
for ((i=1; i<=MAX_RETRIES; i++)); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE_URL}/health/live" || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        echo "[+] Liveness check passed (HTTP 200)."
        LIVENESS_OK=true
        break
    fi
    echo "    Attempt $i/$MAX_RETRIES: Liveness probe returned HTTP $HTTP_CODE. Retrying in ${RETRY_DELAY}s..."
    sleep "$RETRY_DELAY"
done

if [[ "$LIVENESS_OK" != "true" ]]; then
    echo "[-] FATAL: Liveness probe failed after $MAX_RETRIES attempts." >&2
    exit 1
fi

# 2. Probe readiness endpoint (database, cache, vector store)
echo "[*] Step 2/3: Validating subsystem readiness (/health/ready)..."
READINESS_PAYLOAD=$(curl -s "${API_BASE_URL}/health/ready" || echo "{}")
READINESS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE_URL}/health/ready" || echo "000")

if [[ "$READINESS_CODE" != "200" ]]; then
    echo "[-] FATAL: Readiness probe failed with HTTP $READINESS_CODE: $READINESS_PAYLOAD" >&2
    exit 2
fi

echo "[+] Readiness check passed (HTTP 200). Subsystems are operational."

# 3. Summary
echo "============================================================"
echo "[+] POST-RESTORE VERIFICATION SUCCESSFUL"
echo "    All core dependencies are healthy and accepting traffic."
echo "============================================================"
