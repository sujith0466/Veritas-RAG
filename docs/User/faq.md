# Frequently Asked Questions

**Q: What LLM providers does Veritas RAG support?**
A: Veritas RAG ships with OpenAI and Anthropic Claude provider adapters. The `BaseLLMProvider`
interface makes adding new providers straightforward.

**Q: Does Veritas RAG replace my existing RAG pipeline?**
A: No. Veritas RAG wraps around your existing retrieval and LLM infrastructure, adding
reliability, validation, and observability layers without replacing your core logic.

**Q: How does DLP affect latency?**
A: The DLP regex engine adds sub-millisecond overhead per request. It is highly optimized
using compiled Python regex patterns.

**Q: Can I disable the retry controller?**
A: Yes. Set `RETRY_ENABLED=false` in your `.env`. Queries will go directly to generation
without the reliability loop.

**Q: How is tenant data isolated?**
A: Qdrant collections are namespaced per tenant. All database queries include mandatory
`tenant_id` filter predicates enforced at the ORM level.

**Q: Is Veritas RAG production-safe out of the box?**
A: Yes. HSTS headers, DLP, audit logging, RBAC, and circuit breakers are all enabled
by default in the `production` environment.

**Q: What happens when an LLM provider fails?**
A: The Phase 18 Self-Healing Governor rotates to the next provider in `LLM_PRIORITY_LIST`
and fires an alert via the configured channels.
