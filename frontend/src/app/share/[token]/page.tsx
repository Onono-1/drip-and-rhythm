import { Calendar, MapPin, RefreshCw, Sparkles } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { WhatsAppContactLinks } from "@/components/brand/whatsapp-contacts";
import { Button } from "@/components/ui/primitives";
import { PublicShareArtworkShowcase } from "@/features/guest/public-share-actions";
import { formatEventDate } from "@/lib/api-client";
import {
  fetchPublicShareServer,
  getFallbackPublicEvent,
  getPublicSiteUrl,
} from "@/lib/server-api";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const siteUrl = getPublicSiteUrl();
  const res = await fetchPublicShareServer(token);

  if (!res.ok || !res.data) {
    return {
      title:
        res.status >= 500
          ? "DRIP & RHYTHM — Shared Invitation"
          : "Shared Invitation Unavailable",
      robots: { index: false, follow: false },
    };
  }

  const { event, nickname, sharing_version } = res.data;
  const title = nickname
    ? `${nickname} is on the list — ${event.name}`
    : `The Invitation is Secured — ${event.name}`;
  const description = `${event.tagline}. ${formatEventDate(event.event_date)} · ${event.location}. ${event.hashtag}`;
  const ogImageUrl = `${siteUrl}/api/share/${encodeURIComponent(token)}/image/?format=preview&v=${sharing_version}`;
  const canonicalUrl = `${siteUrl}/share/${encodeURIComponent(token)}`;

  return {
    title,
    description,
    alternates: { canonical: canonicalUrl },
    robots: { index: false, follow: false },
    openGraph: {
      title,
      description,
      url: canonicalUrl,
      siteName: event.name,
      type: "website",
      images: [
        {
          url: ogImageUrl,
          width: 1200,
          height: 630,
          alt: `${event.name} — Invitation Secured`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImageUrl],
    },
  };
}

export default async function PublicSharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const res = await fetchPublicShareServer(token);

  if (!res.ok || !res.data) {
    const fallbackEvent = getFallbackPublicEvent();
    const isTransientFailure = res.status >= 500;

    if (isTransientFailure) {
      return (
        <div className="amber-stage-glow film-grain flex min-h-dvh flex-col items-center justify-center px-6 py-20 text-center">
          <OrganizerWordmark organizers={fallbackEvent.organizers} />
          <h1 className="font-display mt-5 text-4xl tracking-wide text-ivory uppercase sm:text-5xl">
            MOMENTARILY BUSY
          </h1>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-ivory-muted sm:text-base">
            We couldn&apos;t load this shared invitation page right now. Your invitation remains secured — refresh in a moment to view the page.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <a href={`/share/${encodeURIComponent(token)}`}>
              <Button>
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Try Again
              </Button>
            </a>
            <Link href="/">
              <Button variant="outline">Explore DRIP &amp; RHYTHM</Button>
            </Link>
          </div>
        </div>
      );
    }

    return (
      <div className="amber-stage-glow film-grain flex min-h-dvh flex-col items-center justify-center px-6 py-20 text-center">
        <OrganizerWordmark organizers={fallbackEvent.organizers} />
        <h1 className="font-display mt-5 text-4xl tracking-wide text-ivory uppercase sm:text-5xl">
          SHARING PAGE UNAVAILABLE
        </h1>
        <p className="mt-3 max-w-md text-sm leading-relaxed text-ivory-muted sm:text-base">
          This shared promotional page is no longer active or has been made private.
        </p>
        {fallbackEvent.reservation_contacts.length > 0 && (
          <div className="mt-6 space-y-2">
            <p className="text-xs text-champagne">Event Inquiries (WhatsApp):</p>
            <WhatsAppContactLinks event={fallbackEvent} variant="pills" />
          </div>
        )}
        <div className="mt-8">
          <Link href="/">
            <Button>Explore DRIP &amp; RHYTHM</Button>
          </Link>
        </div>
      </div>
    );
  }

  const { event, nickname } = res.data;
  const formattedDate = formatEventDate(event.event_date);

  return (
    <div className="amber-stage-glow film-grain flex min-h-dvh flex-col justify-between">
      <header className="border-b border-champagne/15 bg-midnight/90">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Link href="/">
            <OrganizerWordmark organizers={event.organizers} />
          </Link>
          <Link href="/">
            <Button variant="outline" size="sm">
              Event Details
            </Button>
          </Link>
        </div>
      </header>

      <main id="main-content" className="mx-auto w-full max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
        <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-12 lg:gap-12">
          {/* Artwork Focal Point (Primary Visual Centerpiece) */}
          <div className="order-1 lg:order-2 lg:col-span-7">
            <PublicShareArtworkShowcase payload={res.data} />
          </div>

          {/* Balanced Editorial Event Details */}
          <div className="order-2 space-y-6 lg:order-1 lg:col-span-5">
            <div>
              <div className="inline-flex items-center gap-2 text-xs font-semibold text-amber">
                <Sparkles className="h-4 w-4 text-burnt" aria-hidden="true" />
                <span>{event.hashtag} · Invitation Only ({event.age_restriction})</span>
              </div>
              <p className="font-script mt-3 text-3xl text-amber sm:text-4xl">{event.subtitle}</p>
              <h1 className="font-display mt-1 text-4xl leading-[1.02] tracking-wide text-ivory uppercase sm:text-5xl">
                THE INVITATION IS SECURED.
              </h1>
              {nickname && (
                <p className="mt-3 text-lg font-semibold text-champagne">
                  {nickname} is officially on the list for {event.name}.
                </p>
              )}
              <p className="mt-3 text-sm leading-relaxed text-ivory-muted sm:text-base">
                {event.tagline}. See you on {formattedDate} in {event.location}.
              </p>
            </div>

            <dl className="space-y-3 rounded-lg border border-champagne/20 bg-espresso/85 p-5 text-sm">
              <div className="flex items-start gap-3">
                <Calendar className="mt-0.5 h-4 w-4 shrink-0 text-amber" aria-hidden="true" />
                <div>
                  <dt className="text-xs font-semibold text-champagne">Date &amp; Time</dt>
                  <dd className="text-ivory">
                    {formattedDate}
                    {event.start_time ? ` · ${event.start_time.slice(0, 5)}` : ""}
                  </dd>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-amber" aria-hidden="true" />
                <div>
                  <dt className="text-xs font-semibold text-champagne">Location</dt>
                  <dd className="text-ivory">
                    {event.venue_display ? `${event.venue_display}, ${event.location}` : event.location}
                  </dd>
                </div>
              </div>
            </dl>

            <p className="text-xs leading-relaxed text-ivory-muted">
              Promotional announcement only — an official private invitation pass is required for entry ({event.age_restriction}).
            </p>

            {event.reservation_contacts.length > 0 && (
              <div className="border-t border-champagne/15 pt-4">
                <p className="mb-2 text-xs font-semibold text-champagne">
                  Table Reservations &amp; Inquiries (WhatsApp)
                </p>
                <WhatsAppContactLinks event={event} variant="inline" />
              </div>
            )}
          </div>
        </div>
      </main>

      <footer className="border-t border-champagne/15 py-5 text-center text-xs text-ivory-muted">
        <p>
          {event.organizers} · {event.name} · {event.hashtag}
        </p>
      </footer>
    </div>
  );
}
