from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import qrcode
from django.conf import settings
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from apps.events.contacts import build_whatsapp_contact_links

# Compact, balanced VIP admission pass dimensions (mobile + printable single page)
PASS_WIDTH = 420.0
PASS_HEIGHT = 608.0

HEX_MIDNIGHT = HexColor("#190D08")
HEX_ESPRESSO = HexColor("#23110A")
HEX_CHOCOLATE = HexColor("#421509")
HEX_BURNT_ORANGE = HexColor("#E85D19")
HEX_SUNSET_ORANGE = HexColor("#FF8C32")
HEX_AMBER = HexColor("#FFBE55")
HEX_CHAMPAGNE = HexColor("#F5CE86")
HEX_IVORY = HexColor("#FFF3E0")
HEX_DEEP_RED = HexColor("#A51B12")


@lru_cache(maxsize=1)
def _register_pdf_fonts() -> dict[str, str]:
    fonts_dir = Path(settings.FONTS_DIR)
    mapping = {
        "Anton": ("Anton-Regular.ttf", "Helvetica-Bold"),
        "WindSong": ("WindSong-Medium.ttf", "Times-Italic"),
        "Montserrat": ("Montserrat-Regular.ttf", "Helvetica"),
        "MontserratSemi": ("Montserrat-SemiBold.ttf", "Helvetica-Bold"),
        "MontserratBold": ("Montserrat-Bold.ttf", "Helvetica-Bold"),
        "NotoSans": ("NotoSans-Regular.ttf", "Helvetica"),
        "NotoSansBold": ("NotoSans-Bold.ttf", "Helvetica-Bold"),
    }
    resolved: dict[str, str] = {}
    for alias, (filename, fallback) in mapping.items():
        path = fonts_dir / filename
        if path.exists():
            pdfmetrics.registerFont(TTFont(alias, str(path)))
            resolved[alias] = alias
        else:
            resolved[alias] = fallback
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    resolved["CJK"] = "HeiseiKakuGo-W5"
    return resolved


def _contains_cjk(value: str) -> bool:
    return any(
        (0x2E80 <= ord(ch) <= 0x9FFF)
        or (0xAC00 <= ord(ch) <= 0xD7AF)
        or (0xF900 <= ord(ch) <= 0xFAFF)
        for ch in value
    )


def _contains_extended_unicode(value: str) -> bool:
    return any(ord(ch) > 0x024F for ch in value)


def build_qr_payload(raw_admission_token: str) -> str:
    return f"DRIP1:{raw_admission_token}"


def generate_qr_png_bytes(qr_payload: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=12,
        border=4,
    )
    qr.add_data(qr_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _wrap_pdf_text(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return [text]
    lines: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current.strip())
            current = ch
    if current.strip():
        lines.append(current.strip())
    return lines[:2]


def generate_admission_pass_pdf(*, invitation, raw_admission_token: str) -> tuple[str, bytes]:
    fonts = _register_pdf_fonts()
    event = invitation.event
    qr_payload = build_qr_payload(raw_admission_token)
    qr_png = generate_qr_png_bytes(qr_payload)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PASS_WIDTH, PASS_HEIGHT))
    c.setTitle(f"{event.name} — Official Admission Pass ({invitation.reference})")
    c.setAuthor(event.organizers)

    # Full Midnight Brown luxury canvas
    c.setFillColor(HEX_MIDNIGHT)
    c.rect(0, 0, PASS_WIDTH, PASS_HEIGHT, stroke=0, fill=1)

    # Top Dark Chocolate hero header band
    header_h = 166.0
    header_y = PASS_HEIGHT - 16.0 - header_h
    c.setFillColor(HEX_CHOCOLATE)
    c.roundRect(16, header_y, PASS_WIDTH - 32, header_h, 10, stroke=0, fill=1)

    # Outer champagne gold & subtle inner burnt-orange framing
    c.setStrokeColor(HEX_CHAMPAGNE)
    c.setLineWidth(1.5)
    c.roundRect(16, 16, PASS_WIDTH - 32, PASS_HEIGHT - 32, 10, stroke=1, fill=0)
    c.setStrokeColor(Color(0.91, 0.36, 0.10, alpha=0.48))
    c.setLineWidth(0.75)
    c.roundRect(22, 22, PASS_WIDTH - 44, PASS_HEIGHT - 44, 8, stroke=1, fill=0)

    # Prominent framed event poster on right of header band
    poster_size = 112.0
    poster_x = PASS_WIDTH - 32.0 - poster_size
    poster_y = header_y + (header_h - poster_size) / 2.0
    poster_path = Path(settings.POSTER_IMAGE_PATH)
    if poster_path.exists():
        c.setFillColor(HEX_MIDNIGHT)
        c.rect(poster_x - 3, poster_y - 3, poster_size + 6, poster_size + 6, stroke=0, fill=1)
        c.drawImage(
            ImageReader(str(poster_path)),
            poster_x,
            poster_y,
            width=poster_size,
            height=poster_size,
            preserveAspectRatio=True,
            mask="auto",
        )
        c.setStrokeColor(HEX_AMBER)
        c.setLineWidth(1.2)
        c.rect(poster_x, poster_y, poster_size, poster_size, stroke=1, fill=0)

    # Header left typography column
    left_x = 34.0
    c.setFillColor(HEX_CHAMPAGNE)
    c.setFont(fonts["MontserratSemi"], 8.0)
    c.drawString(left_x, PASS_HEIGHT - 40, (event.organizers or "AFTER DARK EVENTS × HYPE DISTRICT").upper())

    c.setFillColor(HEX_IVORY)
    c.setFont(fonts["Anton"], 32)
    c.drawString(left_x, PASS_HEIGHT - 77, event.name.upper())

    c.setFillColor(HEX_AMBER)
    c.setFont(fonts["WindSong"], 21)
    c.drawString(left_x + 2, PASS_HEIGHT - 102, event.subtitle or "Private Party")

    c.setFillColor(HEX_CHAMPAGNE)
    c.setFont(fonts["Montserrat"], 8.5)
    c.drawString(left_x, PASS_HEIGHT - 122, event.tagline)

    # Exclusive Admission Pass + 18+ badges
    badge_y = PASS_HEIGHT - 156
    c.setFillColor(HEX_BURNT_ORANGE)
    c.roundRect(left_x, badge_y, 168, 20, 4, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont(fonts["MontserratBold"], 8.2)
    c.drawCentredString(left_x + 84, badge_y + 6.8, "EXCLUSIVE ADMISSION PASS")

    c.setFillColor(HEX_DEEP_RED)
    c.roundRect(left_x + 174, badge_y, 40, 20, 4, stroke=0, fill=1)
    c.setFillColor(HEX_IVORY)
    c.setFont(fonts["MontserratBold"], 8.2)
    c.drawCentredString(left_x + 194, badge_y + 6.8, event.age_restriction or "18+")

    # Unified Event & Guest Details Card (eliminates dead vertical gaps)
    card_x = 30.0
    card_w = PASS_WIDTH - 60.0
    card_h = 152.0
    card_y = header_y - 14.0 - card_h
    c.setFillColor(HEX_ESPRESSO)
    c.roundRect(card_x, card_y, card_w, card_h, 8, stroke=0, fill=1)
    c.setStrokeColor(Color(0.96, 0.81, 0.53, alpha=0.32))
    c.setLineWidth(0.9)
    c.roundRect(card_x, card_y, card_w, card_h, 8, stroke=1, fill=0)

    inner_x = card_x + 14.0
    inner_right = card_x + card_w - 14.0

    # Date & Time row
    y = card_y + card_h - 18.0
    c.setFillColor(HEX_AMBER)
    c.setFont(fonts["MontserratBold"], 7.5)
    c.drawString(inner_x, y, "DATE")
    c.drawString(inner_x + 168, y, "TIME")

    y -= 14.0
    c.setFillColor(HEX_IVORY)
    c.setFont(fonts["MontserratSemi"], 10.2)
    date_label = f"{event.event_date.day} {event.event_date.strftime('%B %Y')}"
    c.drawString(inner_x, y, date_label)
    if event.start_time:
        time_str = event.start_time.strftime("%I:%M %p").lstrip("0")
        if event.end_time:
            time_str += f" – {event.end_time.strftime('%I:%M %p').lstrip('0')}"
    else:
        time_str = "To be announced"
    c.drawString(inner_x + 168, y, time_str)

    # Location & Venue row
    y -= 18.0
    c.setFillColor(HEX_AMBER)
    c.setFont(fonts["MontserratBold"], 7.5)
    c.drawString(inner_x, y, "LOCATION & VENUE")
    y -= 13.0
    c.setFillColor(HEX_IVORY)
    c.setFont(fonts["MontserratSemi"], 9.5)
    venue_part = event.exact_venue.strip() if event.exact_venue.strip() else "Venue to be announced"
    venue_line = f"{event.location} · {venue_part}"
    for vline in _wrap_pdf_text(venue_line, fonts["MontserratSemi"], 9.5, card_w - 28):
        c.drawString(inner_x, y, vline)
        y -= 12.0

    # Burnt-orange divider inside card
    div_y = card_y + 62.0
    c.setStrokeColor(HEX_BURNT_ORANGE)
    c.setLineWidth(0.9)
    c.line(inner_x, div_y, inner_right, div_y)

    # Guest Identity & Random Unique Reference row
    gy = div_y - 14.0
    c.setFillColor(HEX_AMBER)
    c.setFont(fonts["MontserratBold"], 7.5)
    c.drawString(inner_x, gy, "INVITED GUEST")
    c.drawRightString(inner_right, gy, "INVITATION REF")

    gy -= 17.0
    if _contains_cjk(invitation.nickname):
        nick_font = fonts["CJK"]
    elif _contains_extended_unicode(invitation.nickname):
        nick_font = fonts["NotoSansBold"]
    else:
        nick_font = fonts["MontserratBold"]

    ref_width = pdfmetrics.stringWidth(invitation.reference, fonts["MontserratBold"], 12.0)
    nick_max_w = card_w - 28.0 - ref_width - 14.0
    nick_size = 13.5 if pdfmetrics.stringWidth(invitation.nickname, nick_font, 13.5) <= nick_max_w else 11.5
    nick_lines = _wrap_pdf_text(invitation.nickname, nick_font, nick_size, nick_max_w)

    c.setFillColor(HEX_IVORY)
    c.setFont(nick_font, nick_size)
    c.drawString(inner_x, gy, nick_lines[0])

    c.setFillColor(HEX_CHAMPAGNE)
    c.setFont(fonts["MontserratBold"], 12.0)
    c.drawRightString(inner_right, gy + 0.5, invitation.reference)

    if len(nick_lines) > 1:
        gy -= 13.0
        c.setFillColor(HEX_IVORY)
        c.setFont(nick_font, max(10.5, nick_size - 1.0))
        c.drawString(inner_x, gy, nick_lines[1])

    email_y = card_y + 11.0
    c.setFillColor(HEX_CHAMPAGNE)
    c.setFont(fonts["Montserrat"], 8.6)
    c.drawString(inner_x, email_y, invitation.guest_email)

    # High-Contrast Scannable QR Code Zone (tightly connected below guest details)
    qr_card_size = 160.0
    qr_x = (PASS_WIDTH - qr_card_size) / 2.0
    qr_y = card_y - 16.0 - qr_card_size

    c.setFillColor(white)
    c.roundRect(qr_x, qr_y, qr_card_size, qr_card_size, 8, stroke=0, fill=1)
    c.setStrokeColor(HEX_AMBER)
    c.setLineWidth(2.0)
    c.roundRect(qr_x, qr_y, qr_card_size, qr_card_size, 8, stroke=1, fill=0)

    c.drawImage(
        ImageReader(io.BytesIO(qr_png)),
        qr_x + 7,
        qr_y + 7,
        width=qr_card_size - 14,
        height=qr_card_size - 14,
        preserveAspectRatio=True,
    )

    # Admission Instructions & Clickable WhatsApp Concierge Footer
    inst_y = qr_y - 16.0
    c.setFillColor(HEX_IVORY)
    c.setFont(fonts["MontserratSemi"], 8.8)
    c.drawCentredString(PASS_WIDTH / 2.0, inst_y, "Present this invitation at the entrance for verification.")

    c.setFillColor(HEX_SUNSET_ORANGE)
    c.setFont(fonts["MontserratBold"], 8.2)
    c.drawCentredString(
        PASS_WIDTH / 2.0,
        inst_y - 14.0,
        "VALID FOR ONE ADMISSION ONLY · DO NOT SHARE THIS QR PASS",
    )

    c.setFillColor(HEX_CHAMPAGNE)
    c.setFont(fonts["Montserrat"], 7.4)
    c.drawCentredString(
        PASS_WIDTH / 2.0,
        inst_y - 28.0,
        f"Your invitation to {event.name} is officially secured. Strictly {event.age_restriction}. Please drink responsibly.",
    )

    # Clickable WhatsApp reservation links with actual PDF URI link annotations
    contact_links = build_whatsapp_contact_links(event)
    if contact_links:
        wa_y = 30.0
        prefix = "WhatsApp Reservations: "
        sep = "  ·  "
        font_name = fonts["MontserratSemi"]
        font_size = 7.8

        total_w = pdfmetrics.stringWidth(prefix, fonts["Montserrat"], font_size)
        for idx, item in enumerate(contact_links):
            if idx > 0:
                total_w += pdfmetrics.stringWidth(sep, fonts["Montserrat"], font_size)
            total_w += pdfmetrics.stringWidth(item["display"], font_name, font_size)

        cur_x = (PASS_WIDTH - total_w) / 2.0
        c.setFillColor(HEX_CHAMPAGNE)
        c.setFont(fonts["Montserrat"], font_size)
        c.drawString(cur_x, wa_y, prefix)
        cur_x += pdfmetrics.stringWidth(prefix, fonts["Montserrat"], font_size)

        for idx, item in enumerate(contact_links):
            if idx > 0:
                c.setFillColor(HEX_CHAMPAGNE)
                c.setFont(fonts["Montserrat"], font_size)
                c.drawString(cur_x, wa_y, sep)
                cur_x += pdfmetrics.stringWidth(sep, fonts["Montserrat"], font_size)

            label = item["display"]
            label_w = pdfmetrics.stringWidth(label, font_name, font_size)
            c.setFillColor(HEX_AMBER)
            c.setFont(font_name, font_size)
            c.drawString(cur_x, wa_y, label)
            # Subtle underline indicating clickable WhatsApp link
            c.setStrokeColor(HEX_AMBER)
            c.setLineWidth(0.55)
            c.line(cur_x, wa_y - 1.5, cur_x + label_w, wa_y - 1.5)
            c.linkURL(
                item["whatsapp_url"],
                (cur_x - 2, wa_y - 3, cur_x + label_w + 2, wa_y + font_size + 2),
                relative=0,
            )
            cur_x += label_w

    c.showPage()
    c.save()

    filename = f"DRIP-AND-RHYTHM-{invitation.reference}.pdf"
    return filename, buf.getvalue()
