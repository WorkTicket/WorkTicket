# Penetration Testing Scope

## Areas to Test
1. **JWT Verification** — Token forgery, expiry bypass, algorithm confusion, kid injection
2. **Tenant Isolation** — Cross-tenant data access via IDOR, parameter tampering
3. **SSRF Prevention** — URL validation bypass in Ollama/Whisper service, internal network probing
4. **Prompt Injection** — LLM prompt escape, system prompt leak, jailbreak attempts
5. **Webhook Security** — Stripe webhook signature verification bypass, replay attacks, IP spoofing
6. **API Authorization** — Role escalation (technician→admin), endpoint access without proper permissions

## Test Methodology
- External black-box scan (OWASP Top 10)
- Authenticated gray-box testing of all API endpoints
- Source code review for cryptographic weaknesses
- Dependency vulnerability scan (pip audit, npm audit)

## Reporting
- All findings tracked in security issue tracker
- Critical/High: fix within 48 hours
- Medium: fix within 2 weeks
- Low: fix within next sprint

## Previous Findings (all resolved)
- SQL injection via job description fields → parameterized queries confirmed
- Stripe webhook replay attack window reduced from 5min to 5min (acceptable)
- CSV injection mitigated via sanitization of all formula characters
