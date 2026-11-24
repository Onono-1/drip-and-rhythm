# DRIP & RHYTHM — Private Party Invitation Management System

Controlled, single-event invitation management platform for **DRIP & RHYTHM** (**After Dark Events × Hype District** · `5 December 2026` · Muyenga, Kampala, Uganda · `Africa/Kampala` · `18+`).

**Core Invariant**: **One link. One email. One invitation. One admission.**

---

## 1. Architecture & Verified Stack (Native Runtimes Only)

Docker and containerization are strictly excluded across development, CI, and production.

- **Frontend**: Next.js 16 (App Router, SSR, dynamic metadata, narrow `/api/*` same-origin proxy), React 19, TypeScript, Tailwind CSS v4, Motion, TanStack Query, React Hook Form + Zod, `@zxing/browser`, `canvas-confetti`.
- **Backend**: Python `3.15.0` (`backend/.venv`), Django `6.1.3`, Django REST Framework `3.18.3`, `psycopg[binary] 3.3.9`, `drf-spectacular 0.30.0`, ReportLab `5.1.0`, `qrcode 8.2`, Pillow `13.0.0`, `cryptography 50.0.2`, Resend SDK `2.55.0` + Svix `2.11.1`, Gunicorn `27.0.1` (Linux production only).
- **Database**: Native PostgreSQL `18.7` (`localhost:5432`), dedicated database `drip_and_rhythm` with least-privilege runtime role `drip_app` and isolated test database `drip_and_rhythm_test` (`drip_test`).
- **Email Worker**: Separate native Python process (`python manage.py process_email_jobs`).

---

## 2. Native Local Setup (Windows PowerShell)

### Step 1 — Provision PostgreSQL Databases & `.env` Files
Run the interactive setup script (prompts privately for your `postgres` administrator password via Windows Credential UI or `getpass`, creates `drip_app`, `drip_test`, `drip_and_rhythm`, and `drip_and_rhythm_test`, and writes gitignored `backend/.env` and `frontend/.env`):

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\setup_local_db.py
```

*(If creating `backend/.venv` on a fresh clone: `& "C:\Users\LENOVO\AppData\Local\Python\pythoncore-3.15-64\python.exe" -m venv backend\.venv` then `.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt`.)*

### Step 2 — Run Migrations & Create Initial Super Administrator
```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_event
.\.venv\Scripts\python.exe manage.py create_initial_superadmin
```

### Step 3 — Start the Three Native Local Processes

**Terminal 1 — Django API (`http://127.0.0.1:8000`)**:
```powershell
cd backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

**Terminal 2 — Background Email Worker**:
```powershell
cd backend
.\.venv\Scripts\python.exe manage.py process_email_jobs
```
*(In local mode `EMAIL_DELIVERY_MODE=local`, generated HTML/text emails and attached VIP PDF passes are written to `backend/var/dev_emails/<job_id>/`.)*

**Terminal 3 — Next.js Public & Admin Web App (`http://localhost:3000`)**:
```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:3000` (all browser `/api/*` requests proxy through Next.js to Django on `127.0.0.1:8000`).

### macOS / Linux Equivalents
Use `python3.15 -m venv backend/.venv`, `backend/.venv/bin/python`, and `npm ci` / `npm run dev`.

---

## 3. Verification & Testing Commands

```powershell
# Backend lint & real PostgreSQL integration/concurrency tests
cd backend
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\pytest.exe --create-db

# Frontend strict typecheck, lint, unit tests, and production build
cd ..\frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```

See [DEPLOYMENT.md](file:///c:/Users/LENOVO/Desktop/drip-and-rhythm/DEPLOYMENT.md), [SECURITY.md](file:///c:/Users/LENOVO/Desktop/drip-and-rhythm/SECURITY.md), and [docs/API.md](file:///c:/Users/LENOVO/Desktop/drip-and-rhythm/docs/API.md) for deployment, security controls, and endpoint specifications.
