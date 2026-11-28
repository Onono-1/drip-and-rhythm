"use client";

import { Calendar, ShieldCheck, Sparkles } from "lucide-react";
import { MotionConfig, motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import Link from "next/link";
import { useEffect, useRef, useState, type PointerEvent } from "react";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { WhatsAppContactLinks } from "@/components/brand/whatsapp-contacts";
import { Button } from "@/components/ui/primitives";
import { formatEventDate } from "@/lib/api-client";
import type { PublicEvent } from "@/types/api";

function computeCountdown(event: PublicEvent, nowMs: number) {
  const [y, m, d] = event.event_date.split("-").map(Number);
  if (!y || !m || !d) return { mode: "date_only" as const, days: 0 };

  if (event.start_time) {
    const [hh = 0, mm = 0] = event.start_time.split(":").map(Number);
    // Africa/Kampala is UTC+03:00 year-round (no DST)
    const targetUtcMs = Date.UTC(y, m - 1, d, hh - 3, mm, 0);
    const diff = targetUtcMs - nowMs;
    if (diff <= 0) {
      return { mode: "concluded" as const, days: 0, hours: 0, minutes: 0, seconds: 0 };
    }
    const totalSec = Math.floor(diff / 1000);
    return {
      mode: "exact" as const,
      days: Math.floor(totalSec / 86400),
      hours: Math.floor((totalSec % 86400) / 3600),
      minutes: Math.floor((totalSec % 3600) / 60),
      seconds: totalSec % 60,
    };
  }

  // Start time not yet configured: show honest calendar days remaining in Africa/Kampala without inventing a start hour
  const kampalaNow = new Date(nowMs + 3 * 3600 * 1000);
  const todayMidnight = Date.UTC(
    kampalaNow.getUTCFullYear(),
    kampalaNow.getUTCMonth(),
    kampalaNow.getUTCDate(),
  );
  const eventMidnight = Date.UTC(y, m - 1, d);
  const dayDiff = Math.round((eventMidnight - todayMidnight) / 86_400_000);
  if (dayDiff < 0) {
    return { mode: "concluded" as const, days: 0 };
  }
  return { mode: "days_only" as const, days: dayDiff };
}

export function CinematicHomepage({ event }: { event: PublicEvent }) {
  const heroRef = useRef<HTMLElement | null>(null);
  const prefersReducedMotion = useReducedMotion();
  const [nowMs, setNowMs] = useState<number | null>(null);
  const [spot, setSpot] = useState({ x: 52, y: 38 });

  useEffect(() => {
    const initTimer = window.setTimeout(() => {
      setNowMs(Date.now());
    }, 0);
    const interval = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => {
      window.clearTimeout(initTimer);
      window.clearInterval(interval);
    };
  }, []);

  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ["start start", "end start"],
  });

  const bgPlaneY = useTransform(scrollYProgress, [0, 1], prefersReducedMotion ? [0, 0] : [0, 72]);
  const titlePlaneY = useTransform(scrollYProgress, [0, 1], prefersReducedMotion ? [0, 0] : [0, -34]);
  const posterPlaneY = useTransform(scrollYProgress, [0, 1], prefersReducedMotion ? [0, 0] : [0, -18]);

  const handleStagePointer = (e: PointerEvent<HTMLElement>) => {
    if (prefersReducedMotion) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 100);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 100);
    setSpot({ x, y });
  };

  const formattedDate = formatEventDate(event.event_date);
  const countdown = nowMs !== null ? computeCountdown(event, nowMs) : null;

  return (
    <MotionConfig reducedMotion="user">
    <div className="min-h-dvh bg-midnight text-ivory">
      {/* Top editorial navigation bar */}
      <header className="border-b border-champagne/15 bg-midnight/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4 sm:px-10">
          <OrganizerWordmark organizers={event.organizers} />
          <nav aria-label="Primary" className="flex items-center gap-5 text-xs font-semibold text-champagne">
            <a href="#access" className="hidden py-2 hover:text-ivory sm:inline-block">
              Invitation Protocol
            </a>
            <a href="#concierge" className="py-2 hover:text-ivory">
              Reservations
            </a>
            <span className="rounded border border-crimson/70 bg-crimson/25 px-2.5 py-1 text-[11px] font-bold text-ivory">
              {event.age_restriction}
            </span>
          </nav>
        </div>
      </header>

      <main id="main-content">
        {/* ACT 1: Dimensional Multi-Plane Hero */}
        <section
          ref={heroRef}
          onPointerMove={handleStagePointer}
          className="film-grain relative isolate flex min-h-[calc(100dvh-65px)] items-center overflow-hidden border-b border-champagne/15 py-12 sm:py-16 lg:py-20"
        >
          {/* Plane 1: Atmospheric warm stage light */}
          <motion.div
            aria-hidden="true"
            style={{
              y: bgPlaneY,
              background: `radial-gradient(560px circle at ${spot.x}% ${spot.y}%, rgba(232, 93, 25, 0.24), rgba(66, 21, 9, 0.14) 48%, transparent 78%)`,
            }}
            className="pointer-events-none absolute inset-0 -z-20 transition-opacity duration-300"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -top-36 right-[-10%] -z-10 h-[460px] w-[460px] rounded-full bg-burnt/18 blur-[120px]"
          />

          <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-10 px-6 sm:px-10 lg:grid-cols-12 lg:gap-12">
            {/* Plane 2 & 4: Oversized Editorial Title + Story */}
            <motion.div
              style={{ y: titlePlaneY }}
              initial={prefersReducedMotion ? false : { opacity: 0, y: 22 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
              className="lg:col-span-7"
            >
              <p className="font-script text-4xl text-amber sm:text-5xl">{event.subtitle}</p>
              <h1 className="font-display mt-1 text-[clamp(3.5rem,10vw,7.6rem)] leading-[0.9] tracking-tight text-ivory uppercase">
                {event.name}
              </h1>
              <p className="mt-5 max-w-xl font-display text-xl tracking-wide text-champagne uppercase sm:text-2xl">
                {event.tagline}.
              </p>
              <p className="mt-4 max-w-xl text-sm leading-relaxed text-ivory-muted sm:text-base">
                Where the drip meets the rhythm. One night. One experience. An exclusive celebration of high fashion, curated sound, and Kampala nightlife culture in Muyenga.
              </p>

              <dl className="mt-7 grid max-w-lg grid-cols-2 gap-4 border-y border-champagne/20 py-4 text-sm">
                <div>
                  <dt className="text-xs font-semibold text-amber">Date</dt>
                  <dd className="mt-0.5 font-semibold text-ivory">{formattedDate}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-amber">District</dt>
                  <dd className="mt-0.5 font-semibold text-ivory">{event.location}</dd>
                </div>
              </dl>

              <div className="mt-8 flex flex-col gap-3.5 sm:flex-row sm:items-center">
                <a href="#concierge" className="w-full sm:w-auto">
                  <Button size="lg" className="w-full sm:w-auto">
                    Reservation Inquiries
                  </Button>
                </a>
                <a href="#access" className="w-full sm:w-auto">
                  <Button variant="outline" size="lg" className="w-full sm:w-auto">
                    Invitation-Only Access
                  </Button>
                </a>
              </div>
            </motion.div>

            {/* Plane 3: Framed Authentic Event Poster */}
            <motion.div
              style={{ y: posterPlaneY }}
              initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.75, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto w-full max-w-md lg:col-span-5 lg:max-w-none"
            >
              <div className="group relative rounded-lg border border-champagne/40 bg-espresso p-2.5 shadow-[0_24px_80px_rgba(232,93,25,0.22)]">
                <div className="overflow-hidden rounded">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="/branding/event-poster.jpeg"
                    alt="DRIP & RHYTHM official event poster — 5 December 2026 in Muyenga, Kampala"
                    width={1024}
                    height={1024}
                    className="aspect-square h-auto w-full object-cover transition-transform duration-500 group-hover:scale-[1.02]"
                  />
                </div>
                <div className="mt-2.5 flex items-center justify-between px-1 text-xs text-champagne">
                  <span className="font-semibold">{event.hashtag}</span>
                  <span>Invitation Only · {event.age_restriction}</span>
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        {/* ACT 2: Date Monument & Honest Countdown */}
        <section
          id="date"
          className="border-b border-champagne/15 bg-espresso py-16 sm:py-24"
        >
          <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 px-6 sm:px-10 lg:grid-cols-12">
            <div className="lg:col-span-6">
              <div className="inline-flex items-center gap-2 text-xs font-semibold text-amber">
                <Calendar className="h-4 w-4 text-burnt" aria-hidden="true" />
                <span>Kampala Calendar ({event.time_zone})</span>
              </div>
              <h2 className="font-display mt-3 text-5xl tracking-wide text-ivory uppercase sm:text-6xl">
                {formattedDate}
              </h2>
              <p className="mt-3 max-w-md text-sm leading-relaxed text-ivory-muted sm:text-base">
                {event.venue_display
                  ? `Hosted at ${event.venue_display}, ${event.location}.`
                  : `Hosted in ${event.location}. Exact private venue details are shared with confirmed invitees.`}
              </p>
              <p className="mt-2 text-sm text-champagne">
                {event.start_time
                  ? `Doors: ${event.start_time.slice(0, 5)}${event.end_time ? ` – ${event.end_time.slice(0, 5)}` : ""}`
                  : "Event starting time: To be announced"}
              </p>
            </div>

            <div className="lg:col-span-6">
              <div className="rounded-lg border border-champagne/25 bg-midnight/85 p-6 sm:p-8">
                {countdown === null ? (
                  <p className="font-display text-3xl text-champagne">5 DECEMBER 2026</p>
                ) : countdown.mode === "concluded" ? (
                  <div>
                    <p className="font-display text-3xl text-amber uppercase">
                      THE NIGHT HAS ARRIVED
                    </p>
                    <p className="mt-2 text-sm text-ivory-muted">
                      Thank you to everyone who joined After Dark Events × Hype District for DRIP &amp; RHYTHM.
                    </p>
                  </div>
                ) : countdown.mode === "exact" ? (
                  <div>
                    <p className="text-xs font-semibold text-champagne">Countdown to Doors</p>
                    <div className="mt-4 grid grid-cols-4 gap-3 text-center">
                      {[
                        { label: "Days", val: countdown.days },
                        { label: "Hours", val: countdown.hours },
                        { label: "Minutes", val: countdown.minutes },
                        { label: "Seconds", val: countdown.seconds },
                      ].map((unit) => (
                        <div
                          key={unit.label}
                          className="rounded border border-champagne/20 bg-espresso/90 px-2 py-3"
                        >
                          <div className="font-display text-3xl text-ivory sm:text-4xl">
                            {String(unit.val).padStart(2, "0")}
                          </div>
                          <div className="mt-1 text-[11px] font-medium text-amber">{unit.label}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                    <div>
                      <p className="text-xs font-semibold text-amber">Days Until Event</p>
                      <p className="font-display mt-1 text-6xl leading-none text-ivory sm:text-7xl">
                        {countdown.days}
                      </p>
                    </div>
                    <p className="max-w-xs text-xs leading-relaxed text-ivory-muted">
                      Counting down calendar days in Kampala ({event.time_zone}). Exact door times will appear once announced by the organizers.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ACT 3: The Code of Entry (Exclusivity Peak) */}
        <section
          id="access"
          className="relative overflow-hidden border-b border-champagne/20 bg-chocolate py-16 sm:py-24"
        >
          <div className="mx-auto max-w-7xl px-6 sm:px-10">
            <div className="grid grid-cols-1 gap-10 lg:grid-cols-12">
              <div className="lg:col-span-5">
                <div className="inline-flex items-center gap-2 text-xs font-semibold text-amber">
                  <ShieldCheck className="h-4 w-4 text-sunset" aria-hidden="true" />
                  <span>Controlled Private Admission</span>
                </div>
                <h2 className="font-display mt-3 text-4xl leading-tight tracking-wide text-ivory uppercase sm:text-5xl">
                  STRICTLY BY PERSONAL INVITATION
                </h2>
                <p className="mt-4 text-sm leading-relaxed text-ivory/85 sm:text-base">
                  DRIP &amp; RHYTHM is not open to public ticket sales. Selected guests receive a unique, single-use invitation link directly from our hosts.
                </p>
              </div>

              <div className="divide-y divide-champagne/20 border-y border-champagne/25 lg:col-span-7">
                <div className="py-5">
                  <h3 className="font-display text-xl tracking-wide text-champagne uppercase">
                    Single-Use Personal Link
                  </h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ivory/85">
                    Open the private invitation link shared with you by an authorized host and enter your nickname and email address to claim your spot on the list.
                  </p>
                </div>
                <div className="py-5">
                  <h3 className="font-display text-xl tracking-wide text-champagne uppercase">
                    Official PDF Pass by Email
                  </h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ivory/85">
                    Once claimed, your link is permanently sealed and an official VIP PDF admission pass with your encrypted QR code is sent directly to your inbox.
                  </p>
                </div>
                <div className="py-5">
                  <h3 className="font-display text-xl tracking-wide text-champagne uppercase">
                    Verified Entrance Check-In ({event.age_restriction})
                  </h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ivory/85">
                    Present your official PDF pass at the entrance. Every QR pass is verified live against the guest registry and grants exactly one admission.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ACT 4: Reservations & Concierge */}
        <section id="concierge" className="bg-midnight py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6 sm:px-10">
            <div className="grid grid-cols-1 gap-10 rounded-lg border border-champagne/25 bg-espresso/90 p-6 sm:p-10 lg:grid-cols-12 lg:items-center">
              <div className="lg:col-span-6">
                <div className="inline-flex items-center gap-2 text-xs font-semibold text-amber">
                  <Sparkles className="h-4 w-4 text-burnt" aria-hidden="true" />
                  <span>Tables &amp; Guest Inquiries</span>
                </div>
                <h2 className="font-display mt-2 text-4xl tracking-wide text-ivory uppercase sm:text-5xl">
                  RESERVATION CONCIERGE
                </h2>
                <p className="mt-3 max-w-lg text-sm leading-relaxed text-ivory-muted sm:text-base">
                  For table reservations or direct guest inquiries regarding {event.name}, reach out directly to the {event.organizers} hospitality desk.
                </p>
              </div>

              <div className="lg:col-span-6">
                <WhatsAppContactLinks event={event} variant="cards" />
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Minimal Branded Footer */}
      <footer className="border-t border-champagne/15 bg-midnight py-10">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-6 text-xs text-ivory-muted sm:flex-row sm:items-center sm:px-10">
          <div>
            <OrganizerWordmark organizers={event.organizers} />
            <p className="mt-2">
              {event.name} · {formattedDate} · {event.location} · Strictly {event.age_restriction}. Please drink responsibly.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-6 font-medium text-champagne">
            <span>{event.hashtag}</span>
            <Link href="/privacy" className="py-1 hover:text-ivory">
              Privacy &amp; Data Notice
            </Link>
            <Link href="/admin/login" className="py-1 text-ivory-muted hover:text-ivory">
              Host Portal
            </Link>
          </div>
        </div>
      </footer>
    </div>
    </MotionConfig>
  );
}
