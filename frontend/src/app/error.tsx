"use client";

import Link from "next/link";

import { Button } from "@/components/ui/primitives";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main
      id="main-content"
      className="amber-stage-glow film-grain flex min-h-dvh flex-col items-center justify-center px-6 py-20 text-center"
    >
      <h1 className="font-display text-4xl tracking-wide text-ivory sm:text-6xl">
        MOMENTARY INTERRUPTION
      </h1>
      <p className="mt-4 max-w-md text-sm leading-relaxed text-ivory-muted sm:text-base">
        We hit an unexpected issue loading this screen. Try refreshing, or return to the event homepage.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
        <Button onClick={() => reset()}>Try again</Button>
        <Link href="/">
          <Button variant="outline">Event homepage</Button>
        </Link>
      </div>
    </main>
  );
}
