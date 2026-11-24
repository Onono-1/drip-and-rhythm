"use client";

import confetti from "canvas-confetti";
import { Check, Copy, Download, Mail, Share2, Sparkles } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { WhatsAppContactLinks } from "@/components/brand/whatsapp-contacts";
import { Button, StatusBadge } from "@/components/ui/primitives";
import { apiFetch, formatEventDate } from "@/lib/api-client";
import type { ArtworkFormat, ClaimReceiptPayload, EmailDeliveryStatus } from "@/types/api";

import { ARTWORK_FORMATS, ArtworkPreviewFrame, useLazyArtwork } from "./artwork-preview-frame";

const PREPARED_CAPTIONS = [
  "Invitation secured. The drip is ready, the rhythm is calling. See you on December 5th. #DripAndRhythm",
  "I'm officially on the list. An affair of fashion, music and culture awaits. #DripAndRhythm",
  "The invitation is secured. Now it's time to plan the drip. #DripAndRhythm",
];

function describeEmailStatus(status: EmailDeliveryStatus, email: string) {
  switch (status) {
    case "DELIVERED":
      return {
        tone: "success" as const,
        badge: "Delivered",
        text: `Your official PDF admission pass has been delivered to ${email}.`,
      };
    case "SENT":
      return {
        tone: "gold" as const,
        badge: "Dispatched",
        text: `Your official PDF admission pass has been sent to ${email}. Check your inbox or spam folder.`,
      };
    case "FAILED":
    case "BOUNCED":
      return {
        tone: "danger" as const,
        badge: "Delivery Issue",
        text: `We encountered an issue delivering to ${email}. Message the host desk on WhatsApp to resend or verify your email.`,
      };
    default:
      return {
        tone: "warning" as const,
        badge: "Sending Pass",
        text: `Your official PDF admission pass is being generated and sent to ${email}.`,
      };
  }
}

export function InvitationSuccessClient({
  initialReceipt,
}: {
  initialReceipt: ClaimReceiptPayload | null;
}) {
  const prefersReducedMotion = useReducedMotion();
  const [receipt, setReceipt] = useState<ClaimReceiptPayload | null>(initialReceipt);
  const [selectedFormat, setSelectedFormat] = useState<Exclude<ArtworkFormat, "preview">>("story");
  const [savingPref, setSavingPref] = useState(false);
  const [sharingBusy, setSharingBusy] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const activeFormatMeta = ARTWORK_FORMATS.find((f) => f.id === selectedFormat) ?? ARTWORK_FORMATS[0]!;
  const currentArtworkUrl = receipt?.artwork_urls[selectedFormat];
  const artwork = useLazyArtwork(currentArtworkUrl);
  const artworkReady = artwork.status === "ready" && Boolean(artwork.blob);

  useEffect(() => {
    if (!receipt || prefersReducedMotion) return;
    try {
      void confetti({
        particleCount: 55,
        spread: 68,
        origin: { y: 0.62 },
        colors: ["#E85D19", "#FFBE55", "#F5CE86", "#FFF3E0"],
      });
    } catch {
      // Ignore canvas unavailability in headless test environments
    }
  }, [prefersReducedMotion, receipt]);

  useEffect(() => {
    if (!receipt) return;
    if (receipt.email_delivery_status !== "PENDING" && receipt.email_delivery_status !== "PROCESSING") {
      return;
    }
    let polls = 0;
    const timer = window.setInterval(async () => {
      polls += 1;
      if (polls > 4) {
        window.clearInterval(timer);
        return;
      }
      try {
        const refreshed = await apiFetch<ClaimReceiptPayload>("/api/claim-receipt/");
        setReceipt(refreshed);
      } catch {
        window.clearInterval(timer);
      }
    }, 6000);
    return () => window.clearInterval(timer);
  }, [receipt]);

  const copyText = async (key: string, value: string) => {
    await navigator.clipboard.writeText(value);
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey(null), 2200);
  };

  const updatePreference = async (patch: {
    show_nickname_publicly?: boolean;
    public_sharing_enabled?: boolean;
  }) => {
    if (!receipt) return;
    setSavingPref(true);
    setFeedbackMsg(null);
    try {
      const updated = await apiFetch<ClaimReceiptPayload>("/api/claim-receipt/sharing/", {
        method: "PATCH",
        json: patch,
      });
      setReceipt(updated);
    } catch {
      setFeedbackMsg("Could not save sharing preference. Refresh and try again.");
    } finally {
      setSavingPref(false);
    }
  };

  const handleNativeShareArtwork = async () => {
    if (!receipt || !artwork.blob) return;
    setSharingBusy(true);
    setFeedbackMsg(null);

    try {
      const filename = `drip-and-rhythm-${selectedFormat}.png`;
      const file = new File([artwork.blob], filename, { type: "image/png" });

      if (typeof navigator.canShare === "function" && navigator.canShare({ files: [file] })) {
        await navigator.share({
          title: "DRIP & RHYTHM — Invitation Secured",
          text: PREPARED_CAPTIONS[0],
          files: [file],
        });
      } else if (typeof navigator.share === "function" && receipt.share_url) {
        await navigator.share({
          title: "DRIP & RHYTHM — Invitation Secured",
          text: PREPARED_CAPTIONS[0],
          url: receipt.share_url,
        });
      } else {
        artwork.triggerDownload(filename);
        setFeedbackMsg("Native file sharing is unavailable here — started PNG download instead.");
      }
    } catch (err) {
      if ((err as Error)?.name !== "AbortError") {
        setFeedbackMsg("Unable to open native share. Use Download PNG instead.");
      }
    } finally {
      setSharingBusy(false);
    }
  };

  if (!receipt) {
    return (
      <div className="amber-stage-glow film-grain flex min-h-dvh flex-col items-center justify-center px-6 py-20 text-center">
        <OrganizerWordmark />
        <h1 className="font-display mt-5 text-4xl tracking-wide text-ivory uppercase sm:text-5xl">
          CHECK YOUR EMAIL INBOX
        </h1>
        <p className="mt-3 max-w-md text-sm leading-relaxed text-ivory-muted sm:text-base">
          No active confirmation session was found in this browser. If you have already claimed your invitation, your official PDF admission pass was sent to your registered email address.
        </p>
        <div className="mt-8">
          <Link href="/">
            <Button variant="outline">Return to Homepage</Button>
          </Link>
        </div>
      </div>
    );
  }

  const emailInfo = describeEmailStatus(receipt.email_delivery_status, receipt.guest_email);

  return (
    <div className="amber-stage-glow film-grain min-h-dvh">
      <header className="border-b border-champagne/15 bg-midnight/90">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/">
            <OrganizerWordmark organizers={receipt.event.organizers} />
          </Link>
          <Link href="/">
            <Button variant="ghost" size="sm">
              Event Homepage
            </Button>
          </Link>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-6xl px-5 py-8 sm:px-8 sm:py-12">
        {/* Celebration Banner */}
        <motion.section
          initial={prefersReducedMotion ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="rounded-lg border border-champagne/30 bg-espresso/95 p-6 sm:p-8"
        >
          <div className="inline-flex items-center gap-2 text-xs font-semibold text-amber">
            <Sparkles className="h-4 w-4 text-burnt" aria-hidden="true" />
            <span>Invitation Reference · {receipt.reference}</span>
          </div>
          <h1 className="font-display mt-2 text-4xl leading-none tracking-wide text-ivory uppercase sm:text-6xl">
            IT&apos;S OFFICIAL. INVITATION SECURED.
          </h1>
          <p className="mt-3 max-w-2xl text-base font-medium text-champagne sm:text-lg">
            {receipt.nickname}, you&apos;re officially on the list. The drip is ready. The rhythm is calling.
          </p>

          <div className="mt-5 flex flex-col gap-3 rounded-md border border-champagne/20 bg-midnight/85 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Mail className="mt-0.5 h-5 w-5 shrink-0 text-amber" aria-hidden="true" />
              <div className="text-sm">
                <p className="font-semibold text-ivory">{emailInfo.text}</p>
                <p className="mt-1 text-xs text-ivory-muted">
                  Date: {formatEventDate(receipt.event.event_date)} · {receipt.event.location} · Keep your emailed PDF admission pass private.
                </p>
              </div>
            </div>
            <div className="shrink-0">
              <StatusBadge tone={emailInfo.tone}>{emailInfo.badge}</StatusBadge>
            </div>
          </div>
        </motion.section>

        {/* Promotional Artwork Showcase & Controls */}
        <section className="mt-8 grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
          {/* Lazy Uncropped Artwork Showcase */}
          <div className="flex flex-col items-center lg:col-span-6">
            <div className="mb-5 flex w-full flex-wrap items-center justify-center gap-2">
              {ARTWORK_FORMATS.map((fmt) => (
                <button
                  key={fmt.id}
                  type="button"
                  onClick={() => setSelectedFormat(fmt.id)}
                  className={`min-h-11 cursor-pointer rounded-md border px-4 py-2 text-xs font-semibold transition-colors ${
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
              aspectClass={activeFormatMeta.aspectClass}
              ratioLabel={activeFormatMeta.ratio}
              formatLabel={activeFormatMeta.label}
              altText={`DRIP & RHYTHM ${activeFormatMeta.label} promotional artwork`}
              status={artwork.status}
              objectUrl={artwork.objectUrl}
              isSlow={artwork.isSlow}
              isPermanentError={artwork.isPermanentError}
              onRetry={artwork.retry}
            />
          </div>

          {/* Controls, Privacy & Captions */}
          <div className="space-y-6 rounded-lg border border-champagne/25 bg-espresso/90 p-6 sm:p-7 lg:col-span-6">
            <div>
              <h2 className="font-display text-3xl tracking-wide text-ivory uppercase">
                SHARE YOUR PROMOTIONAL POSTER
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed text-ivory-muted">
                Download or share your custom &ldquo;Invitation Secured&rdquo; graphic on WhatsApp Status, Instagram Stories, or social feeds. Your official admission pass remains separate in your email.
              </p>
            </div>

            {/* Privacy Controls */}
            <div className="space-y-4 rounded-md border border-champagne/20 bg-midnight/80 p-4">
              <label className="flex cursor-pointer items-start justify-between gap-4">
                <div>
                  <span className="block text-sm font-semibold text-ivory">
                    Include my nickname on shared artwork
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-ivory-muted">
                    Enabling displays &ldquo;{receipt.nickname}&rdquo; publicly on your promotional graphic and share webpage. Already downloaded or posted images cannot be remotely removed.
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={receipt.show_nickname_publicly}
                  disabled={savingPref}
                  onChange={(e) => void updatePreference({ show_nickname_publicly: e.target.checked })}
                  className="mt-1 h-5 w-5 shrink-0 accent-burnt"
                />
              </label>

              <hr className="border-champagne/15" />

              <label className="flex cursor-pointer items-start justify-between gap-4">
                <div>
                  <span className="block text-sm font-semibold text-ivory">
                    Enable public shareable webpage
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-ivory-muted">
                    Allows friends to view your Invitation Secured announcement link. Turn off anytime to deactivate the link.
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={receipt.public_sharing_enabled}
                  disabled={savingPref}
                  onChange={(e) => void updatePreference({ public_sharing_enabled: e.target.checked })}
                  className="mt-1 h-5 w-5 shrink-0 accent-burnt"
                />
              </label>
            </div>

            {feedbackMsg && (
              <p role="status" className="text-xs font-medium text-amber">
                {feedbackMsg}
              </p>
            )}

            {/* Download & Share Buttons (artwork actions disabled until ready; share link independent) */}
            <div className="flex flex-wrap gap-3">
              <Button
                size="md"
                disabled={!artworkReady}
                onClick={() => artwork.triggerDownload(`drip-and-rhythm-${selectedFormat}.png`)}
              >
                <Download className="h-4 w-4" aria-hidden="true" />
                Download {selectedFormat} PNG
              </Button>
              <Button
                variant="secondary"
                size="md"
                disabled={!artworkReady}
                loading={sharingBusy}
                onClick={() => void handleNativeShareArtwork()}
              >
                <Share2 className="h-4 w-4" aria-hidden="true" />
                Share Artwork
              </Button>
              {receipt.share_url && (
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => void copyText("share-url", receipt.share_url!)}
                >
                  {copiedKey === "share-url" ? (
                    <Check className="h-4 w-4 text-status-ok" aria-hidden="true" />
                  ) : (
                    <Copy className="h-4 w-4" aria-hidden="true" />
                  )}
                  {copiedKey === "share-url" ? "Copied Share Link" : "Copy Share Webpage"}
                </Button>
              )}
            </div>

            {/* Prepared Social Captions */}
            <div>
              <h3 className="text-xs font-semibold text-champagne uppercase">
                Prepared Social Captions
              </h3>
              <div className="mt-2.5 space-y-2.5">
                {PREPARED_CAPTIONS.map((caption, index) => {
                  const key = `caption-${index}`;
                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between gap-3 rounded border border-champagne/20 bg-midnight/75 p-3 text-xs text-ivory"
                    >
                      <span className="leading-relaxed">{caption}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void copyText(key, caption)}
                        className="shrink-0"
                      >
                        {copiedKey === key ? "Copied" : "Copy"}
                      </Button>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* WhatsApp Concierge Support */}
            {receipt.event.reservation_contacts.length > 0 && (
              <div className="border-t border-champagne/15 pt-4 text-xs text-ivory-muted">
                <p className="mb-1.5 text-champagne">Questions or table inquiries? Chat on WhatsApp:</p>
                <WhatsAppContactLinks event={receipt.event} variant="inline" />
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
