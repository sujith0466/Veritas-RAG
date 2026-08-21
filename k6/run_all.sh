#!/usr/bin/env bash
# ==============================================================================
# Veritas RAG V2 — k6 Load Testing Suite Execution Runner
#
# Usage:
#   ./run_all.sh [BASE_URL]
#
# Environment variables:
#   BASE_URL (default: http://localhost:8000)
#   TEST_USER_EMAIL (default: loadtest@example.com)
#   TEST_USER_PASSWORD (default: LoadTestPassword123!)
# ==============================================================================

set -euo pipefail

BASE_URL="${1:-${BASE_URL:-http://localhost:8000}}"
export BASE_URL

echo "============================================================"
echo " Starting Veritas RAG V2 k6 Performance Test Suite"
echo " Target Endpoint: $BASE_URL"
echo "============================================================"

# Verify k6 binary availability
if ! command -v k6 &> /dev/null; then
    echo "[-] ERROR: 'k6' binary not found in PATH." >&2
    echo "    Please install k6 (https://k6.io/docs/get-started/installation/)" >&2
    exit 1
fi

echo "[*] 1/5: Running Authentication & Session Workload..."
k6 run k6/scenarios/auth_workload.js

echo "[*] 2/5: Running Concurrent Workspace Users Workload..."
k6 run k6/scenarios/concurrent_users.js

echo "[*] 3/5: Running Mandatory Quota Increment Atomicity Test..."
k6 run k6/scenarios/quota_concurrent_increment.js

echo "[*] 4/5: Running Document Upload Throughput Workload..."
k6 run k6/scenarios/document_upload.js

echo "[*] 5/5: Running Mixed Enterprise Realistic Workload..."
k6 run k6/scenarios/mixed_enterprise_workload.js

echo "============================================================"
echo "[+] ALL k6 LOAD TEST SCENARIOS COMPLETED"
echo "============================================================"
