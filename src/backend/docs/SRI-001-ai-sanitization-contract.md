# SRI-001: AI Output Sanitization Architecture Contract

**Status:** Enforced  
**Owner:** Security / Platform Team  
**Last updated:** 2026-05-26

---

## Contract Statement

> **All AI-generated output MUST pass through `_sanitize_output_dict()` (from `app.ai.gateway`) before leaving the trust boundary.**

The trust boundary is defined as any point where AI output is:
- returned in an API response
- persisted to the database
- transmitted over WebSocket
- passed to an external system

---

## Architecture

```
User Input ──> _sanitize_input_text() ──> LLM/AI Service ──> Raw Output
                                                                │
                                                     _sanitize_output_dict()
                                                         (recursive)
                                                                │
                                              ┌──────────────────┼──────────────────┐
                                              ▼                  ▼                  ▼
                                         API Response      DB Persistence     WebSocket
                                    (middleware layer)   (Celery task)      (metadata only)
```

### Sanitization Layers (defense-in-depth)

| Layer | Mechanism | Location |
|-------|-----------|----------|
| 1. Output Sanitizer (canonical) | `_sanitize_output_dict()` — recursive dict/list/string traversal | `app/ai/gateway.py:405` |
| 2. Text Sanitizer | `_sanitize_output_text()` — unicode normalization, pattern blocking, semantic scoring, HTML escaping | `app/ai/gateway.py:384` |
| 3. Input Sanitizer | `_sanitize_input_text()` — strips LLM special tokens, redacts instruction-override patterns | `app/ai/gateway.py:441` |
| 4. Middleware (redundant) | `AIResponseSanitizationMiddleware` — path-based post-response sanitization | `app/middleware/sanitize.py:14` |
| 5. Pydantic Validation | `AIOutputSchema` — field-level type/range validation before DB insert | `app/ai/schemas.py` |

### Sanctioned Orchestrator Callers

Only these files may call `orchestrator.generate_chat_output()` directly:

| File | Rationale |
|------|-----------|
| `app/ai/gateway.py` | Owns the canonical sanitization pipeline; calls `_sanitize_output_text()` inline after generation |
| `app/estimates/engine.py` | Calls `orchestrator.generate_chat_output()` then immediately wraps result in `_sanitize_output_dict()` at line 111 |

All other files MUST NOT call `orchestrator.generate_chat_output()` directly.
New AI output paths MUST go through `gateway.process_job()` or explicitly call `_sanitize_output_dict()`.

---

## Enforcement

### CI Gates

| Check | Tool | Location | Trigger |
|-------|------|----------|---------|
| Lint: raw orchestrator calls | `scripts/audit_ai_sanitization.py` | AST scanner | Every PR to `src/backend/` |
| Audit: unsanitized return paths | `tests/security/test_ai_path_audit.py` | Pytest + AST scanner | Every PR to `src/backend/` |
| Middleware coverage | `test_middleware_covers_all_ai_routes` | Route prefix scan vs middleware path list | Every PR to `src/backend/` |

### What triggers a build failure

1. A `.py` file outside `app/ai/gateway.py` or `app/estimates/engine.py` calls `orchestrator.generate_chat_output()`.
2. A function that calls any orchestrator AI method does not also call `_sanitize_output_dict()` in the same scope.
3. A new route with `/ai/`, `/estimates/`, or `/quotes/` prefix is added but not listed in `AIResponseSanitizationMiddleware._should_sanitize()`.

---

## Schema Evolution

The recursive design of `_sanitize_output_dict()` automatically covers new fields:

```python
def _sanitize_output_dict(data, path=""):
    if isinstance(data, dict):
        return {k: _sanitize_output_dict(v, f"{path}.{k}") for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_output_dict(item, f"{path}[{i}]") for i, item in enumerate(data)]
    if isinstance(data, str):
        return _sanitize_output_text(data)
    return data
```

Adding a new key to the AI output JSON automatically traverses into the sanitizer.
**No manual field registration is required.**

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Developer calls `orchestrator.generate_chat_output()` directly | High | Lint rule + CI audit prevents PR merge |
| New AI pipeline bypasses sanitizer | High | CI audit scans for unsanitized return paths |
| Schema field accidentally excluded from sanitizer | Low | Recursive design auto-covers all fields |
| Sanitizer logic weakened by regression | Medium | Unit tests in `test_sanitization.py` cover known bypass techniques |

---

## History

| Date | Change | Author |
|------|--------|--------|
| 2026-05-26 | Initial contract — post-hardening audit | Security team |
