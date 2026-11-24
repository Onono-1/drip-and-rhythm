export class ApiClientError extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly details: Record<string, unknown>;

  constructor(code: string, message: string, status: number, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const parts = document.cookie.split(";");
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed.startsWith(`${name}=`)) {
      return decodeURIComponent(trimmed.slice(name.length + 1));
    }
  }
  return null;
}

let inflightCsrfPromise: Promise<string> | null = null;

export async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie("drip_csrf");
  if (existing) return existing;

  if (!inflightCsrfPromise) {
    inflightCsrfPromise = fetch("/api/auth/csrf/", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(async (res) => {
        const data = (await res.json()) as { csrfToken?: string };
        return data.csrfToken || readCookie("drip_csrf") || "";
      })
      .finally(() => {
        inflightCsrfPromise = null;
      });
  }
  return inflightCsrfPromise;
}

export async function apiFetch<T>(
  path: string,
  options: Omit<RequestInit, "body"> & { json?: unknown } = {},
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const isMutating = method !== "GET" && method !== "HEAD" && method !== "OPTIONS";

  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");

  if (isMutating) {
    const csrfToken = await ensureCsrfToken();
    if (csrfToken) {
      headers.set("X-CSRFToken", csrfToken);
    }
  }

  let body: BodyInit | undefined;
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  }

  const response = await fetch(path, {
    ...options,
    method,
    headers,
    body,
    credentials: "same-origin",
    cache: "no-store",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    const errObj = payload?.error;
    throw new ApiClientError(
      errObj?.code || "REQUEST_FAILED",
      errObj?.message || `Request failed (${response.status}).`,
      response.status,
      (errObj?.details as Record<string, unknown>) || {},
    );
  }

  return payload as T;
}

/**
 * Prevent open redirects in `/admin/login?next=...`.
 * Allows only clean `/admin/...` relative paths on the same origin.
 */
export function sanitizeAdminNextPath(rawNext: string | null | undefined): string {
  if (!rawNext) return "/admin/dashboard";
  const trimmed = rawNext.trim();
  if (
    !trimmed.startsWith("/admin") ||
    trimmed.startsWith("//") ||
    trimmed.includes("\\") ||
    trimmed.includes("://") ||
    trimmed.startsWith("/admin/login")
  ) {
    return "/admin/dashboard";
  }
  return trimmed;
}

export function formatEventDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  if (!y || !m || !d) return isoDate;
  const dt = new Date(Date.UTC(y, m - 1, d));
  return new Intl.DateTimeFormat("en-UG", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(dt);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return new Intl.DateTimeFormat("en-UG", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Africa/Kampala",
  }).format(dt);
}
