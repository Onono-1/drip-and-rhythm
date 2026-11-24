import type { Metadata } from "next";
import Link from "next/link";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { WhatsAppContactLinks } from "@/components/brand/whatsapp-contacts";
import { Button } from "@/components/ui/primitives";
import { fetchPublicEventServer } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Privacy & Guest Data Notice",
  robots: { index: false, follow: false },
};

export default async function PrivacyPage() {
  const event = await fetchPublicEventServer();

  return (
    <div className="min-h-dvh bg-midnight text-ivory">
      <header className="border-b border-champagne/15 bg-midnight/95">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4 sm:px-8">
          <Link href="/">
            <OrganizerWordmark organizers={event.organizers} />
          </Link>
          <Link href="/">
            <Button variant="outline" size="sm">
              Back to Event
            </Button>
          </Link>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-4xl px-6 py-14 sm:px-8 sm:py-20">
        <p className="font-script text-3xl text-amber">Guest Privacy</p>
        <h1 className="font-display mt-1 text-4xl tracking-wide text-ivory uppercase sm:text-5xl">
          PRIVACY &amp; INVITATION DATA NOTICE
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-ivory-muted sm:text-base">
          DRIP &amp; RHYTHM collects the minimum information required to issue your single-use admission pass and verify entry at the door.
        </p>

        <div className="mt-10 space-y-8 divide-y divide-champagne/15 border-t border-champagne/20 pt-8 text-sm leading-relaxed text-ivory-muted">
          <section className="pt-2">
            <h2 className="font-display text-xl tracking-wide text-champagne uppercase">
              What Information Is Collected
            </h2>
            <p className="mt-2">
              When you claim a valid invitation link, we collect only your chosen <strong className="text-ivory">nickname</strong> (1–50 characters) and <strong className="text-ivory">email address</strong>. We do not collect legal names, phone numbers, physical addresses, dates of birth, or guest passwords.
            </p>
          </section>

          <section className="pt-8">
            <h2 className="font-display text-xl tracking-wide text-champagne uppercase">
              Why It Is Collected &amp; How Invitations Are Delivered
            </h2>
            <p className="mt-2">
              Your nickname personalizes your invitation and your email address ensures one invitation per email and delivers your official PDF admission pass containing your unique admission QR code. We do not run third-party advertising trackers on private invitation pages.
            </p>
          </section>

          <section className="pt-8">
            <h2 className="font-display text-xl tracking-wide text-champagne uppercase">
              Admission Verification &amp; Security Scope
            </h2>
            <p className="mt-2">
              Your admission QR code contains an opaque, single-use cryptographic token rather than your email address or nickname. At the party entrance, authorized event staff scan this token to verify invitation validity and record a single check-in. Email uniqueness prevents duplicate claims per address; guests remain responsible for keeping their unused claim link and PDF QR pass confidential.
            </p>
          </section>

          <section className="pt-8">
            <h2 className="font-display text-xl tracking-wide text-champagne uppercase">
              Optional Public Nickname Visibility
            </h2>
            <p className="mt-2">
              Promotional &ldquo;Invitation Secured&rdquo; social graphics default to <strong className="text-ivory">anonymous</strong>. Your nickname is included on shared promotional graphics or your public sharing page only if you explicitly enable that option. Note that once you download or post an image to external social platforms, external copies and social platform caches cannot be remotely deleted.
            </p>
          </section>

          <section className="pt-8">
            <h2 className="font-display text-xl tracking-wide text-champagne uppercase">
              Data Retention, Assistance &amp; Removal Requests
            </h2>
            <p className="mt-2">
              Invitation and check-in records are retained only for event operations and post-event reconciliation, after which an authorized super administrator executes controlled post-event data cleanup. To request email correction, invitation revocation, or removal of your guest details, contact the organizers on WhatsApp:{" "}
              <WhatsAppContactLinks event={event} variant="inline" />.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
