# Acceptance Criteria Checklist

- [x] Public homepage authentically reflects `assets/event-poster.jpeg` without unconfirmed venue/time fabrication.
- [x] Session + CSRF authentication and Django-enforced `SUPER_ADMIN` / `ADMIN` RBAC.
- [x] Single & bulk link generation with atomic global and per-admin quota enforcement.
- [x] Non-consuming `GET /invite/[token]` and atomic single-use `POST` claim with PostgreSQL email uniqueness (second link stays `UNUSED` on duplicate email).
- [x] Single-page ReportLab VIP PDF pass with scannable `DRIP1:<token>` QR verified via `pypdfium2` + `zxing-cpp`.
- [x] Independent `process_email_jobs` worker (`SKIP LOCKED`, leases, retries) + Svix-verified Resend webhooks.
- [x] Configurable `drip_claim_receipt` cookie and 4 dedicated Pillow PNG formats (`1080×1920`, `1080×1080`, `1080×1350`, `1200×630`) with anonymous default and instant revocation/cache busting.
- [x] Separate QR/manual verification and atomic `OneToOneField` check-in preventing concurrent double admission.
- [x] Guest email correction rotates admission credential and invalidates previous QR + claim receipt.
- [x] Responsive across `390px`, `768px`, and `1440px`; frontend production build succeeds; native `render.yaml` and native Linux CI prepared.
