# MASTER DEVELOPMENT PROMPT
## DRIP & RHYTHM — Private Party Invitation Management System

### 1. Your role and responsibilities

Act as a senior full-stack software engineer, software architect, UI/UX designer, security engineer and quality assurance engineer.

Your task is to design, develop, test and prepare for production a complete, lightweight, secure and visually outstanding private party invitation management website called **DRIP & RHYTHM**.

This application is being developed using Google Antigravity.

Use your planning, coding, terminal, browser testing and artifact-generation capabilities throughout development.

You are responsible for building actual working functionality, not just a UI prototype or demonstration.

Before implementation:

- Inspect the existing project workspace.
- Read this entire specification.
- Examine the supplied event poster.
- Create a comprehensive implementation plan.
- Identify dependencies, security risks and implementation requirements.
- Present the implementation plan for review.
- Create persistent project instructions in `AGENTS.md` and the supported Antigravity workspace rules.
- Maintain an implementation checklist throughout development.

Do not repeatedly ask questions that are already answered in this specification. Make reasonable technical decisions where necessary, document them and continue.

Keep the application lightweight, maintainable and suitable for a single private party. Do not overengineer it.

**Mandatory architecture constraint: native runtimes only.** Do not use Docker, Docker Compose, Dockerfiles, or alternative containerization technologies, including in local development, CI, deployment and testing. Use a Python virtual environment, npm, locally installed PostgreSQL, and a separate native Python email worker. Deploy through Render's native Node.js and Python runtimes with managed PostgreSQL. This constraint must be preserved in the implementation plan, AGENTS.md, workspace rules and all project documentation.

---

# 2. Project overview

DRIP & RHYTHM is an exclusive private party combining fashion, music and culture.

The website will allow authorized event administrators to generate unique, single-use invitation links and distribute them to selected guests.

When guests open their invitation links, they will enter their nickname and email address.

After a successful claim:

1. The invitation link becomes permanently consumed.
2. A personalized PDF invitation is generated.
3. A unique admission QR code is embedded in the PDF.
4. The official invitation is delivered to the guest's email address.
5. The guest sees a beautifully designed success page.
6. The guest receives access to personalized “Invitation Secured” promotional artwork.
7. The guest can download or share the artwork and its associated public webpage.

At the party entrance, authorized administrators can scan the QR code, verify the invitation and admit the guest.

Every official invitation permits exactly one admission.

This is not a ticket-selling platform. It is a controlled, invitation-only event management application.

---

# 3. Event information

Use the following initial event configuration:

- Event name: DRIP & RHYTHM
- Event subtitle: Private Party
- Tagline: An affair of fashion, music and culture
- Organizers: After Dark Events × Hype District
- Event date: 5 December 2026
- Location: Muyenga, Kampala, Uganda
- Exact venue: Configurable later
- Event starting time: Configurable later
- Event ending time: Optional and configurable
- Age restriction: 18+
- Time zone: Africa/Kampala
- Language: English
- Admission capacity per invitation: One person
- Event hashtag: #DripAndRhythm

Reservation contact numbers:

- 0781210342
- 0742627388
- 0700246148

Verify these contact numbers and visual branding against the supplied event poster.

Do not invent missing event information.

The super administrator must be able to configure event information from the administration dashboard without modifying source code.

Display only confirmed information publicly. If the exact venue or event time has not been configured, omit it or display an appropriate “To be announced” message.

Use timezone-aware dates and times throughout the application.

---

# 4. Technology stack

## 4.1 Frontend

Use:

- Next.js with App Router.
- React.
- TypeScript with strict type checking.
- Tailwind CSS.
- shadcn/ui.
- Motion, formerly Framer Motion.
- Lucide React.
- TanStack Query.
- React Hook Form.
- Zod.
- ZXing Browser for QR scanning.
- Canvas Confetti for lightweight celebration effects.
- Web Share API for native social sharing where supported.

Use stable and mutually compatible dependency versions.

Use Next.js Server Components by default where appropriate.

Use Client Components only where interactivity, browser APIs, state management or animations require them.

Do not use Vite or React Router.

Use Next.js file-based routing, layouts, loading boundaries, error boundaries and metadata APIs.

Do not implement a second backend or duplicate Django business logic using Next.js API routes or Server Actions.

Next.js is responsible for frontend presentation, server rendering, metadata and communication with the Django API.

## 4.2 Backend

Use:

- Python.
- Django.
- Django REST Framework.
- PostgreSQL.
- Django ORM.
- Django Session Authentication.
- drf-spectacular.
- ReportLab.
- Python qrcode.
- Pillow.
- Resend transactional email API.
- A lightweight PostgreSQL-backed background email worker.

Use the latest stable, officially supported Django release compatible with the installed Python 3.15 runtime (Django 6.1.x — currently `6.1.3`+); do not restrict Django to Django 5.2 LTS.

## 4.3 Development and production infrastructure

Use:

- Git (installed local version: `2.56.0`).
- GitHub.
- GitHub Actions.
- Python virtual environments (`backend/.venv`) and pip using the installed Python `3.15.0` runtime.
- Node.js (`26.13.0`) and npm (`11.20.0`, invoked via `npm.cmd` / `npx.cmd` on Windows PowerShell where `npm.ps1` is restricted) with a committed `package-lock.json`.
- Locally installed PostgreSQL `18.7` (`localhost:5432`, dedicated database `drip_and_rhythm`, least-privilege role `drip_app`, isolated test role `drip_test`) for development and testing.
- Render native Node.js and Python services (final production runtime versions and hosting settings verified and finalized during Phase 10 — Production Preparation).
- Render managed PostgreSQL for production.
- A separate native Python process for the email worker.
- Gunicorn (production Linux only; use Django's development server locally on Windows).
- WhiteNoise where Django static assets require it.
- Node.js production runtime for Next.js.
- Optional Cloudflare DNS management.

Use the finalized local runtimes without unnecessary downgrades or reinstalls. Commit fully pinned Python dependency requirements (`backend/requirements.txt` and `backend/requirements-dev.txt`) and the npm lockfile (`frontend/package-lock.json`). Use `pip install -r requirements.txt` and `npm ci` for reproducible installation in CI and production. Do not install alpha, beta, experimental, or release-candidate dependencies unless explicitly authorized. Final production runtime versions for Render will be verified and documented during Phase 10 without prematurely constraining local development.

Do not introduce Redis, Celery, Kubernetes, Firebase, Supabase, external object storage or microservices.

---

# 5. System architecture

Use a modular monolithic backend with a separate Next.js frontend in a single repository.

The Django backend is the authoritative source for authentication, authorization, invitation claims, guest information, QR verification, event settings and email delivery.

The browser should communicate with the application through one public origin.

Preferred production architecture:

```text
Guests and Administrators
          |
        HTTPS
          |
   Next.js (native Node.js web service)
          |
   Django REST API (native Python service / Gunicorn)
          |
   Managed PostgreSQL
          |
   Email worker (separate native Python process)
          |
       Resend API
```

Deploy Next.js as the public-facing application.

Use a private Django service where supported by the hosting configuration.

Proxy approved `/api/` requests from the public application to Django using a carefully configured reverse proxy or Next.js rewrite strategy.

Preserve cookies, request methods, headers, CSRF protection, response status codes and email webhook request bodies.

Do not create an unrestricted proxy accepting arbitrary destination URLs.

Server-rendered Next.js pages may communicate with Django through an internal service URL.

Do not expose internal service URLs or secrets to the browser.

Authenticated responses, invitation pages and guest-specific information must never be stored in shared caches.

Public sharing pages must reflect revocations and privacy changes without serving stale guest information.

Use native local development with four components:

- Next.js development server, normally at `http://localhost:3000`.
- Django development server, normally at `http://127.0.0.1:8000`.
- Locally installed PostgreSQL, normally on port 5432.
- A separate Django email worker process running `python manage.py process_email_jobs`.

Configure the Next.js development API proxy to use the local Django server, while browsers continue to access the API through the Next.js origin. Ensure CSRF and session cookies work correctly in development and production; do not disable security checks to make the proxy work.

Provide `render.yaml` for the native production services: a public Next.js Node.js web service, a Django Python private service where supported, a native Python background worker and a managed PostgreSQL database. The API and worker must share the same database and compatible backend settings and credential encryption configuration.

Do not start the worker as a thread in Django or inside Next.js. The worker must remain independently supervised and restartable.

If the preferred production topology requires paid hosting, document the requirements and expected service count without automatically purchasing anything.

---

# 6. Recommended repository structure

Organize the project approximately as follows:

```text
drip-and-rhythm/
├── assets/
│   └── event-poster.jpeg
├── backend/
│   ├── config/
│   │   ├── settings/
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── apps/
│   │   ├── accounts/
│   │   ├── events/
│   │   ├── invitations/
│   │   ├── communications/
│   │   ├── checkins/
│   │   └── audit/
│   ├── templates/
│   │   ├── emails/
│   │   └── documents/
│   ├── static/
│   │   ├── fonts/
│   │   └── branding/
│   ├── tests/
│   ├── manage.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── .python-version
│   └── .env.example
├── frontend/
│   ├── public/
│   │   ├── images/
│   │   ├── fonts/
│   │   └── branding/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (public)/
│   │   │   ├── (guest)/
│   │   │   ├── admin/
│   │   │   ├── share/
│   │   │   ├── layout.tsx
│   │   │   ├── not-found.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── schemas/
│   │   ├── types/
│   │   ├── providers/
│   │   └── lib/
│   ├── tests/
│   ├── package.json
│   ├── package-lock.json
│   ├── .node-version
│   ├── .env.example
│   └── next.config.ts
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROJECT_REQUIREMENTS.md
│   ├── DESIGN_SYSTEM.md
│   ├── ACCEPTANCE_CRITERIA.md
│   └── API.md
├── .github/
│   └── workflows/
├── .env.example
├── .gitignore
├── render.yaml
├── AGENTS.md
├── IMPLEMENTATION.md
├── DEPLOYMENT.md
├── SECURITY.md
└── README.md
```

This structure is a guideline. Adjust it when technically necessary without introducing unnecessary abstractions.

---

# 7. User roles and permissions

The application has three categories of users.

## 7.1 Super administrator

The super administrator has full application management permissions.

Responsibilities:

- Create administrator accounts.
- Activate and deactivate administrator accounts.
- Configure administrator invitation limits.
- Configure global event invitation limits.
- Configure event details.
- Generate individual invitation links.
- Generate invitation links in bulk.
- View all invitation records.
- Search and filter invitations.
- Revoke any invitation.
- Resend any invitation email.
- Correct guest information.
- View all email delivery records.
- Verify invitation QR codes.
- Admit guests.
- View global dashboard statistics.
- Export invitation and admission records.
- View audit logs.
- Manage event configuration.
- Manage their own account.

## 7.2 Ordinary administrator

Ordinary administrators can:

- Log in securely.
- Generate individual invitation links.
- Generate bulk invitation links.
- Copy and share invitation links.
- View all invitation records, including those created by other administrators.
- Search and filter all invitations.
- View global dashboard statistics.
- Revoke invitations they generated.
- Resend invitation emails for invitations they generated.
- Verify any invitation QR code.
- Perform manual invitation verification.
- Admit any valid guest.
- View admission records.
- Manage their own account.

Ordinary administrators cannot:

- Create other administrators.
- Modify global event settings.
- Change invitation limits.
- Revoke invitations belonging to other administrators.
- Resend emails belonging to other administrators.
- Correct guest information.
- Export the entire guest database.
- Access global audit logs.
- Promote themselves to super administrator.

All permission checks must be enforced by Django.

Hiding buttons in the frontend is not a sufficient authorization mechanism.

## 7.3 Guest

Guests do not create accounts or log in.

Guests can:

- View the public event homepage.
- Open a valid invitation link.
- Enter their nickname and email address.
- Claim an invitation.
- Receive their official PDF invitation by email.
- View their successful claim page.
- Download promotional artwork.
- Choose whether to display their nickname publicly.
- Share promotional artwork and the public sharing webpage.

Guests cannot:

- Generate invitation links.
- Access other guests' information.
- Access administrator routes.
- Verify admission QR codes.
- Change their claimed email address independently.
- Claim an invitation without a valid invitation link.

---

# 8. Authentication and administrator accounts

Implement secure Django session-based authentication.

Do not use JWT authentication.

Administrator authentication must support:

- Login with email and password.
- Logout.
- Current authenticated administrator information.
- Password change.
- Forgot password.
- Secure email-based password reset.
- Account activation and deactivation.
- Session expiration.
- Brute-force protection.

There must be no public registration.

Use a custom Django user model from the beginning of development.

Suggested user fields:

- UUID primary key.
- Email address.
- Display name.
- Password.
- Role.
- Invitation generation limit.
- Active status.
- Date joined.
- Last login.
- Created at.
- Updated at.

Use Django's built-in password hashing and validators.

Configure secure HTTP-only session cookies, appropriate SameSite settings and HTTPS in production.

Implement CSRF protection for authentication and all applicable state-changing requests, including anonymous invitation claims.

Provide a reliable CSRF initialization mechanism for Next.js.

Never store session credentials in browser localStorage.

Deactivated administrators must lose access to protected actions, including through previously established sessions.

Prevent accidental deactivation or removal of the final active super administrator.

Provide a secure management command for creating the initial super administrator.

Never ship hardcoded administrator credentials.

---

# 9. Database models

Create well-structured Django models with database constraints, appropriate indexes and migrations.

## 9.1 User

Stores administrator accounts, roles, account status and individual invitation limits.

## 9.2 Event

Stores event configuration.

Suggested fields:

- UUID.
- Name.
- Slug.
- Subtitle.
- Tagline.
- Organizer information.
- Event date.
- Starting time.
- Ending time.
- Location.
- Exact venue.
- Venue visibility settings.
- Reservation contacts.
- Time zone.
- Age restriction.
- Global invitation limit.
- Invitation claim deadline.
- Claiming enabled.
- Admission enabled.
- Public sharing enabled.
- Created at.
- Updated at.

The application manages one event through its user interface.

Do not build a multiple-event management platform.

## 9.3 Invitation

Suggested fields:

- UUID.
- Event foreign key.
- Unique invitation reference.
- Claim token digest.
- Securely protected claim-token recovery data, if needed for copying previously generated links.
- Admission token digest.
- Securely protected admission-token recovery data for PDF regeneration.
- Social sharing token digest.
- Secure sharing credential recovery data where required.
- Nickname.
- Normalized guest email.
- Invitation status.
- Generated by administrator.
- Generated at.
- Expires at.
- Claimed at.
- Revoked at.
- Revoked by administrator.
- Revocation reason.
- Public nickname visibility.
- Public sharing enabled.
- Created at.
- Updated at.

Invitation references should be human-readable, for example:

```text
DR-000001
DR-000002
DR-000003
```

References must be unique and generated safely during simultaneous requests.

Public references are not authentication credentials.

## 9.4 EmailDelivery

Stores email delivery jobs and delivery attempts.

Suggested fields:

- UUID.
- Invitation foreign key where applicable.
- Email type.
- Recipient address.
- Delivery status.
- Provider.
- Provider message ID.
- Stable idempotency key.
- Attempt count.
- Maximum attempts.
- Next retry time.
- Processing lease expiration.
- Last attempted at.
- Sent at.
- Delivered at.
- Failure information.
- Created at.
- Updated at.

Ensure invitation emails, password reset emails and administrative resends can be managed securely.

Additional normalized delivery-attempt or webhook-event records may be introduced if needed for reliable processing.

## 9.5 CheckIn

Stores successful admissions.

Suggested fields:

- UUID.
- Invitation reference or foreign key.
- Verified by administrator.
- Check-in timestamp.
- Verification method.
- Optional administrative notes.

Enforce a database-level unique constraint on the invitation relationship.

An invitation can have only one successful check-in.

## 9.6 AuditLog

Stores important administrative and security-related activity.

Suggested fields:

- UUID.
- Administrator.
- Action type.
- Target object type.
- Target object identifier.
- Sanitized metadata.
- Timestamp.

Audit records should be append-only through the application interface.

Never store passwords, complete secret tokens, session cookies or raw API credentials in audit logs.

---

# 10. Invitation link generation

Only authenticated administrators can generate invitation links.

Support:

- Individual generation.
- Bulk generation.
- Configurable bulk quantity limits.
- Invitation expiration settings.
- Unique invitation references.
- Copying an individual link.
- Copying multiple generated links.
- Native sharing where supported.
- WhatsApp sharing through ordinary share links.
- Downloading generated links in CSV format subject to role permissions.

Generate cryptographically secure random tokens using Python's standard cryptographic randomness facilities.

Use sufficient entropy, preferably 256-bit random tokens.

Example URL:

```text
https://example.com/invite/secure-random-token
```

Never use sequential IDs or predictable values as claim tokens.

Store token digests for secure lookup.

Where an administrator must retrieve an unused invitation link, use authenticated encryption with a separate server-side key rather than insecure plaintext storage.

Never reveal consumed claim credentials unnecessarily.

## 10.1 Invitation limits

The super administrator can configure:

- Maximum total event invitations.
- Maximum invitations per administrator.
- Unlimited invitations when limits are disabled.
- Maximum quantity in an individual bulk-generation request.

As a conservative default, count all issued links toward generation quotas, including revoked and expired links.

Do not silently restore quota when an invitation is revoked.

The super administrator can adjust limits when necessary.

Document this quota policy clearly.

Enforce quotas using atomic database transactions and appropriate row locking.

Simultaneous bulk-generation requests must never exceed configured limits.

---

# 11. Invitation claiming workflow

This is the most important guest-facing functionality.

When the guest opens:

```text
/invite/[token]
```

The system must validate the invitation token.

Possible states:

- Valid and unused.
- Already claimed.
- Expired.
- Revoked.
- Invalid or nonexistent.
- Claiming temporarily disabled.

Opening or previewing the URL must never consume the invitation.

WhatsApp previews, browser prefetching, automated crawlers and search engines must not claim invitations.

Only an intentional, valid POST request may claim an invitation.

## 11.1 Required guest information

Collect only:

1. Nickname.
2. Email address.

Both fields are mandatory.

Do not collect:

- Full legal name.
- Phone number.
- Password.
- Address.
- Date of birth.
- Social media account.

Nicknames must support normal Unicode text and spaces.

Use reasonable length limits, such as 1–50 characters.

Trim surrounding whitespace.

Reject control characters and unsafe input.

Never render nickname content as executable HTML.

Duplicate nicknames are permitted.

## 11.2 Duplicate email prevention

An email address can claim only one invitation for the event.

Normalize email addresses consistently:

- Trim surrounding spaces.
- Apply case-insensitive normalization.
- Validate the email format.
- Apply a consistent internationalized-domain policy.

Do not automatically remove Gmail dots, plus-address aliases or provider-specific address components.

Enforce uniqueness at the PostgreSQL database level using an appropriate unique constraint on the event and normalized email.

Unused invitations must be able to exist without an associated email address.

If a guest attempts to claim another invitation using an already registered email, display:

**Invitation already secured.**

An invitation has already been registered using this email address. Please check your inbox or spam folder for your official admission pass.

The second invitation link must remain unused.

Do not expose the existing invitation reference, QR code, guest nickname or other private information in duplicate-email responses.

Rate-limit these requests to reduce email enumeration.

## 11.3 Successful claim

Within a database transaction:

1. Lock and validate the invitation record.
2. Verify that the invitation has not been claimed, revoked or expired.
3. Check that invitation claiming is enabled.
4. Validate the nickname and email address.
5. Enforce email uniqueness.
6. Save the guest information.
7. Mark the invitation as claimed.
8. Generate an independent admission credential.
9. Create a persistent email delivery job.
10. Commit the transaction.

Handle concurrent uniqueness conflicts gracefully.

Do not create external email side effects before the transaction commits.

A successful claim consumes the invitation link immediately, regardless of whether email delivery has completed.

Email failure must not make a claimed invitation available to another person.

Return the appropriate successful claim state to Next.js.

Redirect the guest to the celebration page.

Use a limited-purpose, secure claim receipt cookie (`drip_claim_receipt`, HTTP-only) to preserve access to the guest's own success experience and sharing preferences without creating a guest account or reusing administrator sessions. Make the claim receipt lifetime configurable (rather than fixed at seven days), with an event-aware default allowing guests to manage sharing preferences through the event and immediate server-side invalidation upon invitation revocation, guest email correction, expiration, or authorized security invalidation.

Refreshing the success page must not create another invitation.

Opening a previously consumed claim link from another browser must not reveal guest information or private credentials.

---

# 12. Invitation lifecycle

Maintain independent invitation, email and admission states.

## 12.1 Invitation states

- Unused.
- Claimed.
- Expired.
- Revoked.

## 12.2 Email delivery states

- Not scheduled.
- Pending.
- Processing.
- Sent.
- Delivered, when confirmed by the provider.
- Failed.
- Bounced.

## 12.3 Admission states

- Not admitted.
- Admitted.

Do not treat a failed email as an unused invitation.

Do not treat email delivery as proof of admission.

Do not expire an already claimed admission pass merely because its original claim deadline has passed.

Admission validity must follow the event admission configuration.

Revoked invitations must not be valid for admission.

Preserve historical admission records.

Do not silently reverse a successful check-in.

---

# 13. Official PDF invitation generation

Generate a personalized PDF admission pass using ReportLab.

The PDF must have a professional, high-quality design matching the supplied event poster.

It should resemble an exclusive VIP admission pass rather than a plain administrative document.

Include:

- After Dark Events branding.
- Hype District branding.
- DRIP & RHYTHM event title.
- Private Party subtitle.
- Event tagline.
- Event date.
- Confirmed event time.
- Appropriate venue information.
- Guest nickname.
- Guest email address.
- Unique invitation reference.
- Unique admission QR code.
- 18+ restriction.
- Single-admission notice.
- Admission instructions.
- Responsible drinking notice.

Suggested invitation wording:

**EXCLUSIVE ADMISSION PASS**

Your invitation to DRIP & RHYTHM is officially secured.

Present this invitation at the entrance for verification.

Valid for one admission only.

Use appropriate typography, generous spacing, consistent alignment and a strong visual hierarchy.

The PDF must remain readable when viewed on a mobile phone or printed.

Use a compact, single-page design.

Embed licensed font files locally.

Do not depend on live external font requests during PDF generation.

Support long nicknames without overflowing text containers.

Use appropriate fallback fonts for unsupported Unicode characters.

Generate PDFs in memory and attach them directly to invitation emails.

External PDF storage is unnecessary.

Use a safe filename such as:

```text
DRIP-AND-RHYTHM-DR-000001.pdf
```

Regenerating the same invitation must preserve its admission identity unless an administrator explicitly rotates its admission credential.

---

# 14. QR code generation and credential security

Use Python qrcode and Pillow to generate QR codes.

Each claimed invitation receives a cryptographically secure admission credential separate from its original claim token.

The system must maintain four independent credentials:

1. Claim credential (`/invite/[token]`).
2. Admission credential (QR payload `DRIP1:<token>`).
3. Social sharing credential (`/share/[token]`).
4. Claim receipt credential (`drip_claim_receipt` HTTP-only cookie, configurable lifetime, limited to success & sharing preferences).

These credentials must never be interchangeable.

The QR code must not contain:

- The original claim token.
- A guest email address.
- The guest nickname.
- Administrator credentials.
- A URL that automatically admits the guest.

The QR code should contain an opaque, versioned admission payload that authorized scanners can interpret.

For example:

```text
DRIP1:secure-admission-token
```

Treat all scanned payloads as untrusted input.

Do not automatically navigate to arbitrary URLs embedded in scanned QR codes.

Use high-contrast black-and-white QR codes with sufficient quiet-zone padding.

Maintain an appropriate error-correction level.

Do not place artwork or logos over QR modules unless reliable decoding has been verified.

Test real QR code readability from generated PDF files.

Test scanning from printed copies and mobile screens where practical.

---

# 15. Email delivery system

Integrate Resend for transactional email delivery.

Use secure environment variables for:

- Resend API key.
- Verified sender email.
- Sender display name.
- Reply-to email.
- Webhook verification secret.

Suggested sender display name:

```text
DRIP & RHYTHM
```

Suggested subject:

```text
You're on the list! Your DRIP & RHYTHM invitation is secured.
```

The email should contain:

- Event branding.
- Personalized greeting using the guest's nickname.
- Invitation confirmation.
- Event date.
- Confirmed event information.
- Instructions to open the attached PDF.
- Invitation reference.
- Appropriate support information.
- A promotional sharing link when available.
- A warning not to share the official admission QR code.

Suggested email content:

Hey [Nickname],

It's official — you're on the list!

Your exclusive invitation to DRIP & RHYTHM has been secured.

Get ready for an affair of fashion, music and culture on 5 December 2026.

Your official admission pass is attached to this email. Please present its QR code at the entrance.

The drip is ready. The rhythm is calling.

See you there.

After Dark Events × Hype District

Create responsive HTML email templates with plain-text alternatives.

Do not rely on complex JavaScript, interactive components or unsupported email styling.

## 15.1 Background email worker

Do not block the invitation claim request while sending an email.

Implement a database-backed worker using a Django management command.

Example:

```bash
python manage.py process_email_jobs
```

The worker must support:

- Pending job processing.
- Atomic job acquisition.
- Safe operation with concurrent workers.
- Processing leases.
- Recovery from interrupted jobs.
- Automatic retries.
- Exponential backoff.
- Maximum retry limits.
- Permanent failure tracking.
- Stable provider idempotency keys.
- Graceful shutdown.

Use PostgreSQL locking mechanisms where appropriate.

Generate the PDF and send the email after the job has been acquired.

Distinguish retrying an existing delivery from an administrator deliberately requesting a resend.

Do not promise exactly-once external email delivery if the provider cannot guarantee it.

Handle ambiguous provider responses carefully and use documented provider idempotency behavior to minimize duplicate emails.

## 15.2 Email webhooks

Where supported, integrate verified Resend webhooks for delivery and bounce events.

Verify webhook signatures using the provider's documented procedure.

Preserve the raw request body where signature verification requires it.

Prevent duplicate webhook processing.

Handle out-of-order provider events without incorrectly reverting delivery status.

Do not trust unsigned webhook requests.

## 15.3 Administrator resend functionality

Authorized administrators can resend an invitation to its existing email address.

Resending must:

- Preserve the invitation reference.
- Preserve the admission credential.
- Avoid creating another invitation.
- Create a new intentional delivery record.
- Be rate-limited.
- Be audit logged.

---

# 16. Guest information corrections

Only the super administrator can correct a claimed invitation's nickname or email address.

When correcting a nickname:

- Validate the new nickname.
- Update the guest information.
- Regenerate affected promotional artwork.
- Record the change in the audit log.
- Allow an updated PDF invitation to be resent.

When correcting an email address:

- Validate the new email.
- Enforce event-level email uniqueness.
- Reject corrections for already admitted guests.
- Invalidate the previous admission credential.
- Generate a replacement admission credential.
- Invalidate pending delivery jobs that reference the previous credential.
- Generate and deliver an updated PDF.
- Rotate or disable existing public sharing credentials where appropriate.
- Record the administrative action.

Never allow an old QR credential to remain valid following an email correction.

Do not automatically release revoked invitations' associated email addresses for reuse.

Any exceptional recovery policy must be documented and explicitly authorized.

---

# 17. QR verification and guest admission

Create a dedicated administrator QR scanning page.

Route:

```text
/admin/scanner
```

Use ZXing Browser for camera-based scanning.

Requirements:

- Request camera permission appropriately.
- Prefer the rear-facing camera on mobile devices.
- Support switching cameras.
- Stop camera streams when leaving the scanner page.
- Avoid continuous duplicate scan submissions.
- Provide a manual verification fallback.
- Display clear loading states.
- Display clear verification results.
- Support poor-light environments where browser hardware controls allow it.
- Provide optional torch control when supported.

The scanner must require an authenticated administrator.

## 17.1 Verification results

Display one of the following:

### Valid invitation

Use a clear success indicator.

Display:

- Guest nickname.
- Guest email address.
- Invitation reference.
- Invitation status.
- Admission eligibility.
- Claim date.
- Generating administrator where useful.

Provide an explicit **Admit Guest** button.

### Already admitted

Display:

- Guest nickname.
- Invitation reference.
- Previous check-in time.
- Administrator responsible for admission.

Do not allow another check-in.

### Revoked invitation

Clearly indicate that admission is not permitted.

### Invalid invitation

Clearly indicate that the QR code is not recognized.

### Admission unavailable

Display an appropriate message if admission is disabled or verification cannot be completed.

Never show a successful verification result based only on locally decoded QR content.

## 17.2 Admission transaction

Scanning must not automatically consume the admission credential.

Verification and admission must be separate actions.

When the administrator presses Admit Guest:

1. Revalidate authorization.
2. Revalidate the admission credential or short-lived verification context.
3. Lock the invitation record.
4. Check current invitation validity.
5. Check that admission is enabled.
6. Check for an existing admission record.
7. Create the check-in record.
8. Record the administrator and timestamp.
9. Commit the transaction.
10. Display successful admission.

Enforce the one-admission rule through a database-level uniqueness constraint.

If two administrators simultaneously attempt to admit the same guest, only one admission can succeed.

## 17.3 Manual verification

Allow administrators to enter a human-readable invitation reference manually.

Provide a way to inspect the corresponding record.

Manual admission must require explicit confirmation and be recorded as a manual verification action.

Do not treat a predictable invitation reference as equivalent to a cryptographically secure QR credential.

Include a warning that manual admission requires additional staff verification of the guest's presented pass.

Do not introduce offline admission synchronization.

The scanner requires internet access to verify invitations against the central database.

---

# 18. Public website

Build a visually outstanding public event landing page.

Route:

```text
/
```

The homepage must communicate that DRIP & RHYTHM is exclusive, premium and invitation-only.

Use the supplied event poster as the primary source of design inspiration.

Include:

- Organizer branding.
- Cinematic hero section.
- Large DRIP & RHYTHM typography.
- Private Party decorative heading.
- Event tagline.
- Event date.
- Location.
- Countdown.
- Event information.
- Reservation contacts.
- Age restriction.
- Invitation-only notice.
- Social sharing information where appropriate.
- Privacy page link.
- Minimal footer.

Suggested headline:

**AN AFFAIR OF FASHION, MUSIC AND CULTURE.**

Suggested supporting text:

Where the drip meets the rhythm. One night. One experience. An exclusive celebration of fashion, music and culture.

Do not include public invitation generation.

Do not include ticket purchasing or payment functionality.

Do not include a public form that allows people without valid invitation links to claim invitations.

When event starting time has not been configured, show the event date or a days-until-event indicator rather than inventing a precise countdown time.

After the event, show an appropriate event-ended state instead of a negative countdown.

Use Next.js metadata APIs for public SEO and social media previews.

---

# 19. Guest invitation claim page

Route:

```text
/invite/[token]
```

Create a mobile-first, beautifully designed invitation experience.

The page should include:

- Event artwork.
- Event branding.
- Exclusive invitation heading.
- Event date and location.
- Nickname input.
- Email input.
- Claim button.
- Single-use invitation notice.
- Privacy information.
- Proper form validation.
- Loading and submission states.

Suggested heading:

**YOU'RE ON THE LIST.**

Suggested description:

Enter your details to secure your exclusive invitation to DRIP & RHYTHM.

Form labels:

- Nickname
- Email address

Nickname placeholder:

```text
What do people call you?
```

Email placeholder:

```text
you@example.com
```

Primary button:

**SECURE MY INVITATION**

Use React Hook Form and Zod for client-side form validation.

Django remains responsible for authoritative validation.

Do not add unnecessary form fields.

Use attractive branded feedback states for invalid, expired, revoked, already claimed and duplicate-email situations.

Do not reveal private guest details on an already claimed invitation page.

Do not enable third-party analytics or tracking on private invitation pages.

---

# 20. Successful invitation celebration page

Route:

```text
/invitation/success
```

Create a memorable, visually impressive celebration experience.

This page should make the guest feel like they have secured access to an exclusive event.

Use:

- Cinematic reveal animation.
- Subtle confetti.
- Large expressive typography.
- Warm lighting effects.
- Personalized nickname greeting.
- Branded confirmation indicator.
- Animated promotional artwork preview.

Suggested heading:

**IT'S OFFICIAL.**

**INVITATION SECURED.**

Suggested message:

[Nickname], you're officially on the list.

The drip is ready. The rhythm is calling.

Your official admission pass is being sent to your email address.

Display email delivery information accurately.

Do not claim that an email has been delivered before the delivery provider confirms it.

Include:

- Share artwork.
- Download artwork.
- Select artwork format.
- Choose whether to include nickname.
- Copy shareable webpage link.
- Copy social media caption.
- Return to homepage.

Do not display the official admission QR code on publicly shareable artwork.

The official invitation remains a separate private document delivered by email.

---

# 21. Personalized social sharing artwork

This feature is mandatory.

Guests must be able to download and share a beautifully designed promotional graphic showing that they have secured their invitation.

It must not resemble a generic confirmation screenshot.

Design it like a premium nightlife promotional poster.

Suggested text:

**DRIP & RHYTHM**

Private Party

**IT'S OFFICIAL**

[Nickname]

**INVITATION SECURED.**

The drip is ready. The rhythm is calling.

05 DECEMBER 2026

MUYENGA · KAMPALA

An affair of fashion, music and culture.

#DripAndRhythm

Use the event's original artwork, cinematic amber lighting, decorative typography, rich gradients and recognizable branding.

Create three downloadable PNG formats.

## 21.1 Story format

- Dimensions: 1080 × 1920 pixels.
- Aspect ratio: 9:16.
- Intended for WhatsApp Status, Instagram Stories and similar platforms.

Keep important content within safe areas so that social media interface overlays do not cover essential text.

## 21.2 Square format

- Dimensions: 1080 × 1080 pixels.
- Aspect ratio: 1:1.
- Intended for social media posts.

## 21.3 Portrait format

- Dimensions: 1080 × 1350 pixels.
- Aspect ratio: 4:5.
- Intended for portrait social media posts.

Generate the artwork using Pillow and locally available branding assets and fonts.

Use dedicated layouts for each aspect ratio.

Do not merely stretch one design into three different dimensions.

Implement dynamic nickname placement.

Long nicknames must wrap or scale appropriately without clipping.

Maintain good image quality and reasonable download sizes.

Allow guests to preview their selected format before downloading.

## 21.4 Nickname visibility

Guests must be able to decide whether to include their nickname in public sharing artwork.

Default to anonymous artwork.

Provide an explicit option:

**Include my nickname on shared artwork**

Explain that enabling the option makes the nickname publicly visible on the shared image or webpage.

Only the successful claimant's limited-purpose session or another appropriately authenticated management context may change the sharing preference.

Anyone with the public sharing URL must not be able to change it.

Provide an ability to disable public sharing.

When visibility changes, regenerate affected artwork and prevent application caches from continuing to serve outdated personalized content.

Explain that already downloaded or posted images cannot be remotely removed.

## 21.5 Prohibited content

Public promotional artwork must never include:

- Guest email address.
- Official admission QR code.
- Original invitation link.
- Claim token.
- Admission token.
- Private invitation reference.
- Private venue details.
- Administrator information.

The artwork is promotional material, not an admission pass.

Include appropriate wording indicating that the official invitation is required for entry.

---

# 22. Public shareable invitation webpage

Create a separate public webpage for guests to share.

Example:

```text
/share/[token]
```

The sharing token must be entirely independent from claim and admission credentials.

Generate the sharing credential when the guest enables or creates their public sharing experience.

The public sharing webpage must display:

- DRIP & RHYTHM branding.
- Invitation Secured artwork.
- Guest nickname only when explicitly enabled.
- Public event date.
- Public location information.
- Event tagline.
- Download or share options.
- Link to the event homepage.

Example heading:

**THE INVITATION IS SECURED.**

**SEE YOU ON DECEMBER 5TH.**

The page must not allow another guest to claim an invitation.

Use Next.js server rendering and dynamic metadata to generate meaningful social sharing previews.

Implement Open Graph metadata:

- Title.
- Description.
- Absolute preview image URL.
- Appropriate image dimensions.
- Canonical sharing URL.

Generate an appropriate landscape social preview image, such as 1200 × 630 pixels, in addition to the three downloadable promotional formats.

Use public-safe information only.

Implement appropriate social preview behavior for WhatsApp and other supported platforms.

Do not guarantee that every platform will immediately refresh previously cached previews.

Keep sharing pages accessible to link-preview crawlers while discouraging general search-engine indexing.

Do not block social preview crawlers from retrieving the Open Graph image.

When an invitation is revoked:

- Disable its sharing webpage.
- Disable associated artwork endpoints.
- Display an appropriate unavailable state.
- Prevent application-controlled caches from serving active confirmation content.

Previously downloaded images or third-party cached previews cannot be remotely revoked.

## 22.1 Native social sharing

Use the Web Share API when supported.

Check browser support before invoking file sharing.

Support:

- Native mobile image sharing.
- Sharing public webpage links.
- Downloading PNG artwork.
- Copying share URLs.
- Copying prepared captions.

When native file sharing is unavailable, provide a download fallback.

Do not implement unauthorized direct posting to guests' social media accounts.

Suggested social captions:

**Invitation secured. The drip is ready, the rhythm is calling. See you on December 5th. #DripAndRhythm**

**I'm officially on the list. An affair of fashion, music and culture awaits. #DripAndRhythm**

**The invitation is secured. Now it's time to plan the drip. #DripAndRhythm**

---

# 23. Administrator dashboard

Create a modern, responsive, professionally designed administration dashboard.

The dashboard must follow the event branding while remaining clean, fast and functional.

Use a desktop sidebar and a collapsible mobile navigation system.

Suggested navigation:

- Overview.
- Invitations.
- QR Scanner.
- Check-ins.
- Administrators.
- Event Settings.
- Audit Logs.
- Profile.
- Logout.

Show navigation items according to administrator permissions.

## 23.1 Dashboard overview

Provide meaningful statistics:

- Total invitation links generated.
- Available invitation links.
- Claimed invitations.
- Expired invitations.
- Revoked invitations.
- Pending emails.
- Emails sent.
- Emails delivered.
- Failed emails.
- Guests admitted.
- Guests awaiting admission.
- Claim rate.
- Attendance rate.
- Invitation quota usage.

Use accurate database-backed statistics.

Do not display hardcoded production statistics.

Provide clearly defined calculation methods.

Claim rate should use a documented denominator.

Attendance rate should represent admitted guests relative to eligible claimed invitations.

Handle zero-value denominators gracefully.

Include quick actions:

- Generate invitation.
- Generate bulk invitations.
- View invitations.
- Open QR scanner.

Use lightweight charts only where they improve the dashboard.

## 23.2 Invitation management page

Route:

```text
/admin/invitations
```

Display invitation records with:

- Invitation reference.
- Guest nickname.
- Guest email.
- Invitation status.
- Email delivery status.
- Admission status.
- Generating administrator.
- Generated date.
- Claimed date.
- Actions.

Support:

- Search by nickname.
- Search by email.
- Search by invitation reference.
- Filter by invitation status.
- Filter by email delivery status.
- Filter by admission status.
- Filter by generating administrator.
- Date filtering.
- Sorting.
- Server-side pagination.

Available actions depend on permissions:

- View details.
- Copy unused invitation link.
- Share unused invitation link.
- Revoke invitation.
- Resend invitation.
- Correct guest information.
- View delivery attempts.
- View admission details.

Use confirmation dialogs for destructive or sensitive actions.

## 23.3 Bulk invitation generation

Create a straightforward interface containing:

- Number of links to generate.
- Optional expiration configuration.
- Remaining administrator quota.
- Remaining global quota where applicable.
- Generate button.
- Generated invitation results.

Allow administrators to copy links individually or collectively.

Never generate a partial batch silently.

If a requested batch exceeds the remaining quota, reject it clearly and display the available capacity.

## 23.4 Administrator management

Super administrators can:

- Create administrators.
- View administrators.
- Edit account information.
- Set invitation limits.
- Activate accounts.
- Deactivate accounts.
- Review invitation generation statistics per administrator.

Never display existing passwords.

Use a secure account setup or password reset mechanism.

## 23.5 Event settings

Allow the super administrator to configure:

- Event name.
- Tagline.
- Event date.
- Starting time.
- Ending time.
- Exact venue.
- Public venue visibility.
- Reservation contacts.
- Global invitation limit.
- Claim deadline.
- Invitation claiming enabled or disabled.
- Admission enabled or disabled.
- Public sharing enabled or disabled.

Protect all configuration changes using authorization and validation.

Audit important configuration changes.

---

# 24. Frontend routes

Implement the following Next.js routes.

## Public and guest routes

```text
/
/invite/[token]
/invitation/success
/share/[token]
/privacy
```

Implement a branded not-found page and appropriate error boundaries.

## Administrator routes

```text
/admin/login
/admin/forgot-password
/admin/reset-password
/admin/dashboard
/admin/invitations
/admin/invitations/[id]
/admin/scanner
/admin/check-ins
/admin/users
/admin/settings
/admin/audit-logs
/admin/profile
```

Protect administrator layouts and routes.

Unauthenticated administrators should be redirected to login.

Preserve the intended destination safely without allowing open redirects.

Frontend route protection is a usability layer. Django must independently enforce authorization on every protected API endpoint.

Avoid conflicts between Next.js administrator routes and Django's built-in administration site.

If the built-in Django administration site is retained, restrict it appropriately and use a separate route.

---

# 25. REST API specification

Implement a documented and consistently structured REST API.

Use `/api/` as the base path.

## Authentication

```text
GET   /api/auth/csrf/
POST  /api/auth/login/
POST  /api/auth/logout/
GET   /api/auth/me/
POST  /api/auth/password/change/
POST  /api/auth/password/forgot/
POST  /api/auth/password/reset/
```

## Event

```text
GET   /api/event/public/
GET   /api/event/settings/
PATCH /api/event/settings/
```

## Administrators

```text
GET   /api/users/
POST  /api/users/
GET   /api/users/{id}/
PATCH /api/users/{id}/
POST  /api/users/{id}/activate/
POST  /api/users/{id}/deactivate/
```

## Invitation management

```text
GET   /api/invitations/
POST  /api/invitations/
POST  /api/invitations/bulk/
GET   /api/invitations/{id}/
POST  /api/invitations/{id}/revoke/
POST  /api/invitations/{id}/resend/
POST  /api/invitations/{id}/correct-guest/
GET   /api/invitations/{id}/deliveries/
GET   /api/invitations/{id}/claim-link/
GET   /api/invitations/export/
```

## Guest invitation claiming

```text
GET   /api/invite/{token}/
POST  /api/invite/{token}/claim/
GET   /api/claim-receipt/
```

Claim request body:

```json
{
  "nickname": "The Vibe",
  "email": "guest@example.com"
}
```

## Social sharing

```text
GET   /api/claim-receipt/sharing/
POST  /api/claim-receipt/sharing/
PATCH /api/claim-receipt/sharing/
GET   /api/share/{token}/
GET   /api/share/{token}/image/
```

Supported artwork format parameters:

```text
story
square
portrait
preview
```

Use explicit authorization for changing sharing preferences.

The public sharing token provides read-only access to public promotional content.

## Verification and check-in

```text
POST  /api/verify/
POST  /api/verify/manual/
POST  /api/check-in/
GET   /api/check-ins/
GET   /api/check-ins/export/
```

## Dashboard and audit

```text
GET   /api/dashboard/
GET   /api/audit-logs/
```

## Communications

```text
POST  /api/webhooks/resend/
```

## Health and documentation

```text
GET   /api/health/
GET   /api/schema/
GET   /api/docs/
```

Restrict detailed API documentation appropriately in production.

Use consistent serializers and validation.

Return meaningful HTTP status codes and machine-readable error identifiers.

Suggested identifiers:

```text
INVALID_INVITATION
INVITATION_ALREADY_CLAIMED
INVITATION_EXPIRED
INVITATION_REVOKED
DUPLICATE_EMAIL
INVITATION_LIMIT_REACHED
INVALID_QR_CODE
ALREADY_ADMITTED
ADMISSION_DISABLED
CLAIMING_DISABLED
PERMISSION_DENIED
RATE_LIMITED
VALIDATION_ERROR
SHARING_UNAVAILABLE
```

Document request bodies, response schemas, permissions and failure cases.

Generate OpenAPI documentation using drf-spectacular.

Keep frontend types aligned with the API contract.

---

# 26. Visual design system

The supplied DRIP & RHYTHM event poster is the primary visual reference.

Analyze the poster's:

- Colour palette.
- Typography.
- Fashion imagery.
- Composition.
- Lighting.
- Textures.
- Graphic hierarchy.
- Organizer logos.
- Overall atmosphere.

The desired design style is:

**Luxury Afrocentric nightlife combined with warm cinematic lighting, retro glamour, high-end fashion editorial aesthetics and exclusive private-party branding.**

The website must feel custom-designed specifically for DRIP & RHYTHM.

Avoid generic AI-generated website aesthetics.

## 26.1 Colour palette

Use the following design tokens as initial values:

| Colour | Hex |
|---|---|
| Burnt orange | #E85D19 |
| Sunset orange | #FF8C32 |
| Golden amber | #FFBE55 |
| Dark chocolate | #421509 |
| Midnight brown | #190D08 |
| Champagne gold | #F5CE86 |
| Warm ivory | #FFF3E0 |
| Deep red | #A51B12 |

These colours are approximate interpretations of the poster.

Refine them when appropriate after examining the original artwork.

Use semantic tokens for:

- Background.
- Foreground.
- Primary.
- Secondary.
- Accent.
- Muted.
- Border.
- Success.
- Warning.
- Error.
- Input.
- Focus ring.

Maintain sufficient text contrast.

Use accessible success and error indicators, not colour alone.

## 26.2 Typography

Use the following fonts:

### Anton

For:

- Major headings.
- Event title.
- Promotional artwork.
- Invitation Secured typography.
- Bold editorial statements.

### WindSong

For:

- Decorative script headings.
- Private Party subtitle.
- Elegant visual accents.

### Montserrat

For:

- Body text.
- Forms.
- Buttons.
- Navigation.
- Administration dashboard.
- Supporting information.

These are visual alternatives to the poster fonts, not confirmed original typefaces.

Use locally hosted font assets or an appropriate Next.js font-loading strategy that does not require runtime third-party font requests.

Store applicable font licenses in the repository.

Use the same typography across the website, PDF templates and social artwork where technically appropriate.

Provide fallback fonts for Unicode nicknames.

Do not use decorative script typography for critical functional text.

## 26.3 Visual styling

Use:

- Warm amber glows.
- Burnt orange gradients.
- Deep chocolate backgrounds.
- Subtle film grain.
- Cinematic light effects.
- Large condensed typography.
- Fashion-editorial compositions.
- Generous spacing.
- Elegant decorative lines.
- Strong visual hierarchy.
- Responsive layouts.

Avoid:

- Generic blue and purple SaaS gradients.
- Excessive glassmorphism.
- Random stock photography.
- Unrelated illustrations.
- Excessive rounded cards.
- Excessive shadows.
- Excessive visual effects.
- Generic template designs.
- Unnecessary decorative icons.
- Overcrowded layouts.

Use the supplied poster without stretching, distorting or cropping important information.

If separate background artwork or transparent organizer logos are unavailable, use the supplied poster appropriately and document the missing assets.

Do not fabricate organizer logos.

## 26.4 Animations and installed design skills

Use the four already-installed project-level design skills under `.agents/skills/` selectively by phase and responsibility (`frontend-design` for architecture/UI/components, `design-taste-frontend` for editorial creative direction adapted to the DRIP & RHYTHM palette/fonts, `scroll-craft` selectively on the public homepage `/`, and `impeccable` for targeted critique and visual QA). Project requirements, security controls, and the approved visual identity always take precedence over generic skill defaults.

Use Motion and native CSS for:

- Page entry transitions.
- Hero typography reveals and restrained scroll-linked transitions on the public homepage.
- Form appearance and microinteractions.
- Button interactions.
- Success-state transitions.
- Artwork preview transitions.
- Subtle background movement.

Do not implement scroll hijacking, do not block navigation or forms on animation completion, and do not add complex scroll-driven animations in guest claim forms, administrator login, dashboard tables, invitation management, QR scanner, or check-in workflows. Do not introduce GSAP, Lenis, Three.js, WebGL, or other heavy animation libraries without explicit approval.

Use lightweight confetti only during the successful claim celebration.

Respect `prefers-reduced-motion`.

Do not let animations interfere with forms, scanning, accessibility or page performance.

Do not autoplay music.

---

# 27. Responsive design and accessibility

Prioritize mobile users because most guests will receive invitation links through WhatsApp and other mobile applications.

Verify layouts at representative widths:

```text
320px
360px
375px
390px
414px
768px
1024px
1440px
1920px
```

Ensure:

- No unintended horizontal scrolling.
- Readable typography.
- Appropriate touch target sizes.
- Correct keyboard behavior.
- Accessible form labels.
- Visible focus indicators.
- Accessible dialogs.
- Proper semantic headings.
- Sufficient colour contrast.
- Screen-reader-compatible feedback.
- Reduced-motion support.
- Correct image aspect ratios.
- Responsive tables and dashboard navigation.

Pay particular attention to Android mobile browsers and WhatsApp in-app browsers.

Use progressive enhancement for camera scanning and social sharing.

Provide practical fallbacks when browser capabilities are unavailable.

---

# 28. Security and privacy

Security is mandatory throughout the application.

Implement:

- Cryptographically secure tokens.
- Separate token purposes.
- Token digest storage.
- Authenticated encryption for credentials that require recovery.
- Secure administrator authentication.
- Password hashing.
- Session security.
- CSRF protection.
- Server-side authorization.
- Brute-force protection.
- Rate limiting.
- Atomic invitation claims.
- Atomic invitation generation.
- Atomic guest admissions.
- Database uniqueness constraints.
- Input validation.
- HTML escaping.
- Protection against SQL injection.
- Protection against XSS.
- Protection against open redirects.
- Secure webhook signature validation.
- Safe error messages.
- Secret redaction.
- Appropriate HTTP security headers.
- HTTPS enforcement in production.
- Trusted host and proxy configuration.
- Sensitive response cache prevention.
- Appropriate referrer policies.
- Search engine indexing restrictions.
- Minimal personal data collection.

Use rate limiting that remains effective across multiple processes.

Do not rely exclusively on in-memory request counters.

Avoid introducing Redis solely for rate limiting; use a suitable database-backed or infrastructure-level mechanism.

Never log complete private invitation URLs, admission credentials or password reset tokens.

Sanitize application and infrastructure request logging where tokenized URLs are involved.

Do not expose private API responses through Next.js hydration data, static generation or shared caches.

Do not expose secrets using `NEXT_PUBLIC_` variables.

Do not trust arbitrary forwarded host or IP headers supplied by external clients.

Protect CSV exports against spreadsheet formula injection.

Create a concise privacy page explaining:

- What guest information is collected.
- Why the information is collected.
- How invitations are delivered.
- How admission verification works.
- Optional public nickname visibility.
- How guests can request assistance or data removal.
- Data retention practices.

Provide a documented post-event data retention and deletion procedure requiring explicit administrator authorization.

Do not automatically delete production data.

Document that email uniqueness is not identity verification. Guests can possess multiple email addresses, and unused claim links or admission passes can be forwarded. The system prevents repeated claims and admissions, not all forms of identity substitution.

---

# 29. Error handling

Handle all expected failure cases.

Required scenarios:

- Invalid invitation token.
- Expired invitation.
- Revoked invitation.
- Previously claimed link.
- Duplicate email address.
- Invalid email format.
- Empty nickname.
- Excessively long nickname.
- Unsafe nickname characters.
- Simultaneous claims.
- Simultaneous duplicate-email submissions.
- Invitation quota exceeded.
- Invalid bulk quantity.
- Email provider unavailable.
- Email bounced.
- Interrupted email processing.
- Duplicate webhook event.
- Database failure.
- Network connection loss.
- Expired administrator session.
- Unauthorized administrator action.
- Camera permission denied.
- Camera unavailable.
- Unsupported QR scanner capabilities.
- Invalid QR payload.
- Already admitted guest.
- Simultaneous check-in attempts.
- Revoked sharing webpage.
- Unsupported native social sharing.
- Missing branding assets.
- Missing event time.
- Missing exact venue.

Display meaningful user-friendly error messages.

Do not expose stack traces, internal database errors or sensitive diagnostic information to public users.

Maintain detailed but sanitized server-side diagnostics.

---

# 30. Testing requirements

Implement comprehensive automated tests.

## Backend tools

- pytest.
- pytest-django.
- Django REST Framework APIClient.
- PostgreSQL integration tests.

## Frontend tools

- Vitest.
- React Testing Library.
- Playwright.
- TypeScript type checking.
- ESLint.
- Prettier.

## Python quality

- Ruff.
- Appropriate formatting.
- Clear type annotations where beneficial.

## Required backend tests

Test:

1. Super administrator authentication.
2. Ordinary administrator authentication.
3. Invalid login credentials.
4. Account deactivation.
5. Password reset.
6. Role-based permissions.
7. Individual link generation.
8. Bulk link generation.
9. Global invitation quotas.
10. Per-administrator invitation quotas.
11. Concurrent quota enforcement.
12. Valid invitation claiming.
13. Invalid invitation claiming.
14. Duplicate email prevention.
15. Case-insensitive email uniqueness.
16. Duplicate nickname acceptance.
17. Concurrent claims of the same link.
18. Concurrent claims using the same email.
19. Duplicate-email rejection without consuming a link.
20. Expired invitation behavior.
21. Revocation.
22. Email job creation.
23. Email delivery failure.
24. Automatic retry behavior.
25. Interrupted worker recovery.
26. Administrator-controlled resending.
27. Webhook authentication.
28. Duplicate webhook handling.
29. PDF generation.
30. QR readability from generated PDF.
31. Unique QR credentials.
32. Valid QR verification.
33. Invalid QR verification.
34. Single-use admission.
35. Concurrent admission attempts.
36. Manual verification.
37. Guest information correction.
38. Previous QR invalidation.
39. Social sharing credential isolation.
40. Public nickname opt-in.
41. Public nickname removal.
42. Sharing revocation.
43. PNG generation in all required dimensions.
44. Public information exposure restrictions.
45. CSV export permissions.
46. CSV formula-injection protection.
47. CSRF enforcement.
48. Audit logging.
49. API response consistency.
50. Session and caching security.

Use actual PostgreSQL for critical concurrency tests.

Do not assume SQLite reproduces PostgreSQL transaction and locking behavior.

## Required frontend tests

Test:

- Public homepage.
- Invitation claim form.
- Input validation.
- Successful claim.
- Duplicate-email feedback.
- Expired invitation feedback.
- Already-claimed invitation feedback.
- Social artwork format selection.
- Nickname visibility control.
- Artwork download.
- Native sharing fallbacks.
- Admin authentication.
- Protected routes.
- Dashboard statistics.
- Invitation generation.
- Bulk generation.
- Invitation filters.
- QR verification interface.
- Check-in confirmation.
- Permission-dependent actions.
- Responsive navigation.
- Accessible forms.
- Error and loading states.

Mock external services where appropriate for automated testing, but clearly distinguish mocked verification from real external-service verification.

---

# 31. Browser-based visual verification

Use Antigravity's browser capabilities to inspect the actual running application.

Do not consider a design complete merely because frontend code compiles.

Inspect:

- Desktop homepage.
- Mobile homepage.
- Guest invitation claim page.
- Successful invitation page.
- Invalid invitation states.
- Duplicate-email state.
- Personalized sharing page.
- Administrator login.
- Dashboard.
- Invitation table.
- QR scanner interface.
- Event settings.
- Promotional artwork downloads.

Capture representative screenshots as reviewable artifacts.

Inspect spacing, typography, image fitting, colour contrast, margins, padding, alignment and visual hierarchy.

Fix all obvious visual problems before finalizing the implementation.

Use the supplied event poster to evaluate branding consistency.

Ensure the public website looks professionally designed and distinctive rather than like a generic dashboard template.

Test camera workflows with appropriate browser simulation where possible and document any physical-device verification still required.

---

# 32. Environment configuration

Provide complete environment variable examples.

Suggested backend variables:

```dotenv
DJANGO_SECRET_KEY=
DJANGO_DEBUG=
DJANGO_ALLOWED_HOSTS=
DJANGO_CSRF_TRUSTED_ORIGINS=
DATABASE_URL=
APP_BASE_URL=
DJANGO_TIME_ZONE=Africa/Kampala
TOKEN_ENCRYPTION_KEY=
CLAIM_RECEIPT_TTL_DAYS=
RESEND_API_KEY=
RESEND_FROM_EMAIL=
RESEND_FROM_NAME=
RESEND_REPLY_TO_EMAIL=
RESEND_WEBHOOK_SECRET=
EMAIL_MAX_RETRIES=
EMAIL_WORKER_POLL_INTERVAL=
EMAIL_WORKER_LEASE_SECONDS=
```

Suggested frontend variables:

```dotenv
NEXT_PUBLIC_SITE_URL=
DJANGO_INTERNAL_API_URL=
```

Adjust the environment configuration according to actual implementation requirements.

Validate mandatory production configuration at startup.

Never commit real secrets.

Provide safe local development settings.

Document exactly how each service loads its environment variables (including the worker), with separate backend and frontend example files if appropriate. For local development, use a PostgreSQL connection such as `postgresql://drip_app:LOCAL_PASSWORD@127.0.0.1:5432/drip_and_rhythm`, `APP_BASE_URL=http://localhost:3000`, `NEXT_PUBLIC_SITE_URL=http://localhost:3000` and `DJANGO_INTERNAL_API_URL=http://127.0.0.1:8000`. Treat these as examples, never production credentials. Use a dedicated non-superuser database role; use a separate test database or test-only role with the permissions required by pytest-django. Keep actual environment files and `.venv/` out of version control.

Provide an email development backend that allows testing without sending actual emails.

Make it possible to generate and inspect sample PDFs and sharing artwork locally.

Do not confuse local email simulation with successful production email delivery.

---

# 33. Deployment

Prepare the application for native deployment on Render.

## 33.1 Native local development setup

Provide and verify Windows PowerShell instructions as the primary local development guide, with macOS/Linux equivalents where practical.

Use the already-installed local runtimes (Python `3.15.0`, Node.js `26.13.0`, npm `11.20.0`, Git `2.56.0`, and PostgreSQL `18.7` running on `localhost:5432`). Configure the dedicated `drip_and_rhythm` database, non-superuser `drip_app` role, and isolated `drip_test` test role/database without weakening PowerShell execution policy or exposing the `postgres` administrator password in conversation, code, or logs.

From the repository root, the documented Windows commands should follow this pattern (adapt to the verified Python 3.15 path and environment loader):

```powershell
cd backend
py -3.15 -m venv .venv
# Or, when WindowsApps aliases precede Python in PATH:
# & 'C:\Users\LENOVO\AppData\Local\Python\pythoncore-3.15-64\python.exe' -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

If the project implements a custom initial-admin or event initialization command, document its actual invocation and any required seed configuration. Do not seed hardcoded production credentials.

In a second terminal, from the repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py process_email_jobs
```

In a third terminal, from the repository root (using `npm.cmd` on Windows PowerShell when `npm.ps1` is restricted):

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

The public local application should open at `http://localhost:3000`. Keep PostgreSQL 18.7 running independently. The direct virtual-environment interpreter and `npm.cmd` commands above avoid requiring changes to PowerShell execution policy.

For macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` (or activate the virtual environment) with equivalent commands.

Document native migration, administrator creation, linting, type checking, automated testing, Playwright browser installation, production build and clean shutdown commands. Test with local PostgreSQL, not SQLite, for transaction and concurrency guarantees.

## 33.2 Native Render services

Provide:

- A complete `render.yaml` Blueprint with explicit native runtimes and service root directories.
- Public Next.js web service: Node.js runtime; install from the committed lockfile, build with `npm ci && npm run build`, and start with `npm run start` using Render's assigned `PORT` and binding to `0.0.0.0` as required.
- Django API: Python runtime, preferably a private service where supported; install pinned requirements, collect static files where needed, and run `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` (adjust the WSGI module to the actual implementation).
- Email worker: native Python background worker using the same backend root and dependencies, started with `python manage.py process_email_jobs`; keep it running continuously with restart and graceful shutdown support.
- Managed PostgreSQL, with shared database configuration for the API and worker.
- A documented migration step, using a supported pre-deploy command where available or an authorized one-off migration before activating updated services. Do not run conflicting migrations independently in every process.
- Pinned runtime versions and dependency lockfiles.
- Render environment variable and secret mapping, including an internal Django API URL accessible to Next.js.
- A documented service count and plan requirements, including any paid private service, worker or database requirements. Do not assume the entire topology can run free of charge.
- Native deployment verification and rollback instructions.
- Health checks.
- Production environment instructions.
- Database migration instructions.
- Static asset configuration.
- Domain configuration instructions.
- Resend sender-domain verification instructions.
- Database backup instructions.
- Recovery instructions.

Use a production Next.js runtime with support for server rendering and dynamic metadata.

Do not use a static-only Next.js export because dynamic invitation routes and public sharing pages require runtime behavior.

Use Gunicorn for the production Django application.

Use a single public application domain.

Keep PostgreSQL and internal services private where supported.

Ensure the email webhook endpoint remains reachable through the approved public application route.

Ensure HTTPS is enabled.

Do not automatically deploy, provision paid services or purchase domains.

Do not automatically push code to GitHub.

Wait for explicit authorization before external deployment actions.

## 33.3 Native continuous integration

Configure GitHub Actions to install the pinned Python and Node.js versions on a hosted runner, install Python dependencies and use `npm ci`, and run linting, type checking, tests and the Next.js production build.

Use a Linux runner with PostgreSQL installed and started natively (for example, through the runner's package manager and PostgreSQL service tools). Create an isolated test database and test-only credentials. Do not use container-based CI jobs or PostgreSQL service containers.

Run the Django migrations and actual PostgreSQL concurrency tests. Install Playwright's required browsers and operating-system dependencies natively. Keep production secrets out of CI test jobs.

Validate the native production start commands and service configuration locally or in an authorized staging environment, and document anything that remains unverified. A successful local build alone is not proof of a successful Render deployment.

---

# 34. Documentation and required deliverables

Produce the following working deliverables:

- Complete Django backend.
- Complete Next.js frontend.
- PostgreSQL database models.
- Database migrations.
- Administrator authentication system.
- Invitation link management.
- Duplicate prevention system.
- PDF invitation generation.
- QR generation and scanning.
- Admission management.
- Resend integration.
- Email processing worker.
- Branded HTML email templates.
- Three downloadable social artwork formats.
- Open Graph preview artwork.
- Public sharing webpages.
- Responsive public website.
- Administrator dashboard.
- API documentation.
- Automated tests.
- Native Python virtual-environment and npm setup, pinned dependencies and lockfiles.
- Native Render deployment configuration (`render.yaml`).
- Separate native email worker startup and supervision instructions.
- GitHub Actions workflows.
- Environment variable examples.

Create documentation files:

## README.md

Include:

- Project overview.
- Technology stack.
- Native local development setup, with Windows PowerShell and macOS/Linux commands.
- Python virtual-environment creation and pinned dependency installation.
- npm lockfile installation.
- Local PostgreSQL installation, database and role setup.
- Migration commands.
- Initial administrator creation.
- Frontend startup.
- Backend startup.
- Email worker startup.
- Testing commands.

## AGENTS.md

Include:

- Persistent project requirements.
- Architecture decisions.
- Coding standards.
- Security requirements.
- Testing requirements.
- Explicitly excluded features.
- Development restrictions.
- Instructions to avoid unnecessary changes.

## IMPLEMENTATION.md

Maintain:

- Completed functionality.
- Remaining functionality.
- Implementation decisions.
- Testing results.
- Known issues.
- Unverified external integrations.
- Production configuration requirements.

## DEPLOYMENT.md

Include complete native production setup and deployment instructions for the Next.js web service, Django API, PostgreSQL and separate Python email worker. Document environment variables, builds, start commands, migrations, health checks, service plan requirements, backup and rollback procedures.

## SECURITY.md

Include:

- Authentication design.
- Authorization design.
- Token security.
- Database constraints.
- Privacy controls.
- Known security limitations.
- Credential rotation instructions.
- Data retention instructions.
- Incident recovery guidance.

Create additional architecture, requirements and design-system documentation under the `docs/` directory.

---

# 35. Implementation phases

Follow the following development order.

## Phase 1 — Planning and project foundation

- Verify already-installed local runtimes (Python 3.15.0, Node.js 26.13.0, npm 11.20.0, PostgreSQL 18.7, Git 2.56.0) and project-level design skills.
- Resolve and import-verify mutually compatible stable dependency versions (including Windows Python 3.15 binary wheels).
- Create the `backend/.venv` virtual environment and pin reproducible dependency lockfiles.
- Configure the dedicated PostgreSQL 18.7 development (`drip_and_rhythm`, `drip_app`) and test (`drip_test`) databases safely.
- Initialize the local Git repository and `.gitignore`.
- Create backend and frontend project foundations, development settings, testing/linting, and core documentation.

## Phase 2 — Backend foundation

- Custom user model.
- Authentication.
- Administrator roles.
- Event configuration.
- Database models.
- Database migrations.
- Authorization system.
- Audit logging.

## Phase 3 — Invitation engine

- Individual generation.
- Bulk generation.
- Invitation limits.
- Token management.
- Claiming workflow.
- Duplicate email prevention.
- Expiration.
- Revocation.
- Concurrency protection.

## Phase 4 — PDF and email delivery

- Branded PDF templates.
- Font integration.
- QR code generation.
- Email templates.
- Resend integration.
- Database-backed worker.
- Retry handling.
- Email delivery tracking.
- Webhook integration.

## Phase 5 — Verification and admission

- QR verification API.
- Manual verification.
- Admission transactions.
- Duplicate check-in prevention.
- Check-in history.

## Phase 6 — Public frontend

- Design system.
- Public homepage.
- Event branding.
- Invitation claim page.
- Loading and error states.
- Success celebration page.

## Phase 7 — Social sharing

- Personalized artwork generation.
- Story format.
- Square format.
- Portrait format.
- Nickname privacy control.
- Download functionality.
- Native sharing.
- Public sharing webpage.
- Open Graph metadata.

## Phase 8 — Administrator frontend

- Authentication pages.
- Dashboard.
- Invitation management.
- Bulk generation.
- Administrator management.
- QR scanner.
- Check-in records.
- Event settings.
- Audit logs.

## Phase 9 — Testing and security

- Unit tests.
- Integration tests.
- PostgreSQL concurrency tests.
- End-to-end tests.
- Permission tests.
- QR readability tests.
- Privacy tests.
- Browser visual verification.
- Mobile responsiveness.
- Security review.

## Phase 10 — Production preparation

- Verify current Render native runtime support (Python, Node.js, managed PostgreSQL) and document/test any local-vs-production runtime differences before deployment.
- Verify native Next.js production build and start commands.
- Verify Django Gunicorn startup in a supported Linux environment and native email worker startup.
- Verify pinned dependency installation, database migrations, same-origin API proxy, HTTPS, email/webhook handling, and native CI.
- Finalize `render.yaml` Blueprint and production environment configuration.
- Complete deployment, security, and operational documentation.
- Final implementation review and production readiness report (without automatic deployment or provisioning).

Complete related work together to avoid repeatedly changing the same files.

Run relevant tests after each major phase.

Resolve identified failures before marking a phase complete.

---

# 36. Explicitly excluded features

Do not implement the following:

- Public user registration.
- Guest login accounts.
- Full legal name collection.
- Phone number collection.
- Guest OTP verification.
- Ticket purchasing.
- Payments.
- Subscription systems.
- Multiple-event management interface.
- Public invitation generation.
- SMS integration.
- WhatsApp Business API integration.
- Automatic social media posting.
- Redis.
- Celery.
- Firebase.
- Supabase.
- External PDF storage.
- Cloudflare R2.
- AWS S3.
- Kubernetes.
- Microservices.
- WebSockets.
- Native mobile applications.
- Offline admission synchronization.
- Unrequested artificial intelligence features.
- Container-based development, CI or deployment, and alternative containerization technologies.

Do not introduce additional infrastructure unless a genuine requirement cannot be fulfilled using the agreed stack. Document the reason before changing the architecture.

---

# 37. Developer execution rules

Throughout development:

1. Follow this specification.
2. Build actual working functionality.
3. Maintain clean, readable code.
4. Keep dependencies minimal.
5. Avoid unnecessary architectural abstractions.
6. Reuse existing components and services.
7. Do not repeatedly rebuild completed functionality.
8. Minimize unnecessary agent calls and credit usage.
9. Do not introduce unrelated changes.
10. Do not use hardcoded secrets.
11. Do not use fake production statistics.
12. Do not leave essential functionality as placeholders.
13. Do not silently disable security checks.
14. Do not remove failing tests to obtain a passing result.
15. Do not claim functionality has been tested without actually testing it.
16. Do not claim external services have been verified using mocked responses.
17. Do not invent event information or branding assets.
18. Do not delete unrelated workspace files.
19. Do not access files outside the project unnecessarily.
20. Do not push to GitHub without authorization.
21. Do not deploy without authorization.
22. Do not purchase or provision paid services without authorization.
23. Document important implementation decisions.
24. Keep the project implementation checklist updated.
25. Use browser verification to validate the visual experience.

Use targeted fixes when issues are identified rather than rewriting entire working modules.

---

# 38. Final acceptance criteria

The application is functionally complete only when all the following conditions are satisfied:

- The public homepage accurately represents DRIP & RHYTHM.
- The visual design matches the supplied event poster.
- Authorized administrators can log in.
- Unauthorized users cannot access administrative functionality.
- Super administrators can manage administrator accounts.
- Administrators can generate individual and bulk invitation links.
- Global and individual invitation quotas are enforced.
- All administrators can view all invitation records.
- Only authorized administrators can perform sensitive management actions.
- Guests can claim valid invitations using nickname and email.
- Duplicate nicknames are accepted.
- Duplicate emails are rejected.
- Duplicate-email attempts do not consume unused links.
- Opening invitation URLs does not consume them.
- Simultaneous claims cannot create duplicates.
- Expired and revoked invitations cannot be claimed.
- Successful claims consume invitation links permanently.
- Personalized PDFs are generated correctly.
- QR codes can be decoded from generated PDFs.
- Email jobs are processed reliably.
- Failed email deliveries can be retried.
- Administrator resends do not create new invitations.
- Guest corrections invalidate old admission credentials where required.
- Guests receive a branded successful claim experience.
- Story, square and portrait artwork downloads work.
- Guests can choose whether their nickname is displayed publicly.
- Social sharing webpages contain no private admission credentials.
- Social previews use appropriate branded metadata.
- Revoked sharing pages become unavailable.
- Administrators can scan valid QR codes.
- Verification does not automatically admit guests.
- Explicit guest admission works.
- Duplicate admissions are prevented.
- Concurrent check-ins cannot admit a guest twice.
- Manual verification works.
- Administrator statistics are accurate.
- Audit logging works.
- CSV export permissions are enforced.
- All critical pages are responsive.
- Loading and error states are implemented.
- Automated tests pass.
- Production builds succeed.
- Database migrations succeed.
- Native development setup works with a Python virtual environment, npm and locally installed PostgreSQL.
- Pinned dependencies and lockfiles support reproducible installation.
- The separate native Python email worker starts and processes test jobs successfully.
- Native CI runs the required checks against actual PostgreSQL.
- Native Render service configuration and start commands are complete and verified to the extent possible without production credentials.
- Deployment documentation is complete.
- Security documentation is complete.
- Missing production credentials are clearly documented.
- Any unverified live integrations are clearly identified.

---

# 39. Final development report

After completing implementation, produce a concise but comprehensive report containing:

1. Project implementation summary.
2. Architecture overview.
3. Completed backend features.
4. Completed frontend features.
5. Screenshots of key pages.
6. PDF invitation sample.
7. Social artwork samples in all three formats.
8. Automated test results.
9. PostgreSQL concurrency test results.
10. Security verification results.
11. Frontend production build results.
12. Database migration results.
13. Native runtime verification results (dependency installation, Next.js build/start, Django Gunicorn startup where supported, PostgreSQL connectivity, email worker startup and CI checks).
14. Known limitations.
15. Pending external configuration.
16. Exact local development commands.
17. Deployment instructions.
18. Remaining manual verification requirements.

Clearly distinguish implemented, locally verified, externally verified and pending functionality.

Do not report that the application is fully production-ready until the actual production configuration, email sender verification, live email delivery, database connectivity, HTTPS, and physical-device QR scanning have been appropriately verified.

---

# 40. Begin development

Start by inspecting the project workspace and the supplied DRIP & RHYTHM event poster.

Create a comprehensive implementation plan covering the entire specification.

Prepare the persistent workspace rules and project documentation.

Present the proposed architecture, implementation phases, technical decisions, security strategy and any genuine blockers.

After implementation-plan approval, proceed through the development phases systematically.

The final result must be a secure, lightweight, premium-looking, fully functional invitation management application with a memorable guest experience.

The application must preserve the exclusivity and visual identity of DRIP & RHYTHM.

**One link. One email. One invitation. One admission.**

Build accordingly.