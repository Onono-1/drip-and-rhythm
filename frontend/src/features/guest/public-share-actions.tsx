"use client";

import { Check, Download, Maximize2, Share2, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/primitives";
import type { ArtworkFormat, PublicSharePayload } from "@/types/api";

const SHARE_FORMATS: Array<{ id: Exclude<ArtworkFormat, "preview">; label: string; aspectClass: string }> = [
  { id: "story", label: "Story (9:16)", aspectClass: "aspect-[9/16] max-w-[360px]" },
  { id: "portrait", label: "Portrait (4:5)", aspectClass: "aspect-[4/5] max-w-[440px]" },
  { id: "square", label: "Square (1:1)", aspectClass: "aspect-square max-w-[440px]" },
];

export function PublicShareArtworkShowcase({ payload }: { payload: PublicSharePayload }) {
  const [selectedFormat, setSelectedFormat] = useState<Exclude<ArtworkFormat, "preview">>("portrait");
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [copied, setCopied] = useState(false);

  const activeMeta = SHARE_FORMATS.find((f) => f.id === selectedFormat) ?? SHARE_FORMATS[1]!;
  const currentUrl = payload.artwork_urls[selectedFormat];

  const handleShare = async () => {
    setSharing(true);
    try {
      const resp = await fetch(currentUrl);
      const blob = await resp.blob();
      const file = new File([blob], `drip-and-rhythm-${selectedFormat}.png`, { type: "image/png" });

      if (typeof navigator.canShare === "function" && navigator.canShare({ files: [file] })) {
        await navigator.share({
          title: `${payload.event.name} — Invitation Secured`,
          text: `The invitation is secured. See you on December 5th. ${payload.event.hashtag}`,
          files: [file],
        });
      } else if (typeof navigator.share === "function") {
        await navigator.share({
          title: `${payload.event.name} — Invitation Secured`,
          text: `The invitation is secured. See you on December 5th. ${payload.event.hashtag}`,
          url: payload.share_url,
        });
      } else {
        await navigator.clipboard.writeText(payload.share_url);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      // User dismissed share sheet
    } finally {
      setSharing(false);
    }
  };

  return (
    <div className="flex flex-col items-center">
      <div className="flex flex-wrap justify-center gap-2">
        {SHARE_FORMATS.map((fmt) => (
          <button
            key={fmt.id}
            type="button"
            onClick={() => setSelectedFormat(fmt.id)}
            className={`min-h-10 cursor-pointer rounded-md border px-3.5 py-1.5 text-xs font-semibold transition-colors ${
              selectedFormat === fmt.id
                ? "border-amber bg-burnt text-ivory"
                : "border-champagne/25 bg-espresso text-champagne hover:border-champagne/50"
            }`}
          >
            {fmt.label}
          </button>
        ))}
      </div>

      <div className={`relative mt-4 w-full ${activeMeta.aspectClass}`}>
        <button
          type="button"
          onClick={() => setLightboxOpen(true)}
          aria-label="Enlarge promotional poster"
          className="group relative block h-full w-full cursor-zoom-in overflow-hidden rounded-lg border border-champagne/35 bg-midnight shadow-[0_26px_72px_rgba(232,93,25,0.2)]"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={currentUrl}
            alt={`${payload.event.name} Invitation Secured ${activeMeta.label} artwork`}
            className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-[1.015]"
          />
          <span className="absolute right-3 bottom-3 inline-flex items-center gap-1.5 rounded-md bg-midnight/85 px-2.5 py-1.5 text-[11px] font-semibold text-champagne">
            <Maximize2 className="h-3.5 w-3.5 text-amber" aria-hidden="true" />
            Enlarge
          </span>
        </button>
      </div>

      <div className="mt-5 flex flex-wrap justify-center gap-2.5">
        <a href={`${currentUrl}&download=1`} download={`drip-and-rhythm-${selectedFormat}.png`}>
          <Button size="md">
            <Download className="h-4 w-4" aria-hidden="true" />
            Download Poster
          </Button>
        </a>
        <Button variant="secondary" size="md" loading={sharing} onClick={() => void handleShare()}>
          {copied ? <Check className="h-4 w-4 text-status-ok" /> : <Share2 className="h-4 w-4" />}
          {copied ? "Link Copied" : "Share"}
        </Button>
        <Link href="/">
          <Button variant="outline" size="md">
            Event Homepage
          </Button>
        </Link>
      </div>

      {lightboxOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Full-size poster preview"
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
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={currentUrl}
            alt="Enlarged DRIP & RHYTHM promotional poster"
            onClick={(e) => e.stopPropagation()}
            className="max-h-[88dvh] max-w-[92vw] rounded-md border border-champagne/30 object-contain shadow-2xl"
          />
        </div>
      )}
    </div>
  );
}
