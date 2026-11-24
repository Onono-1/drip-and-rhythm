# System Architecture

- **Topology**: Modular Django 6.1 monolith (`backend/`) + Next.js 16 App Router SSR frontend (`frontend/`) + native PostgreSQL 18.7 + separate native Python email worker (`python manage.py process_email_jobs`).
- **Single Public Origin**: Browsers talk exclusively to Next.js. `frontend/src/app/api/[...path]/route.ts` forwards only allowlisted `/api/*` segments to `DJANGO_INTERNAL_API_URL`, preserving cookies, `X-CSRFToken`, status codes, binary PNG/CSV streams, and raw webhook bytes.
- **Authoritative State**: Django owns all authentication, RBAC, invitation lifecycle, quotas, PDF/QR/PNG rendering, email queuing, check-ins, and audit logs. Next.js contains zero duplicate business logic.
- **Lock Ordering**: Multi-row transactions acquire PostgreSQL `SELECT ... FOR UPDATE` locks strictly in `Event` → `User` → `Invitation` → `EmailDelivery` order. The email worker claims jobs via `SELECT ... FOR UPDATE SKIP LOCKED` with lease recovery.
