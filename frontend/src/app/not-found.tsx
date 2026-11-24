import Link from "next/link";

import { OrganizerWordmark } from "@/components/brand/organizer-wordmark";
import { Button } from "@/components/ui/primitives";

export default function NotFound() {
  return (
    <main
      id="main-content"
      className="amber-stage-glow film-grain flex min-h-dvh flex-col items-center justify-center px-6 py-20 text-center"
    >
      <OrganizerWordmark />
      <p className="font-script mt-4 text-4xl text-amber">Private Party</p>
      <h1 className="font-display mt-2 text-5xl tracking-wide text-ivory sm:text-7xl">
        PAGE NOT ON THE LIST
      </h1>
      <p className="mt-4 max-w-md text-sm leading-relaxed text-ivory-muted sm:text-base">
        The link you followed could not be found. If you received a private invitation link, check that the complete URL was copied accurately.
      </p>
      <div className="mt-8">
        <Link href="/">
          <Button size="lg">Return to DRIP &amp; RHYTHM</Button>
        </Link>
      </div>
    </main>
  );
}
