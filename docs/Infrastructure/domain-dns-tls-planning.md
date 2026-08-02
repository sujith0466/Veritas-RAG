# Domain, DNS, and TLS Planning

## DNS Strategy
RAGuard AI services should be deployed on a dedicated sub-domain to isolate
cookie and CORS policies from the main application.
- API Endpoint: `api.raguard.yourdomain.com`

## TLS / HTTPS
- **Edge Termination**: TLS must be terminated at the edge (Load Balancer or Nginx Reverse Proxy).
- **Certificates**:
  - Use Let's Encrypt (Certbot) for automated certificate rotation.
  - Or, supply Enterprise Wildcard certificates via the secrets volume mount.
- **HSTS**: Strict-Transport-Security headers are automatically enforced by RAGuard
  when `ENVIRONMENT=production`.
