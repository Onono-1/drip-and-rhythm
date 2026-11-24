from __future__ import annotations

import base64
import ctypes
import getpass
import os
import secrets
import shutil
import string
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def find_psql() -> str:
    default_win = Path(r"C:\Program Files\PostgreSQL\18\bin\psql.exe")
    if default_win.exists():
        return str(default_win)
    found = shutil.which("psql")
    if found:
        return found
    raise FileNotFoundError("Could not locate psql executable.")


def safe_secret(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class CREDUI_INFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hwndParent", wintypes.HANDLE),
        ("pszMessageText", wintypes.LPCWSTR),
        ("pszCaptionText", wintypes.LPCWSTR),
        ("hbmBanner", wintypes.HBITMAP),
    ]


def prompt_windows_credui() -> str | None:
    if os.name != "nt":
        return None
    try:
        credui = ctypes.windll.credui
        info = CREDUI_INFO()
        info.cbSize = ctypes.sizeof(CREDUI_INFO)
        info.hwndParent = ctypes.windll.user32.GetForegroundWindow()
        info.pszMessageText = (
            "Enter your local PostgreSQL 'postgres' password to create the "
            "drip_and_rhythm databases and least-privilege roles."
        )
        info.pszCaptionText = "DRIP & RHYTHM — Local PostgreSQL 18.7 Setup"

        user_buf = ctypes.create_unicode_buffer("postgres", 128)
        pw_buf = ctypes.create_unicode_buffer(256)
        save = wintypes.BOOL(False)
        # CREDUI_FLAGS_GENERIC_CREDENTIALS (0x40000) | CREDUI_FLAGS_ALWAYS_SHOW_UI (0x80) | CREDUI_FLAGS_DO_NOT_PERSIST (0x2)
        flags = 0x40000 | 0x80 | 0x2
        rc = credui.CredUIPromptForCredentialsW(
            ctypes.byref(info),
            "localhost:5432",
            None,
            0,
            user_buf,
            128,
            pw_buf,
            256,
            ctypes.byref(save),
            flags,
        )
        if rc == 0 and pw_buf.value:
            val = pw_buf.value
            ctypes.memset(pw_buf, 0, ctypes.sizeof(pw_buf))
            return val
    except Exception:
        return None
    return None


def get_postgres_admin_password() -> str:
    env_pw = os.getenv("PGADMIN_SETUP_PASSWORD", "")
    if env_pw:
        return env_pw
    if sys.stdin and sys.stdin.isatty():
        return getpass.getpass("PostgreSQL 'postgres' administrator password: ")
    gui_pw = prompt_windows_credui()
    if gui_pw:
        return gui_pw
    raise RuntimeError(
        "No interactive password provided. Run this script directly in PowerShell: "
        ".\\backend\\.venv\\Scripts\\python.exe backend\\scripts\\setup_local_db.py"
    )


def run_psql(psql_bin: str, user: str, password: str, dbname: str, args: list[str], stdin_sql: str | None = None) -> str:
    env = {**os.environ, "PGPASSWORD": password}
    res = subprocess.run(
        [psql_bin, "-h", "localhost", "-p", "5432", "-U", user, "-d", dbname, "-v", "ON_ERROR_STOP=1", *args],
        input=stdin_sql,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"psql failed (code {res.returncode}): {res.stderr.strip()}")
    return res.stdout.strip()


def main() -> None:
    psql_bin = find_psql()
    app_pass = safe_secret(28)
    test_pass = safe_secret(28)
    django_secret = safe_secret(56)
    token_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")

    pg_password = get_postgres_admin_password()
    try:
        role_sql = f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'drip_app') THEN
        CREATE ROLE drip_app WITH LOGIN PASSWORD '{app_pass}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    ELSE
        ALTER ROLE drip_app WITH LOGIN PASSWORD '{app_pass}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'drip_test') THEN
        CREATE ROLE drip_test WITH LOGIN PASSWORD '{test_pass}' NOSUPERUSER CREATEDB NOCREATEROLE;
    ELSE
        ALTER ROLE drip_test WITH LOGIN PASSWORD '{test_pass}' NOSUPERUSER CREATEDB NOCREATEROLE;
    END IF;
END
$$;
"""
        run_psql(psql_bin, "postgres", pg_password, "postgres", [], stdin_sql=role_sql)

        for db_name, owner in [("drip_and_rhythm", "drip_app"), ("drip_and_rhythm_test", "drip_test")]:
            exists = run_psql(
                psql_bin,
                "postgres",
                pg_password,
                "postgres",
                ["-tAc", f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"],
            )
            if exists != "1":
                run_psql(
                    psql_bin,
                    "postgres",
                    pg_password,
                    "postgres",
                    ["-c", f"CREATE DATABASE {db_name} OWNER {owner} ENCODING 'UTF8';"],
                )
            else:
                run_psql(
                    psql_bin,
                    "postgres",
                    pg_password,
                    "postgres",
                    ["-c", f"ALTER DATABASE {db_name} OWNER TO {owner};"],
                )
            run_psql(
                psql_bin,
                "postgres",
                pg_password,
                db_name,
                ["-c", f"GRANT ALL ON SCHEMA public TO {owner};"],
            )
    finally:
        pg_password = ""

    app_check = run_psql(psql_bin, "drip_app", app_pass, "drip_and_rhythm", ["-tAc", "SELECT current_user || '@' || current_database();"])
    test_check = run_psql(psql_bin, "drip_test", test_pass, "drip_and_rhythm_test", ["-tAc", "SELECT current_user || '@' || current_database();"])
    print(f"Verified runtime DB role: {app_check}")
    print(f"Verified test DB role:    {test_check}")

    backend_env = f"""DJANGO_SECRET_KEY={django_secret}
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql://drip_app:{app_pass}@127.0.0.1:5432/drip_and_rhythm
TEST_DATABASE_URL=postgresql://drip_test:{test_pass}@127.0.0.1:5432/drip_and_rhythm_test
APP_BASE_URL=http://localhost:3000
DJANGO_TIME_ZONE=Africa/Kampala
TOKEN_ENCRYPTION_KEY={token_key}
CLAIM_RECEIPT_TTL_DAYS=
EMAIL_DELIVERY_MODE=local
RESEND_API_KEY=
RESEND_FROM_EMAIL=invitations@dripandrhythm.local
RESEND_FROM_NAME=DRIP & RHYTHM
RESEND_REPLY_TO_EMAIL=support@dripandrhythm.local
RESEND_WEBHOOK_SECRET=whsec_dGVzdF9sb2NhbF9zZWNyZXRfa2V5X2Zvcl9zdm14X3ZlcmlmeQ==
EMAIL_MAX_RETRIES=5
EMAIL_WORKER_POLL_INTERVAL=3
EMAIL_WORKER_LEASE_SECONDS=120
"""
    (REPO_ROOT / "backend" / ".env").write_text(backend_env, encoding="utf-8")

    frontend_env = """NEXT_PUBLIC_SITE_URL=http://localhost:3000
DJANGO_INTERNAL_API_URL=http://127.0.0.1:8000
"""
    (REPO_ROOT / "frontend" / ".env").write_text(frontend_env, encoding="utf-8")
    print("Created gitignored backend/.env and frontend/.env.")


if __name__ == "__main__":
    main()
