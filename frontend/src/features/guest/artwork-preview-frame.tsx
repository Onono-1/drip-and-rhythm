"use client";

import { AlertCircle, Loader2, Maximize2, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/primitives";
import type { ArtworkFormat } from "@/types/api";

export const ARTWORK_FORMATS: Array<{
  id: Exclude<ArtworkFormat, "preview">;
  label: string;
  ratio: string;
  aspectClass: string;
}> = [
  {
    id: "story",
    label: "Story (9:16)",
    ratio: "1080 × 1920",
    aspectClass: "aspect-[9/16] max-w-[360px]",
  },
  {
    id: "portrait",
    label: "Portrait (4:5)",
    ratio: "1080 × 1350",
    aspectClass: "aspect-[4/5] max-w-[440px]",
  },
  {
    id: "square",
    label: "Square (1:1)",
    ratio: "1080 × 1080",
    aspectClass: "aspect-square max-w-[450px]",
  },
];

const MAX_CLIENT_BLOB_CACHE = 12;
const MAX_AUTO_RETRIES = 3;
const TRANSIENT_HTTP_STATUSES = new Set([502, 503, 504]);

interface CachedArtworkEntry {
  blob: Blob;
  objectUrl: string;
}

const clientArtworkCache = new Map<string, CachedArtworkEntry>();
const inflightArtworkPromises = new Map<string, Promise<CachedArtworkEntry>>();

function rememberArtwork(url: string, blob: Blob): CachedArtworkEntry {
  const existing = clientArtworkCache.get(url);
  if (existing) {
    clientArtworkCache.delete(url);
    clientArtworkCache.set(url, existing);
    return existing;
  }
  const entry: CachedArtworkEntry = {
    blob,
    objectUrl: URL.createObjectURL(blob),
  };
  clientArtworkCache.set(url, entry);
  if (clientArtworkCache.size > MAX_CLIENT_BLOB_CACHE) {
    const oldestKey = clientArtworkCache.keys().next().value;
    if (oldestKey) {
      const evicted = clientArtworkCache.get(oldestKey);
      clientArtworkCache.delete(oldestKey);
      if (evicted) {
        URL.revokeObjectURL(evicted.objectUrl);
      }
    }
  }
  return entry;
}

export function clearClientArtworkCacheForTest(): void {
  for (const entry of clientArtworkCache.values()) {
    URL.revokeObjectURL(entry.objectUrl);
  }
  clientArtworkCache.clear();
  inflightArtworkPromises.clear();
}

function parseRetryDelayMs(retryAfterHeader: string | null, attemptIndex: number): number {
  const backoffDefaults = [1500, 3000, 5000];
  let baseMs = backoffDefaults[Math.min(attemptIndex, backoffDefaults.length - 1)] ?? 4000;
  if (retryAfterHeader) {
    const parsedSec = Number(retryAfterHeader.trim());
    if (Number.isFinite(parsedSec) && parsedSec > 0) {
      baseMs = Math.min(8000, Math.max(1200, Math.round(parsedSec * 1000)));
    }
  }
  const jitter = Math.floor(Math.random() * 250);
  return baseMs + jitter;
}

function waitWithAbort(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

class ArtworkHttpError extends Error {
  status: number;
  retryAfter: string | null;
  permanent: boolean;

  constructor(status: number, retryAfter: string | null) {
    super(`Artwork HTTP ${status}`);
    this.name = "ArtworkHttpError";
    this.status = status;
    this.retryAfter = retryAfter;
    this.permanent = !TRANSIENT_HTTP_STATUSES.has(status);
  }
}

async function fetchArtworkOnceDeduplicated(url: string): Promise<CachedArtworkEntry> {
  const cached = clientArtworkCache.get(url);
  if (cached) return cached;

  const existing = inflightArtworkPromises.get(url);
  if (existing) return existing;

  const promise = (async () => {
    const resp = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
    });
    if (!resp.ok) {
      throw new ArtworkHttpError(resp.status, resp.headers.get("retry-after"));
    }
    const contentType = resp.headers.get("content-type") || "";
    if (!contentType.includes("image/")) {
      throw new ArtworkHttpError(502, null);
    }
    const blob = await resp.blob();
    if (blob.size === 0) {
      throw new ArtworkHttpError(502, null);
    }
    return rememberArtwork(url, blob);
  })().finally(() => {
    inflightArtworkPromises.delete(url);
  });

  inflightArtworkPromises.set(url, promise);
  return promise;
}

export type ArtworkLoadStatus = "idle" | "loading" | "ready" | "error";

interface ResolvedRequestState {
  requestKey: string;
  outcome: "ready" | "error";
  entry: CachedArtworkEntry | null;
  isPermanentError: boolean;
}

export function useLazyArtwork(url: string | undefined) {
  const [reloadNonce, setReloadNonce] = useState(0);
  const [resolved, setResolved] = useState<ResolvedRequestState | null>(null);
  const [slowKey, setSlowKey] = useState<string | null>(null);

  const requestKey = url ? `${url}#${reloadNonce}` : "";
  const cachedEntry = url ? clientArtworkCache.get(url) ?? null : null;

  useEffect(() => {
    if (!url || clientArtworkCache.has(url)) {
      return;
    }

    const activeKey = `${url}#${reloadNonce}`;
    const controller = new AbortController();

    const slowTimer = window.setTimeout(() => {
      if (!controller.signal.aborted) {
        setSlowKey(activeKey);
      }
    }, 3500);

    void (async () => {
      for (let attempt = 0; attempt <= MAX_AUTO_RETRIES; attempt += 1) {
        if (controller.signal.aborted) return;
        try {
          const entry = await fetchArtworkOnceDeduplicated(url);
          if (controller.signal.aborted) return;
          setResolved({
            requestKey: activeKey,
            outcome: "ready",
            entry,
            isPermanentError: false,
          });
          return;
        } catch (err) {
          if (controller.signal.aborted || (err as Error)?.name === "AbortError") {
            return;
          }
          if (err instanceof ArtworkHttpError && err.permanent) {
            setResolved({
              requestKey: activeKey,
              outcome: "error",
              entry: null,
              isPermanentError: true,
            });
            return;
          }
          if (attempt >= MAX_AUTO_RETRIES) {
            setResolved({
              requestKey: activeKey,
              outcome: "error",
              entry: null,
              isPermanentError: false,
            });
            return;
          }
          setSlowKey(activeKey);
          const delayMs = parseRetryDelayMs(
            err instanceof ArtworkHttpError ? err.retryAfter : null,
            attempt,
          );
          try {
            await waitWithAbort(delayMs, controller.signal);
          } catch {
            return;
          }
        }
      }
    })();

    return () => {
      controller.abort();
      window.clearTimeout(slowTimer);
    };
  }, [url, reloadNonce]);

  const activeEntry =
    cachedEntry ?? (resolved?.requestKey === requestKey ? resolved.entry : null);

  let status: ArtworkLoadStatus = "idle";
  if (!url) {
    status = "idle";
  } else if (activeEntry) {
    status = "ready";
  } else if (resolved?.requestKey === requestKey && resolved.outcome === "error") {
    status = "error";
  } else {
    status = "loading";
  }

  const isPermanentError =
    resolved?.requestKey === requestKey ? resolved.isPermanentError : false;
  const isSlow = status === "loading" && slowKey === requestKey;
  const blob = activeEntry?.blob ?? null;
  const objectUrl = activeEntry?.objectUrl ?? null;

  const blobRef = useRef<Blob | null>(blob);
  useEffect(() => {
    blobRef.current = blob;
  }, [blob]);

  const retry = useCallback(() => {
    setReloadNonce((n) => n + 1);
  }, []);

  const triggerDownload = useCallback((filename: string) => {
    const currentBlob = blobRef.current;
    if (!currentBlob) return;
    const dlUrl = URL.createObjectURL(currentBlob);
    const link = document.createElement("a");
    link.href = dlUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(dlUrl), 2000);
  }, []);

  return {
    status,
    blob,
    objectUrl,
    isSlow,
    isPermanentError,
    retry,
    triggerDownload,
  };
}

export function ArtworkPreviewFrame({
  aspectClass,
  ratioLabel,
  formatLabel,
  altText,
  status,
  objectUrl,
  isSlow,
  isPermanentError,
  onRetry,
}: {
  aspectClass: string;
  ratioLabel: string;
  formatLabel: string;
  altText: string;
  status: ArtworkLoadStatus;
  objectUrl: string | null;
  isSlow: boolean;
  isPermanentError: boolean;
  onRetry: () => void;
}) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [revealedUrl, setRevealedUrl] = useState<string | null>(null);

  const isReady = status === "ready" && Boolean(objectUrl);
  const imgRevealed = Boolean(objectUrl && revealedUrl === objectUrl);

  return (
    <div className="flex w-full flex-col items-center">
      <div className={`relative w-full ${aspectClass}`}>
        {isReady && objectUrl ? (
          <button
            type="button"
            onClick={() => setLightboxOpen(true)}
            aria-label={`Enlarge ${formatLabel} promotional artwork`}
            className="group relative block h-full w-full cursor-zoom-in overflow-hidden rounded-lg border border-champagne/30 bg-midnight shadow-[0_24px_64px_rgba(0,0,0,0.6)]"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={objectUrl}
              alt={altText}
              onLoad={() => setRevealedUrl(objectUrl)}
              className={`h-full w-full object-contain transition-all duration-300 group-hover:scale-[1.01] ${
                imgRevealed ? "opacity-100" : "opacity-0"
              }`}
            />
          </button>
        ) : status === "error" ? (
          <div
            role="status"
            className="flex h-full w-full flex-col items-center justify-center rounded-lg border border-champagne/25 bg-midnight/95 p-6 text-center"
          >
            <AlertCircle className="h-7 w-7 text-amber" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-ivory">
              {isPermanentError
                ? "This artwork preview is unavailable."
                : "Couldn't load your artwork right now."}
            </p>
            {!isPermanentError && (
              <>
                <p className="mt-1.5 max-w-xs text-xs leading-relaxed text-ivory-muted">
                  Your invitation remains secured. Tap retry in a moment to load this format.
                </p>
                <Button variant="outline" size="sm" onClick={onRetry} className="mt-4">
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  Retry
                </Button>
              </>
            )}
          </div>
        ) : (
          <div
            role="status"
            aria-live="polite"
            className="flex h-full w-full flex-col items-center justify-center rounded-lg border border-champagne/20 bg-midnight/90 p-6 text-center"
          >
            <Loader2 className="h-7 w-7 animate-spin text-amber" aria-hidden="true" />
            <p className="mt-3 text-sm font-semibold text-champagne">
              {isSlow
                ? "Your invitation is secured. We're preparing your artwork."
                : "Preparing your artwork..."}
            </p>
          </div>
        )}
      </div>

      {/* Footer metadata & outside Enlarge control (never covers the artwork footer) */}
      <div className="mt-3 flex flex-wrap items-center justify-center gap-3 text-xs text-ivory-muted">
        <span>
          <span className="font-semibold text-champagne">{ratioLabel}px</span> · Safe to share on your favourite social platforms.
        </span>
        <button
          type="button"
          disabled={!isReady}
          onClick={() => setLightboxOpen(true)}
          className="inline-flex min-h-8 cursor-pointer items-center gap-1.5 rounded border border-champagne/25 bg-espresso px-2.5 py-1 text-[11px] font-semibold text-champagne transition-colors hover:border-amber hover:text-ivory disabled:cursor-not-allowed disabled:opacity-45"
        >
          <Maximize2 className="h-3.5 w-3.5 text-amber" aria-hidden="true" />
          Enlarge
        </button>
      </div>

      {lightboxOpen && isReady && objectUrl && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Full-size promotional artwork preview"
          onClick={() => setLightboxOpen(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4 backdrop-blur-xs"
        >
          <button
            type="button"
            onClick={() => setLightboxOpen(false)}
            aria-label="Close enlarged preview"
            className="fixed top-4 right-4 inline-flex h-11 w-11 items-center justify-center rounded-full border border-champagne/40 bg-midnight/90 text-ivory hover:border-amber"
          >
            <X className="h-5 w-5" />
          </button>
          <div
            onClick={(e) => e.stopPropagation()}
            className="flex max-h-[92dvh] max-w-[92vw] flex-col items-center gap-3"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={objectUrl}
              alt={`Enlarged ${formatLabel} promotional artwork`}
              className="max-h-[84dvh] w-auto rounded-md border border-champagne/30 object-contain shadow-2xl"
            />
            <p className="text-xs text-champagne">
              {formatLabel} · {ratioLabel}px
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
