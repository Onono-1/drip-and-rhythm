# AGENTS.md — Persistent Project Rules for DRIP & RHYTHM

This file defines mandatory, persistent engineering, architectural, security, design, and operational rules for the **DRIP & RHYTHM** Private Party Invitation Management System. Every contributor and agent working in this repository must follow these rules strictly.

---

## 1. Instruction Priority & Scope

When guidance conflicts, resolve using this strict precedence order:
1. Approved consolidated project decisions and `implementation_plan.md`.
2. `MASTER_PROMPT.md`.
3. Approved architecture and security requirements.
4. `AGENTS.md` and `.agents/rules/drip-and-rhythm.md`.
5. Approved DRIP & RHYTHM design system.
6. Relevant installed design skill guidance.

**Core Invariant**: **One link. One email. One invitation. One admission.**

DRIP & RHYTHM is a controlled, single-event, invitation-only private party management platform for **After Dark Events × Hype District** (`5 December 2026`, Muyenga, Kampala, Uganda, `Africa/Kampala`, `18+`, reservation contacts `0781210342`, `0742627388`, `0700246148`).

- Build real, production-grade working functionality — never stubs, fake stats, or UI-only mocks for core behavior.
- Never invent missing event details (venue/times show "To be announced" or are omitted until configured by the super admin).
- Never fabricate organizer logos; use the authentic supplied poster (`assets/event-poster.jpeg`, `1024×1024`) and clean typographic wordmarks (`AFTER DARK EVENTS × HYPE DISTRICT`) structured so standalone official vector logos can drop in later without redesign.

---

## 2. Mandatory Architecture Constraint: Native Runtimes Only

**Containerization is strictly prohibited across development, testing, CI, and production.**

- **DO NOT** create or use Docker, Docker Compose, Dockerfiles, Podman, Devcontainers, Kubernetes, or container-based CI services.
- **Finalized Local Runtimes** (installed and verified — do not reinstall or downgrade):
  - **Python `3.15.0`** (`C:\Users\LENOVO\AppData\Local\Python\pythoncore-3.15-64\python.exe`; create `backend/.venv` via `py -3.15 -m venv backend/.venv` or the verified Python 3.15 path, and invoke `backend\.venv\Scripts\python.exe` directly). Do not use Pipenv, Poetry, Conda, or install Python 3.13.
  - **Node.js `26.13.0` + npm `11.20.0`** (invoke via `npm.cmd` / `npx.cmd` on Windows PowerShell where `npm.ps1` is restricted; never weaken system-wide PowerShell execution policy; do not introduce pnpm or Yarn; commit `package-lock.json` and use `npm ci`).
  - **PostgreSQL `18.7`** (`C:\Program Files\PostgreSQL\18\bin`, `localhost:5432`, Windows service `postgresql-x64-18`). Use dedicated database `drip_and_rhythm`, least-privilege runtime role `drip_app` (never `postgres` superuser), and isolated test role/database `drip_test`. Never expose the `postgres` password in chat, files, logs, or commits. Never substitute SQLite.
  - **Git `2.56.0`**.
- **Local Services**: Next.js dev server (`localhost:3000`), Django `runserver` (`127.0.0.1:8000` — never run Gunicorn as the Windows dev server), native PostgreSQL 18.7, and separate native Python email worker (`python manage.py process_email_jobs`). Never run the email worker as a thread inside Django or inside Next.js.
- **Production Target**: Native Render services via `render.yaml` (Next.js Node.js Web Service, Django Python Private Service with Gunicorn on Linux where supported, separate Python Background Worker, Managed PostgreSQL). Final production runtime versions are verified and finalized during Phase 10 (Production Preparation) without prematurely constraining local development.
- **CI**: Native `ubuntu-latest` GitHub Actions runner using native PostgreSQL (`systemctl`), pinned runtimes, and native Playwright installation.

---

## 3. Authoritative Stack & Architectural Boundaries

- **Backend**: Python `3.15.0`, **latest stable Django release supporting Python 3.15 (`Django 6.1.x` — do not restrict to 5.2 LTS)**, Django REST Framework, `psycopg[binary]` (Psycopg 3), PostgreSQL 18.7, Django ORM, Django Session Authentication (NO JWT), `drf-spectacular`, ReportLab, `qrcode`, Pillow, `cryptography`, Resend SDK + Svix webhook verification, WhiteNoise, Gunicorn (Linux production only).
- **Frontend**: Latest stable mutually compatible Next.js (App Router, SSR + dynamic metadata — NO static export), React, strict TypeScript, Tailwind CSS v4, shadcn/ui, Motion, Lucide React, TanStack Query, React Hook Form, Zod, `@zxing/browser`, `canvas-confetti`, Web Share API.
- **Dependency Discipline**: No alpha, beta, experimental, or RC packages without explicit authorization. Pin resolved compatible versions in `backend/requirements.txt`, `backend/requirements-dev.txt`, and `frontend/package-lock.json`. Surface any genuine Python 3.15 compatibility blocker transparently rather than silently downgrading Python or removing functionality.
- **Single Authoritative Backend**: Django owns all authentication, authorization, invitation lifecycle, uniqueness, PDFs, QR verification, artwork generation, email jobs, and audit logs. **Never** duplicate business logic or build a second backend in Next.js API routes or Server Actions.
- **Single Public Origin**: Browsers talk only to the Next.js origin. Proxy only approved `/api/:path*` paths to `DJANGO_INTERNAL_API_URL`, preserving cookies, CSRF headers, HTTP methods, status codes, binary streams, and raw request body bytes (for webhook HMAC verification). Never create an open/arbitrary proxy or expose internal URLs via `NEXT_PUBLIC_*`.

---

## 4. Non-Negotiable Security, Concurrency & Privacy Rules

1. **Four Isolated Cryptographic Credentials** (256-bit `secrets.token_urlsafe(32)`, stored as SHA-256 digests; never interchangeable):
   - **Claim token** (`/invite/[token]`): Authenticated-encrypted copy (`TOKEN_ENCRYPTION_KEY`) stored only while `UNUSED`, wiped immediately upon claim or revocation.
   - **Admission token** (QR payload `DRIP1:<token>`): Generated only on claim; authenticated-encrypted copy for PDF regeneration; versioned and immediately rotated on guest email correction (invalidating old QRs and stale pending email jobs).
   - **Social sharing token** (`/share/[token]`): Read-only public promotional access only; never authorizes mutations or reveals private info.
   - **Claim receipt token** (`drip_claim_receipt` HTTP-only cookie): Limited-purpose guest session for `/invitation/success` and sharing preferences without creating a guest account or reusing admin `sessionid`. Lifetime is **configurable** (`CLAIM_RECEIPT_TTL_DAYS`, defaulting to an event-aware window through the event + post-event grace period rather than a fixed 7-day expiry) and invalidated immediately on invitation revocation, guest email correction, expiration, or authorized security invalidation.
2. **Authentication & Authorization**:
   - Django session auth only (`HttpOnly`, `SameSite=Lax`, `Secure` in prod); never store credentials in `localStorage`.
   - Enforce CSRF on all state-changing endpoints including login and anonymous `POST /api/invite/{token}/claim/`; exempt ONLY `POST /api/webhooks/resend/` (strict Svix signature verification on raw bytes).
   - Enforce every role & ownership check in Django (`SUPER_ADMIN` vs `ADMIN`). Deactivated admins immediately lose access even on existing sessions. Prevent deactivating/demoting the last active `SUPER_ADMIN`.
   - No public registration; never ship hardcoded admin credentials.
3. **Database Atomicity, Lock Ordering & Worker Reliability**:
   - Enforce event-level email uniqueness at the PostgreSQL level (`UniqueConstraint` on `(event, guest_email_normalized)` where non-null). Normalize by trimming, lowercasing, and IDNA-normalizing domain; do **not** strip Gmail dots or `+aliases`. Do not silently release revoked invitations' email addresses.
   - Duplicate-email attempts must leave the second unused link `UNUSED` and never leak existing guest PII.
   - Follow consistent lock ordering (`Event` -> `User` -> `Invitation` -> `EmailDelivery`) to avoid deadlocks. Keep invitation claiming and email job creation in the same transaction; never call Resend inside the claim transaction.
   - Enforce global and per-admin quotas atomically (`select_for_update()`), counting all generated links (including expired/revoked). Never generate partial bulk batches.
   - Opening/previewing `/invite/[token]` (`GET`) must NEVER consume an invitation.
   - QR scanning (`POST /api/verify/`) and admission (`POST /api/check-in/`) must remain separate actions. Enforce single admission via a PostgreSQL `OneToOneField` constraint + row locking.
   - Email worker uses `SELECT ... FOR UPDATE SKIP LOCKED`, bounded retries, processing leases, stable Resend idempotency keys, pre-send revocation/version checks (documenting the external in-flight race limitation without claiming impossible exactly-once external delivery), and idempotent/monotonic webhook processing.
   - Rate-limit sensitive endpoints via a PostgreSQL-backed limiter (no Redis; no memory-only counters).
4. **Privacy, Caching & Sanitization**:
   - Collect ONLY `nickname` (1–50 Unicode chars, no control chars) and `email` from guests.
   - Default public sharing artwork to anonymous (`show_nickname_publicly = False`).
   - Public artwork and `/share/[token]` must NEVER contain email, QR code, tokens, invitation reference, private venue, or admin info.
   - Never cache authenticated responses, `/invite/*`, or `/api/claim-receipt/*` in shared caches (`Cache-Control: no-store`). Disabled/revoked public sharing endpoints must not serve stale content from application-controlled caches (documenting that downloaded images and third-party social caches cannot be remotely purged).
   - Sanitize CSV exports against spreadsheet formula injection (`=`, `+`, `-`, `@`, `\t`, `\r`).
   - Redact tokens, passwords, secrets, and cookies from application logs and append-only `AuditLog` records.
   - Never allow open redirects on login `next` parameters or auto-navigate to scanned QR URLs.

---

## 5. Visual Design, Installed Design Skills & Animation Boundaries

- **Visual Reference**: [assets/event-poster.jpeg](file:///c:/Users/LENOVO/Desktop/drip-and-rhythm/assets/event-poster.jpeg) (`1024×1024`) — Luxury Afrocentric nightlife, warm cinematic amber/burnt-orange lighting, Midnight Brown (`#190D08`), Dark Chocolate (`#421509`), Burnt Orange (`#E85D19`), Sunset Orange (`#FF8C32`), Golden Amber (`#FFBE55`), Champagne Gold (`#F5CE86`), Warm Ivory (`#FFF3E0`), Deep Red (`#A51B12`).
- **Typography**: Self-hosted local `Anton`, `WindSong`, `Montserrat`, and `Noto Sans` (Unicode fallback for PDFs/artwork) with committed OFL licenses. Verify real WCAG contrast rather than assuming poster combinations pass.
- **Installed Project-Level Design Skills** (`.agents/skills/` — already installed; do not reinstall, duplicate, or auto-update; load selectively per task; never send private project/guest/credential data to external skill scripts):
  - `frontend-design`: Frontend architecture, public/guest/sharing/admin layouts, and reusable components.
  - `design-taste-frontend`: Editorial creative direction and anti-slop elevation adapted strictly to the DRIP & RHYTHM palette and fonts.
  - `scroll-craft`: Selectively on the public homepage (`/`) only for cinematic layered scroll storytelling.
  - `impeccable`: Targeted UI critique, accessibility/contrast/responsive auditing, and polish checkpoints.
- **Animation Boundaries**:
  - Prefer `motion` and native CSS only. Do **not** add GSAP, Lenis, Three.js, WebGL, or heavy animation dependencies without explicit approval.
  - No scroll hijacking; never block navigation or forms on animation completion; no unnecessary long filler sections.
  - Do **not** put complex scroll-driven animations in `/invite/[token]`, `/admin/login`, `/admin/dashboard`, `/admin/invitations`, `/admin/scanner`, or check-in workflows.
  - Respect `prefers-reduced-motion`; no autoplaying audio.

---

## 6. Explicitly Excluded Features

Do **not** implement: public registration, guest login accounts, guest passwords, full legal name or phone collection, guest OTP, ticketing/payments/subscriptions, multi-event management UI, public link generation, SMS or WhatsApp Business API integration, automatic social posting, Redis, Celery, Firebase, Supabase, S3/R2/external PDF storage, Kubernetes, microservices, WebSockets, native mobile apps, offline admission sync, unrequested AI features, or any containerization.

---

## 7. Testing, Visual Verification & Operational Guardrails

- Test backend concurrency, lock ordering, uniqueness, quotas, worker leases, and webhooks against **actual PostgreSQL 18.7** (never SQLite).
- Test real QR decoding from rendered ReportLab PDFs (`pypdfium2` + `zxing-cpp`) and visually verify generated PDFs + all 4 dedicated Pillow PNG compositions (`1080×1920`, `1080×1080`, `1080×1350`, `1200×630`) including long/Unicode nicknames and safe areas.
- Perform mandatory Antigravity browser visual verification across `320px, 360px, 375px, 390px, 414px, 768px, 1024px, 1440px, 1920px` and capture reviewable screenshots at checkpoints; fix visible layout defects before declaring frontend phases complete.
- Never remove or weaken failing tests, never disable security checks to work around proxy/test issues, and clearly separate unit, integration, local E2E, mocked external, live external, physical-device, and production verification.
- Keep `IMPLEMENTATION.md` updated concisely throughout development; minimize redundant file re-reads, web searches, or skill loading.
- **Do not** push to GitHub, deploy to Render, purchase domains/plans, provision paid services, or alter unrelated system settings/databases without explicit user authorization.
