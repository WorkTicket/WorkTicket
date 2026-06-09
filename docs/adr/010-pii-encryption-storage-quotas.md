# ADR 010: Column-Level PII Encryption and Per-Tenant Storage Quotas

**Status:** Accepted
**Date:** 2026-06-05

## Context

The security audit identified two gaps:
1. PII fields (email, name, phone) stored in plaintext in the database
2. No per-tenant storage quotas for uploaded media

## Decision

### PII Encryption (AES-256-GCM)

We implement **application-layer column-level encryption** using AES-256-GCM:

- **Algorithm:** AES-256-GCM (authenticated encryption with integrity verification)
- **Key management:** Single encryption key from `PII_ENCRYPTION_KEY` env var
- **Versioning:** Key version tracked per encrypted value for rotation support
- **Storage:** Encrypted data stored as JSON blobs in `encrypted_*` columns alongside plaintext columns
- **Access pattern:** Property getters/setters transparently encrypt/decrypt
- **Fields encrypted:** User email, User name, Customer email, Customer phone, Customer name

### Per-Tenant Storage Quotas

We add storage quota tracking to `BillingAccount`:

- **Default quota:** 5GB per tenant
- **Tracking:** Atomic increment on upload, decrement on delete
- **Enforcement:** Uploads rejected at `confirm-upload` if quota exceeded
- **Migration:** New columns `storage_quota_bytes` and `used_storage_bytes` on `billing_accounts`

## Consequences

### Positive
- PII data encrypted-at-rest beyond DB-level encryption
- Storage costs bounded per tenant
- Gradual migration: encrypted columns alongside existing columns

### Negative
- Encryption adds ~1ms per encrypt/decrypt operation
- Key rotation process must be documented
- Storage quota adds DB write on every upload
