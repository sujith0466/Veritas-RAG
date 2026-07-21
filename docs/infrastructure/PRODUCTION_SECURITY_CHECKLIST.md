# Production Security Checklist

- [ ] **HTTPS Enforced**: Nginx configured with `return 301 https://$host$request_uri`.
- [ ] **HSTS Headers**: Nginx `Strict-Transport-Security` header is present.
- [ ] **Secrets Manager**: `.env.prod` is populated exclusively by a CI/CD secrets manager.
- [ ] **Dependency Scan**: `pip-audit` or `safety` ran against `requirements-lock.txt` with zero critical findings.
- [ ] **Container Security**: `raguard` user created in Dockerfile; container runs non-root.
- [ ] **RBAC**: Multi-tenant isolation verified by `SecurityInterceptor` middleware.
- [ ] **DLP Active**: `DLP_ENABLED=true` is set.
- [ ] **Audit Trail Active**: `AUDIT_LOG_ENABLED=true` is set.
