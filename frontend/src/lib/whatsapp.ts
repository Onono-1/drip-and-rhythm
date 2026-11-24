import { formatEventDate } from "@/lib/api-client";
import type { PublicEvent } from "@/types/api";

export interface WhatsAppContactLink {
  display: string;
  whatsappUrl: string;
}

export function normalizeWhatsAppDigits(rawPhone: string, defaultCountryCode = "256"): string {
  const cleaned = rawPhone.trim().replace(/[^\d+]/g, "");
  if (!cleaned) return "";
  if (cleaned.startsWith("+")) {
    return cleaned.slice(1).replace(/\D/g, "");
  }
  if (cleaned.startsWith("00")) {
    return cleaned.slice(2).replace(/\D/g, "");
  }
  const digits = cleaned.replace(/\D/g, "");
  if (digits.startsWith("0") && digits.length === 10) {
    return `${defaultCountryCode}${digits.slice(1)}`;
  }
  if (digits.length === 9 && digits.startsWith("7")) {
    return `${defaultCountryCode}${digits}`;
  }
  return digits;
}

export function buildWhatsAppInquiryMessage(
  event: Pick<PublicEvent, "name" | "event_date">,
): string {
  const name = event.name || "DRIP & RHYTHM";
  const dateStr = formatEventDate(event.event_date);
  return `Hello, I would like to inquire about ${name} on ${dateStr}.`;
}

export function buildWhatsAppUrl(
  rawPhone: string,
  event: Pick<PublicEvent, "name" | "event_date">,
): string {
  const digits = normalizeWhatsAppDigits(rawPhone);
  if (!digits) return "";
  const message = buildWhatsAppInquiryMessage(event);
  return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;
}

export function getWhatsAppContactLinks(
  event: Pick<PublicEvent, "name" | "event_date" | "reservation_contacts" | "reservation_contact_links">,
): WhatsAppContactLink[] {
  if (event.reservation_contact_links && event.reservation_contact_links.length > 0) {
    return event.reservation_contact_links.map((item) => ({
      display: item.display,
      whatsappUrl: item.whatsapp_url,
    }));
  }

  return (event.reservation_contacts || [])
    .map((raw) => raw.trim())
    .filter(Boolean)
    .map((display) => ({
      display,
      whatsappUrl: buildWhatsAppUrl(display, event),
    }))
    .filter((item) => Boolean(item.whatsappUrl));
}
