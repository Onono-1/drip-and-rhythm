# SECURITY.md — Security, Privacy & Operational Controls

## 1. Authentication & Authorization
- **Django Session Authentication Only**: Administrator sessions use `drip_admin_session` (`HttpOnly`, `SameSite=Lax`, `Secure` in production, 12-hour lifetime). No JWTs or `localStorage` tokens are used.
- **CSRF Protection**: Enforced across all state-changing endpoints (`POST`, `PATCH`, `PUT`, `DELETE`), including anonymous login (`POST /api/auth/login/`), password reset, guest invitation claiming (`POST /api/invite/{token}/claim/`), and sharing preference updates. Only `POST /api/webhooks/resend/` is CSRF-exempt, protected instead by cryptographic Svix HMAC-SHA256 verification over the raw request body bytes.
- **Server-Side RBAC & Ownership**: Every role (`SUPER_ADMIN` vs `ADMIN`) and invitation-ownership check is enforced in Django. Deactivated administrators lose access immediately on existing sessions via both session table purge and `ActiveAdminAndCacheControlMiddleware`. Deactivating or demoting the final active `SUPER_ADMIN` is blocked under `SELECT ... FOR UPDATE`.

## 2. Four Isolated Cryptographic Credentials
All tokens are generated with 256-bit `secrets.token_urlsafe(32)` and stored as SHA-256 digests (`hashlib.sha256`):
1. **Claim Token** (`/invite/[token]`): Recoverable Fernet-encrypted copy (`TOKEN_ENCRYPTION_KEY`) kept only while `UNUSED` and wiped immediately upon claim, expiry transition, or revocation.
2. **Admission Token** (`DRIP1:<token>` in PDF QR): Created only upon claim, versioned (`admission_credential_version`), and rotated immediately if a super administrator corrects the guest's email address (permanently invalidating previous QR codes).
3. **Public Sharing Token** (`/share/[token]`): Read-only promotional token; never authorizes mutations or reveals guest email, invitation reference, QR code, or private venue.
4. **Claim Receipt Token** (`drip_claim_receipt` HTTP-only cookie): Limited-purpose guest confirmation credential with configurable lifetime (`CLAIM_RECEIPT_TTL_DAYS`, defaulting to `max(event_date + 7 days, claimed_at + 7 days)`), immediately invalidated on revocation or guest email correction.

## 3. Database Constraints, Concurrency & Rate Limiting
- **Canonical Lock Ordering**: `Event` → `User` → `Invitation` → `EmailDelivery` prevents deadlocks across concurrent claims, bulk generation, revocations, guest corrections, and check-ins.
- **Database Integrity**: Partial PostgreSQL `UniqueConstraint` on `(event, guest_email_normalized)` prevents duplicate emails (preserving Gmail dots/`+aliases` and keeping unused links `UNUSED` on duplicate attempts). `CheckIn.invitation` uses a PostgreSQL `OneToOneField` unique constraint + row lock so simultaneous check-ins can never admit a guest twice.
- **Rate Limiting**: `RateLimitBucket` enforces cross-process limits directly in PostgreSQL (`INSERT ... ON CONFLICT DO UPDATE`).

## 4. Privacy, Sanitization & Known Limitations
- **Minimal Guest Data**: Only `nickname` (1–50 chars, control/HTML brackets rejected) and `email` are collected. Public sharing defaults to anonymous (`show_nickname_publicly = False`).
- **Cache & Log Hygiene**: Sensitive API and Next.js routes emit `Cache-Control: no-store`. `SensitiveDataRedactionFilter` and `sanitize_metadata` redact tokens, cookies, secrets, and QR payloads from logs and append-only `AuditLog` entries. CSV exports prefix formula-triggering cells (`=`, `+`, `-`, `@`, `\t`, `\r`) with `'`.
- **Documented Operational Limitations**:
  1. *Identity Scope*: Email uniqueness prevents repeated claims per email address, not guests using multiple email addresses or forwarding an unused link/PDF pass.
  2. *In-Flight Email Race*: The email worker re-verifies invitation status and `admission_credential_version` immediately before calling Resend and uses stable `Idempotency-Key` headers, but if revocation/correction happens while an external HTTP request is already in flight at Resend, an obsolete email could still arrive; its old QR code is nevertheless rejected at entrance verification.
  3. *External Caches*: Disabling or revoking public sharing immediately blocks application endpoints, but previously downloaded PNGs or third-party social preview caches (WhatsApp, X, etc.) cannot be remotely deleted.

## 5. Credential Rotation & Post-Event Data Retention
- **Rotating Secrets**: Rotating `DJANGO_SECRET_KEY` invalidates active admin sessions. Rotating `TOKEN_ENCRYPTION_KEY` requires re-encrypting recoverable `claim_token_encrypted` / `admission_token_encrypted` / `share_token_encrypted` values in an authorized maintenance window while keeping both API and worker synchronized.
- **Post-Event Cleanup**: Production data is never auto-deleted. After post-event reconciliation, an authorized super administrator should export final audit/attendance archives if needed, back up or drop the managed database under explicit organizer authorization, and revoke live Resend API keys.
