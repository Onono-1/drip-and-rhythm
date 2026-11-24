import { ArrowUpRight } from "lucide-react";

import { getWhatsAppContactLinks } from "@/lib/whatsapp";
import type { PublicEvent } from "@/types/api";

export function WhatsAppGlyph({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.26-1.38a9.9 9.9 0 0 0 4.78 1.22h.01c5.46 0 9.91-4.45 9.91-9.91A9.85 9.85 0 0 0 12.04 2Zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23a8.2 8.2 0 0 1 8.22 8.24c0 4.54-3.7 8.23-8.22 8.23Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.12-.16.25-.64.81-.78.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-2-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.5.11-.11.25-.29.37-.43.12-.15.16-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.4-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.28Z" />
    </svg>
  );
}
export function WhatsAppContactLinks({
  event,
  variant = "pills",
  className = "",
}: {
  event: Pick<
    PublicEvent,
    "name" | "event_date" | "reservation_contacts" | "reservation_contact_links"
  >;
  variant?: "cards" | "pills" | "inline";
  className?: string;
}) {
  const links = getWhatsAppContactLinks(event);
  if (links.length === 0) return null;

  if (variant === "cards") {
    return (
      <ul className={`flex w-full flex-col gap-3 ${className}`}>
        {links.map((contact) => (
          <li key={contact.display}>
            <a
              href={contact.whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Chat on WhatsApp with ${contact.display}`}
              className="group flex items-center gap-4 rounded-lg border border-champagne/25 bg-midnight/80 p-3.5 transition-all duration-200 hover:border-amber/70 hover:bg-midnight focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber sm:p-4"
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-burnt/40 bg-burnt/15 text-sunset transition-colors group-hover:bg-burnt group-hover:text-ivory">
                <WhatsAppGlyph className="h-5 w-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-display text-2xl leading-none tracking-wider text-ivory tabular-nums">
                  {contact.display}
                </span>
                <span className="mt-1 block text-xs font-medium text-champagne/80">
                  Chat on WhatsApp
                </span>
              </span>
              <ArrowUpRight
                className="h-4 w-4 shrink-0 text-champagne/60 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-amber"
                aria-hidden="true"
              />
            </a>
          </li>
        ))}
      </ul>
    );
  }
  if (variant === "inline") {
    return (
      <span className={`inline-flex flex-wrap items-center gap-x-2 gap-y-1 ${className}`}>
        {links.map((contact, idx) => (
          <span key={contact.display} className="inline-flex items-center gap-2">
            {idx > 0 && (
              <span className="text-champagne/50" aria-hidden="true">
                ·
              </span>
            )}
            <a
              href={contact.whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-semibold text-amber underline decoration-amber/60 underline-offset-2 hover:text-ivory"
            >
              <WhatsAppGlyph className="h-3.5 w-3.5 shrink-0" />
              <span>{contact.display}</span>
            </a>
          </span>
        ))}
      </span>
    );
  }

  return (
    <div className={`flex flex-wrap items-center justify-center gap-2 ${className}`}>
      {links.map((contact) => (
        <a
          key={contact.display}
          href={contact.whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`Message ${contact.display} on WhatsApp`}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-md border border-champagne/25 bg-midnight/85 px-3 py-1.5 text-xs font-semibold text-champagne transition-colors hover:border-amber hover:text-ivory"
        >
          <WhatsAppGlyph className="h-3.5 w-3.5 text-sunset" />
          <span>{contact.display}</span>
        </a>
      ))}
    </div>
  );
}
