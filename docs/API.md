# REST API Reference

Base path: `/api/` (proxied same-origin via Next.js; OpenAPI 3.1 schema at `/api/schema/` and Swagger UI at `/api/docs/`).

All error responses follow:
```json
{
  "error": {
    "code": "DUPLICATE_EMAIL",
    "message": "Human-readable explanation.",
    "details": {}
  }
}
```

## Endpoints Summary
- **Auth**: `GET /api/auth/csrf/`, `POST /api/auth/login/`, `POST /api/auth/logout/`, `GET|PATCH /api/auth/me/`, `POST /api/auth/password/change/`, `POST /api/auth/password/forgot/`, `POST /api/auth/password/reset/`
- **Event**: `GET /api/event/public/` (public), `GET /api/event/settings/` (admin), `PATCH /api/event/settings/` (super admin)
- **Administrators** *(super admin)*: `GET|POST /api/users/`, `GET|PATCH /api/users/{id}/`, `POST /api/users/{id}/activate/`, `POST /api/users/{id}/deactivate/`
- **Invitations** *(admin)*: `GET|POST /api/invitations/`, `POST /api/invitations/bulk/`, `GET /api/invitations/export/` *(super admin)*, `GET /api/invitations/{id}/`, `GET /api/invitations/{id}/claim-link/`, `POST /api/invitations/{id}/revoke/`, `POST /api/invitations/{id}/resend/`, `POST /api/invitations/{id}/correct-guest/` *(super admin)*, `GET /api/invitations/{id}/deliveries/`
- **Guest Claiming & Sharing**: `GET /api/invite/{token}/` (non-consuming), `POST /api/invite/{token}/claim/` (`{ "nickname", "email" }`), `GET /api/claim-receipt/`, `GET|POST|PATCH /api/claim-receipt/sharing/`, `GET /api/share/{token}/`, `GET /api/share/{token}/image/?format=story|square|portrait|preview`
- **Entrance Verification & Check-In** *(admin)*: `POST /api/verify/` (`{ "qr_payload" }`), `POST /api/verify/manual/` (`{ "reference" }`), `POST /api/check-in/`, `GET /api/check-ins/`, `GET /api/check-ins/export/` *(super admin)*
- **Metrics, Audit & System**: `GET /api/dashboard/`, `GET /api/audit-logs/` *(super admin)*, `POST /api/webhooks/resend/` (Svix-signed), `GET /api/health/`
