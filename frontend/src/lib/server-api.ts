import "server-only";

import type { PublicEvent } from "@/types/api";

const FALLBACK_PUBLIC_EVENT: PublicEvent = {
  name: "DRIP & RHYTHM",
  subtitle: "Private Party",
  tagline: "An affair of fashion, music and culture",
  organizers: "After Dark Events × Hype District",
  hashtag: "#DripAndRhythm",
  event_date: "2026-12-05",
  start_time: null,
  end_time: null,
  location: "Muyenga, Kampala, Uganda",
  venue_display: null,
  venue_is_public: false,
  reservation_contacts: ["0781210342", "0742627388", "0700246148"],
  time_zone: "Africa/Kampala",
  age_restriction: "18+",
  claiming_enabled: true,
  public_sharing_enabled: true,
};

export function getDjangoServerBaseUrl(): string {
  const raw = (process.env.DJANGO_INTERNAL_API_URL || "http://127.0.0.1:8000").trim();
  const hasScheme = /^https?:\/\//i.test(raw);
  const isLocalOrPort =
    raw.includes(":") || raw.startsWith("127.") || raw.startsWith("localhost");
  const withScheme = hasScheme ? raw : isLocalOrPort ? `http://${raw}` : `https://${raw}`;
  return withScheme.replace(/\/+$/, "");
}

function buildServerUpstreamHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json", ...extra };
  const proxySecret = process.env.PROXY_SHARED_SECRET?.trim();
  if (proxySecret) {
    headers["X-Drip-Proxy-Secret"] = proxySecret;
  }
  try {
    const site = process.env.NEXT_PUBLIC_SITE_URL ? new URL(process.env.NEXT_PUBLIC_SITE_URL) : null;
    if (site && !["localhost", "127.0.0.1"].includes(site.hostname)) {
      headers["X-Forwarded-Proto"] = site.protocol.replace(":", "");
      headers["X-Forwarded-Host"] = site.host;
    }
  } catch {
    // Ignore malformed site URL
  }
  return headers;
}

export function getPublicSiteUrl(): string {
  return (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/+$/, "");
}

export async function fetchPublicEventServer(): Promise<PublicEvent> {
  try {
    const res = await fetch(`${getDjangoServerBaseUrl()}/api/event/public/`, {
      cache: "no-store",
      headers: buildServerUpstreamHeaders(),
    });
    if (!res.ok) return FALLBACK_PUBLIC_EVENT;
    return (await res.json()) as PublicEvent;
  } catch {
    return FALLBACK_PUBLIC_EVENT;
  }
}

export async function fetchServerJson<T>(
  apiPath: string,
  cookieHeader?: string,
): Promise<{ ok: boolean; status: number; data: T | null }> {
  try {
    const extra: Record<string, string> = {};
    if (cookieHeader) {
      extra.Cookie = cookieHeader;
    }
    const res = await fetch(`${getDjangoServerBaseUrl()}${apiPath}`, {
      cache: "no-store",
      headers: buildServerUpstreamHeaders(extra),
    });
    if (!res.ok) {
      return { ok: false, status: res.status, data: null };
    }
    const data = (await res.json()) as T;
    return { ok: true, status: res.status, data };
  } catch {
    return { ok: false, status: 502, data: null };
  }
}
