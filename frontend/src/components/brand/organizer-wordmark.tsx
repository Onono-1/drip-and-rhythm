import { clsx } from "clsx";

/**
 * Typographic organizer wordmark structured so standalone official vector SVGs
 * can drop into `afterDarkLogoUrl` / `hypeDistrictLogoUrl` later without redesign.
 */
export function OrganizerWordmark({
  organizers = "After Dark Events × Hype District",
  className,
  afterDarkLogoUrl,
  hypeDistrictLogoUrl,
}: {
  organizers?: string;
  className?: string;
  afterDarkLogoUrl?: string;
  hypeDistrictLogoUrl?: string;
}) {
  if (afterDarkLogoUrl && hypeDistrictLogoUrl) {
    return (
      <div className={clsx("inline-flex items-center gap-4", className)}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={afterDarkLogoUrl} alt="After Dark Events" className="h-7 w-auto object-contain" />
        <span className="text-amber/70 font-sans text-xs" aria-hidden="true">
          ×
        </span>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={hypeDistrictLogoUrl} alt="Hype District" className="h-7 w-auto object-contain" />
      </div>
    );
  }

  const parts = organizers.split("×").map((p) => p.trim());
  if (parts.length === 2) {
    return (
      <div
        className={clsx(
          "inline-flex flex-wrap items-center gap-2.5 text-xs font-semibold tracking-[0.18em] text-champagne uppercase",
          className,
        )}
      >
        <span>{parts[0]}</span>
        <span className="text-burnt font-bold" aria-hidden="true">
          ×
        </span>
        <span>{parts[1]}</span>
      </div>
    );
  }

  return (
    <span
      className={clsx(
        "inline-block text-xs font-semibold tracking-[0.18em] text-champagne uppercase",
        className,
      )}
    >
      {organizers}
    </span>
  );
}
