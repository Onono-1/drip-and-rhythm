from __future__ import annotations

import re
from urllib.parse import quote


def normalize_whatsapp_digits(raw_phone: str, *, default_country_code: str = "256") -> str:
    """Normalize a local Ugandan or international phone number into wa.me digits (no '+')."""
    cleaned = re.sub(r"[^\d+]", "", (raw_phone or "").strip())
    if not cleaned:
        return ""
    if cleaned.startswith("+"):
        return re.sub(r"\D", "", cleaned[1:])
    if cleaned.startswith("00"):
        return re.sub(r"\D", "", cleaned[2:])
    digits = re.sub(r"\D", "", cleaned)
    if digits.startswith("0") and len(digits) == 10:
        return f"{default_country_code}{digits[1:]}"
    if len(digits) == 9 and digits.startswith("7"):
        return f"{default_country_code}{digits}"
    return digits


def format_event_inquiry_date(event) -> str:
    """Format event date as e.g. '5 December 2026' without leading zero."""
    return f"{event.event_date.day} {event.event_date.strftime('%B %Y')}"


def build_whatsapp_inquiry_message(event) -> str:
    event_name = getattr(event, "name", "DRIP & RHYTHM") or "DRIP & RHYTHM"
    date_str = format_event_inquiry_date(event)
    return f"Hello, I would like to inquire about {event_name} on {date_str}."


def build_whatsapp_url(raw_phone: str, *, event) -> str:
    digits = normalize_whatsapp_digits(raw_phone)
    if not digits:
        return ""
    message = build_whatsapp_inquiry_message(event)
    return f"https://wa.me/{digits}?text={quote(message, safe='')}"


def build_whatsapp_contact_links(event) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for raw in event.reservation_contacts or []:
        display = str(raw).strip()
        if not display:
            continue
        url = build_whatsapp_url(display, event=event)
        if url:
            links.append({"display": display, "whatsapp_url": url})
    return links
