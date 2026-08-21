# Security Response Headers Specification (F15.6)

**Program**: Veritas RAG — An Enterprise Knowledge Reliability Platform for Self-Correcting Retrieval-Augmented Generation
**Epic**: Epic 15 — Production Hardening & Enterprise Security
**Feature**: F15.6 — Security Headers Audit & Hardening
**Status**: ACTIVE / HARDENED

---

## 1. Overview

Veritas RAG enforces strict, defense-in-depth HTTP security response headers across both the ASGI application layer (`SecurityHeadersMiddleware`) and the edge proxy layer (Nginx `default.conf`).

All headers are designed to align with modern **OWASP Secure Headers Project** standards, eliminating legacy configurations and resolving prior proxy/application header conflicts.

---

## 2. Configured Headers & Policy Matrix

| Header Name | Value / Directive | Target Scope | Security Purpose |
|:---|:---|:---|:---|
| **`Content-Security-Policy`** | `default-src 'none'; frame-ancestors 'none'` | `/api/*` Routes | Prevents API context script execution, MIME confusion, and UI framing |
| **`Content-Security-Policy`** | `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' ws: wss: http: https:; frame-ancestors 'none';` | Frontend / Root | Blocks cross-origin injection and unauthorized frame embedding |
| **`Strict-Transport-Security`** | `max-age=31536000; includeSubDomains; preload` | Production HTTPS | Enforces mandatory HTTPS encryption for 1 year, including subdomains |
| **`X-Frame-Options`** | `DENY` | Universal | Completely prevents clickjacking attacks |
| **`X-Content-Type-Options`** | `nosniff` | Universal | Disables browser MIME-type sniffing |
| **`X-XSS-Protection`** | `0` | Universal | Disables obsolete/buggy browser XSS filters (modern CSP takes precedence) |
| **`Referrer-Policy`** | `strict-origin-when-cross-origin` | Universal | Restricts referrer leakages across third-party domains |
| **`Permissions-Policy`** | `accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()` | Universal | Disables hardware API access from client context |
| **`Cross-Origin-Opener-Policy`** | `same-origin` | Universal | Isolates browsing context against Spectre-style attacks |
| **`Cross-Origin-Resource-Policy`**| `same-origin` | Universal | Prevents foreign origin resource embedding |
| **`Cache-Control`** | `no-store, no-cache, must-revalidate, max-age=0` | `/api/*` Routes | Prevents client and intermediate proxy caching of sensitive API data |
| **`Pragma`** / **`Expires`** | `Pragma: no-cache`, `Expires: 0` | `/api/*` Routes | HTTP/1.0 legacy cache prevention |

---

## 3. Proxy vs Application Alignment

Prior to F15.6, Nginx `default.conf` specified `X-Frame-Options: SAMEORIGIN` and `X-XSS-Protection: 1; mode=block`, which contradicted ASGI middleware settings (`DENY` and `0`).

In F15.6:
- Nginx `default.conf` and `SecurityHeadersMiddleware` are **100% aligned**.
- `DENY` is enforced at both layers.
- `0` is enforced at both layers.
- Permissions-Policy and Cross-Origin policies are declared at both layers.

---

## 4. Automated Testing & Verification

Automated test suite: [`backend/tests/unit/middleware/test_security_headers.py`](file:///d:/Veritas RAG/backend/tests/unit/middleware/test_security_headers.py)
- `test_security_headers_api_route_dev_mode`: Verifies all baseline headers, strict API CSP, and absence of HSTS in dev mode.
- `test_security_headers_production_mode_hsts`: Verifies HSTS injection with `max-age=31536000`, `includeSubDomains`, and `preload`.
- `test_security_headers_non_api_route_csp`: Verifies frontend CSP rules on non-API routes.
