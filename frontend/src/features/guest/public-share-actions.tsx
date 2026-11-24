"use client";

import { Check, Copy, Download, Share2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/primitives";
import type { ArtworkFormat, PublicSharePayload } from "@/types/api";

import { ARTWORK_FORMATS, ArtworkPreviewFrame, useLazyArtwork } from "./artwork-preview-frame";

export function PublicShareArtworkShowcase({ payload }: { payload: PublicSharePayload }) {
  const [selectedFormat, setSelectedFormat] = useState<Exclude<ArtworkFormat, "preview">>("story");
  const [sharing, setSharing] = useState(false);
  const [copied, setCopied] = useState(false);

  const activeMeta = ARTWORK_FORMATS.find((f) => f.id === selectedFormat) ?? ARTWORK_FORMATS[0]!;
  const currentUrl = payload.artwork_urls[selectedFormat];
  const artwork = useLazyArtwork(currentUrl);
  const artworkReady = artwork.status === "ready" && Boolean(artwork.blob);

  const handleCopyShareLink = async () => {
    await navigator.clipboard.writeText(payload.share_url);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  const handleShare = async () => {
    if (!artwork.blob) return;
    setSharing(true);
    try {
      const filename = `drip-and-rhythm-${selectedFormat}.png`;
      const file = new File([artwork.blob], filename, { type: "image/png" });

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
        await handleCopyShareLink();
      }
    } catch {
      // User dismissed share sheet
    } finally {
      setSharing(false);
    }
  };

  return (
    <div className="flex flex-col items-center">
      <div className="mb-4 flex flex-wrap justify-center gap-2">
        {ARTWORK_FORMATS.map((fmt) => (
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

      <ArtworkPreviewFrame
        aspectClass={activeMeta.aspectClass}
        ratioLabel={activeMeta.ratio}
        formatLabel={activeMeta.label}
        altText={`${payload.event.name} Invitation Secured ${activeMeta.label} artwork`}
        status={artwork.status}
        objectUrl={artwork.objectUrl}
        isSlow={artwork.isSlow}
        isPermanentError={artwork.isPermanentError}
        onRetry={artwork.retry}
      />

      <div className="mt-5 flex flex-wrap justify-center gap-2.5">
        <Button
          size="md"
          disabled={!artworkReady}
          onClick={() => artwork.triggerDownload(`drip-and-rhythm-${selectedFormat}.png`)}
        >
          <Download className="h-4 w-4" aria-hidden="true" />
          Download Poster
        </Button>
        <Button
          variant="secondary"
          size="md"
          disabled={!artworkReady}
          loading={sharing}
          onClick={() => void handleShare()}
        >
          <Share2 className="h-4 w-4" aria-hidden="true" />
          Share Poster
        </Button>
        <Button variant="outline" size="md" onClick={() => void handleCopyShareLink()}>
          {copied ? <Check className="h-4 w-4 text-status-ok" /> : <Copy className="h-4 w-4" />}
          {copied ? "Link Copied" : "Copy Link"}
        </Button>
        <Link href="/">
          <Button variant="ghost" size="md">
            Event Homepage
          </Button>
        </Link>
      </div>
    </div>
  );
}
