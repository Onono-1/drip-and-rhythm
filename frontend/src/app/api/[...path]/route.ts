import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const ALLOWED_TOP_SEGMENTS = new Set([
  "health",
  "auth",
  "event",
  "users",
  "invitations",
  "invite",
  "claim-receipt",
  "share",
  "verify",
  "check-in",
  "check-ins",
  "dashboard",
  "audit-logs",
  "emails",
  "webhooks",
  "schema",
  "docs",
]);

const FORWARDED_REQ_HEADERS = [
  "accept",
  "accept-language",
  "content-type",
  "cookie",
  "if-none-match",
  "origin",
  "referer",
  "user-agent",
  "x-csrftoken",
  "svix-id",
  "svix-timestamp",
  "svix-signature",
];

function getDjangoInternalBase(): string {
  const raw = (process.env.DJANGO_INTERNAL_API_URL || "http://127.0.0.1:8000").trim();
  const hasScheme = /^https?:\/\//i.test(raw);
  const isLocalOrPort =
    raw.includes(":") || raw.startsWith("127.") || raw.startsWith("localhost");
  const withScheme = hasScheme ? raw : isLocalOrPort ? `http://${raw}` : `https://${raw}`;
  return withScheme.replace(/\/+$/, "");
}

async function proxyToDjango(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { path } = await context.params;
  const firstSegment = path[0] || "";

  if (
    !firstSegment ||
    !ALLOWED_TOP_SEGMENTS.has(firstSegment) ||
    path.some((seg) => seg === ".." || seg === "." || seg.includes("\\"))
  ) {
    return NextResponse.json(
      {
        error: {
          code: "NOT_FOUND",
          message: "API endpoint not found.",
          details: {},
        },
      },
      { status: 404, headers: { "Cache-Control": "no-store, max-age=0" } },
    );
  }

  const incomingUrl = new URL(request.url);
  // Preserve exact pathname (including trailing slash) + query string
  if (!incomingUrl.pathname.startsWith("/api/")) {
    return NextResponse.json(
      { error: { code: "NOT_FOUND", message: "Invalid API path.", details: {} } },
      { status: 404 },
    );
  }

  const targetUrl = `${getDjangoInternalBase()}${incomingUrl.pathname}${incomingUrl.search}`;

  const upstreamHeaders = new Headers();
  for (const headerName of FORWARDED_REQ_HEADERS) {
    const val = request.headers.get(headerName);
    if (val) {
      upstreamHeaders.set(headerName, val);
    }
  }
  // Canonical public origin: prefer the configured site URL so Django host/CSRF validation always sees the
  // public domain (also covers Render health checks that arrive without edge forwarding headers).
  let publicProto: string | undefined;
  let publicHost: string | undefined;
  try {
    const site = process.env.NEXT_PUBLIC_SITE_URL ? new URL(process.env.NEXT_PUBLIC_SITE_URL) : null;
    if (site && !["localhost", "127.0.0.1"].includes(site.hostname)) {
      publicProto = site.protocol.replace(":", "");
      publicHost = site.host;
    }
  } catch {
    // Ignore malformed site URL and fall back to edge headers.
  }
  const edgeProto = request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim();
  const edgeHost =
    request.headers.get("x-forwarded-host")?.split(",")[0]?.trim() || request.headers.get("host");
  upstreamHeaders.set(
    "x-forwarded-proto",
    publicProto || edgeProto || incomingUrl.protocol.replace(":", ""),
  );
  upstreamHeaders.set("x-forwarded-host", publicHost || edgeHost || incomingUrl.host);

  const proxySecret = process.env.PROXY_SHARED_SECRET?.trim();
  if (proxySecret) {
    upstreamHeaders.set("x-drip-proxy-secret", proxySecret);
  }
  const clientIp = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (clientIp) {
    upstreamHeaders.set("x-drip-client-ip", clientIp);
  }

  const method = request.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";
  // Preserve raw bytes untouched (essential for Svix webhook HMAC verification)
  const rawBody = hasBody ? await request.arrayBuffer() : undefined;

  try {
    const upstreamResp = await fetch(targetUrl, {
      method,
      headers: upstreamHeaders,
      body: rawBody && rawBody.byteLength > 0 ? rawBody : undefined,
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(28_000),
    });

    if (upstreamResp.status >= 502) {
      console.warn(`[proxy] upstream_status=${upstreamResp.status} segment=${firstSegment} method=${method}`);
    }

    const respHeaders = new Headers();
    const copyHeaderNames = [
      "content-type",
      "content-disposition",
      "content-length",
      "cache-control",
      "etag",
      "pragma",
      "retry-after",
      "vary",
      "allow",
      "location",
    ];
    for (const name of copyHeaderNames) {
      const value = upstreamResp.headers.get(name);
      if (value) {
        respHeaders.set(name, value);
      }
    }

    const setCookies =
      typeof upstreamResp.headers.getSetCookie === "function"
        ? upstreamResp.headers.getSetCookie()
        : [];
    for (const cookieStr of setCookies) {
      respHeaders.append("set-cookie", cookieStr);
    }
    if (setCookies.length === 0) {
      const fallbackCookie = upstreamResp.headers.get("set-cookie");
      if (fallbackCookie) {
        respHeaders.set("set-cookie", fallbackCookie);
      }
    }

    if (!respHeaders.has("cache-control")) {
      respHeaders.set("cache-control", "no-store, max-age=0, private");
    }

    return new NextResponse(upstreamResp.body, {
      status: upstreamResp.status,
      headers: respHeaders,
    });
  } catch (err) {
    console.warn(
      `[proxy] upstream_unreachable segment=${firstSegment} method=${method} error=${err instanceof Error ? err.name : "unknown"}`,
    );
    return NextResponse.json(
      {
        error: {
          code: "UPSTREAM_UNAVAILABLE",
          message: "The invitation service is momentarily unreachable. Please try again.",
          details: {},
        },
      },
      {
        status: 502,
        headers: {
          "Cache-Control": "no-store, max-age=0",
          "Retry-After": "3",
        },
      },
    );
  }
}

export const GET = proxyToDjango;
export const POST = proxyToDjango;
export const PATCH = proxyToDjango;
export const PUT = proxyToDjango;
export const DELETE = proxyToDjango;
export const OPTIONS = proxyToDjango;
