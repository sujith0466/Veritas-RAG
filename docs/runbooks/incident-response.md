# Incident Response Runbook

## Scope
Security incidents, PII leakage, DDOS, or LLM provider compromise.

## Procedure: Compromised LLM Key
1. Go to Admin Dashboard / Secret Manager.
2. Rotate key for the compromised provider (e.g., OpenAI).
3. Update `.env.prod` / Secret injection.
4. Restart API instances (Rolling Deployment).
5. OpenTelemetry will log the new `auth_rotation` event for auditing.

## Procedure: DLP Failure (PII Leak)
1. Determine the regex pattern that failed in the DLP engine.
2. Update the `DLP_CUSTOM_PATTERNS` environment variable.
3. Restart API instances.
4. Check `audit_logs` table for any queries executed during the window of vulnerability.
