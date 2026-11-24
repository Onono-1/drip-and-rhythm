from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FORMAT_SPECS: dict[str, tuple[int, int]] = {
    "story": (1080, 1920),
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "preview": (1200, 630),
}

MIDNIGHT_BROWN = (25, 13, 8)
ESPRESSO = (35, 17, 10)
DARK_CHOCOLATE = (66, 21, 9)
BURNT_ORANGE = (232, 93, 25)
SUNSET_ORANGE = (255, 140, 50)
GOLDEN_AMBER = (255, 190, 85)
CHAMPAGNE_GOLD = (245, 206, 134)
WARM_IVORY = (255, 243, 224)

CJK_FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    Path(r"C:\Windows\Fonts\YuGothB.ttc"),
    Path(r"C:\Windows\Fonts\malgunbd.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
]


def _has_cjk(text: str) -> bool:
    return any(
        (0x2E80 <= ord(ch) <= 0x9FFF)
        or (0xAC00 <= ord(ch) <= 0xD7AF)
        or (0xF900 <= ord(ch) <= 0xFAFF)
        for ch in text
    )


def _needs_unicode_fallback(text: str) -> bool:
    return any(ord(ch) > 0x024F for ch in text)


@lru_cache(maxsize=64)
def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    if filename == "__CJK__":
        for cand in CJK_FONT_CANDIDATES:
            if cand.exists():
                return ImageFont.truetype(str(cand), size=size)
        filename = "NotoSans-Bold.ttf"

    font_path = Path(settings.FONTS_DIR) / filename
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size=size)
    fallback = Path(settings.FONTS_DIR) / "NotoSans-Bold.ttf"
    if fallback.exists():
        return ImageFont.truetype(str(fallback), size=size)
    return ImageFont.load_default()


@lru_cache(maxsize=2)
def _load_poster_base() -> Image.Image | None:
    poster_path = Path(settings.POSTER_IMAGE_PATH)
    if poster_path.exists():
        return Image.open(poster_path).convert("RGB")
    return None


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _measure_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
) -> tuple[int, int, int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    width: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
) -> int:
    bx, by, tw, th = _measure_text(draw, text, font)
    x = (width - tw) // 2 - bx
    draw.text((x, y - by), text, font=font, fill=fill)
    return y + th


def _draw_left_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
) -> int:
    bx, by, _tw, th = _measure_text(draw, text, font)
    draw.text((x - bx, y - by), text, font=font, fill=fill)
    return y + th


def _select_nickname_font_key(nickname: str) -> str:
    if _has_cjk(nickname):
        return "__CJK__"
    if _needs_unicode_fallback(nickname):
        return "NotoSans-Bold.ttf"
    return "Montserrat-Bold.ttf"


def _strip_missing_glyphs(text: str, font: ImageFont.FreeTypeFont) -> str:
    """Remove glyphs that the selected TrueType font renders as .notdef tofu boxes."""
    try:
        notdef_mask = bytes(font.getmask("\uffff"))
    except Exception:
        return text
    if not notdef_mask:
        return text
    cleaned: list[str] = []
    for ch in text:
        if ch.isspace():
            cleaned.append(ch)
            continue
        try:
            if bytes(font.getmask(ch)) == notdef_mask:
                continue
        except Exception:
            pass
        cleaned.append(ch)
    result = " ".join("".join(cleaned).split())
    return result or text


def _fit_font_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_filename: str,
    start_size: int,
    min_size: int,
    max_width: int,
) -> ImageFont.FreeTypeFont:
    for size in range(start_size, min_size - 1, -1):
        font = _load_font(font_filename, size)
        if _measure_text(draw, text, font)[2] <= max_width:
            return font
    return _load_font(font_filename, min_size)


def _wrap_nickname(
    draw: ImageDraw.ImageDraw,
    nickname: str,
    max_width: int,
    start_size: int,
    min_size: int,
    max_lines: int = 2,
) -> tuple[list[str], ImageFont.FreeTypeFont]:
    font_key = _select_nickname_font_key(nickname)
    probe_font = _load_font(font_key, start_size)
    nickname = _strip_missing_glyphs(nickname, probe_font)
    for size in range(start_size, min_size - 1, -4):
        font = _load_font(font_key, size)
        _bx, _by, tw, _th = _measure_text(draw, nickname, font)
        if tw <= max_width:
            return [nickname], font

    font = _load_font(font_key, min_size)
    words = nickname.split()
    lines: list[str] = []
    if len(words) > 1:
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip() if current else word
            _bx, _by, tw, _th = _measure_text(draw, candidate, font)
            if tw <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

    # Character-level wrap fallback for long single tokens or CJK strings
    if not lines or any(_measure_text(draw, ln, font)[2] > max_width for ln in lines):
        lines = []
        current = ""
        for ch in nickname:
            candidate = current + ch
            if _measure_text(draw, candidate, font)[2] <= max_width or not current:
                current = candidate
            else:
                lines.append(current.strip())
                current = ch
        if current.strip():
            lines.append(current.strip())

    return lines[:max_lines], font


def _build_editorial_backdrop(width: int, height: int) -> Image.Image:
    canvas = Image.new("RGB", (width, height), MIDNIGHT_BROWN)
    poster = _load_poster_base()
    if poster is not None:
        bg_poster = _cover_crop(poster, width, height)
        bg_poster = bg_poster.filter(ImageFilter.GaussianBlur(radius=42))
        bg_poster = ImageEnhance.Brightness(bg_poster).enhance(0.24)
        bg_poster = ImageEnhance.Color(bg_poster).enhance(1.22)
        canvas = Image.blend(canvas, bg_poster, alpha=0.78)

    # Warm dual stage spotlights (heavily blurred for silky seamless lighting)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse(
        (-int(width * 0.12), -int(height * 0.08), int(width * 1.12), int(height * 0.52)),
        fill=(232, 93, 25, 74),
    )
    odraw.ellipse(
        (int(width * 0.08), int(height * 0.45), int(width * 0.92), int(height * 0.95)),
        fill=(255, 190, 85, 34),
    )
    odraw.rectangle((0, int(height * 0.72), width, height), fill=(25, 13, 8, 165))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=85))
    composed = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    # Subtle restrained editorial film grain
    grain = Image.effect_noise((width, height), 14).convert("RGB")
    composed = Image.blend(composed, grain, alpha=0.03)
    return composed


def _paste_framed_poster(
    img: Image.Image,
    poster: Image.Image | None,
    x: int,
    y: int,
    size: int,
) -> None:
    if poster is None:
        return
    # Soft backlit burnt-orange & dark drop shadow behind poster
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.rectangle((x - 18, y - 14, x + size + 18, y + size + 24), fill=(232, 93, 25, 82))
    gdraw.rectangle((x - 4, y + 10, x + size + 4, y + size + 18), fill=(12, 6, 3, 170))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=28))
    merged = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    img.paste(merged)

    poster_thumb = poster.resize((size, size), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)
    # Crisp thin gold frame + inner burnt-orange keyline
    draw.rectangle((x - 5, y - 5, x + size + 5, y + size + 5), outline=CHAMPAGNE_GOLD, width=2)
    draw.rectangle((x - 2, y - 2, x + size + 2, y + size + 2), outline=BURNT_ORANGE, width=2)
    img.paste(poster_thumb, (x, y))


def _format_event_date(event) -> str:
    return f"{event.event_date.day} {event.event_date.strftime('%B %Y')}".upper()


def _format_public_location(event) -> str:
    parts = [p.strip() for p in event.location.split(",") if p.strip()]
    if len(parts) >= 2:
        return f"{parts[0]}, {parts[1]}".upper()
    return event.location.upper()


def _format_date_time_line(event) -> str:
    date_part = _format_event_date(event)
    loc_part = _format_public_location(event)
    if event.start_time:
        t = event.start_time.strftime("%I:%M %p").lstrip("0")
        return f"{date_part}  ·  {t}  ·  {loc_part}"
    return f"{date_part}  ·  {loc_part}"


def _draw_official_badge(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    rule_len: int = 86,
) -> int:
    text = "IT'S OFFICIAL"
    bx, by, tw, th = _measure_text(draw, text, font)
    tx = center_x - tw // 2
    draw.text((tx - bx, y - by), text, font=font, fill=SUNSET_ORANGE)
    mid_y = y + th // 2
    draw.line((tx - 18 - rule_len, mid_y, tx - 18, mid_y), fill=BURNT_ORANGE, width=3)
    draw.line((tx + tw + 18, mid_y, tx + tw + 18 + rule_len, mid_y), fill=BURNT_ORANGE, width=3)
    return y + th


def _render_story(event, active_nickname: str) -> Image.Image:
    """Dedicated 1080 x 1920 (9:16) WhatsApp Status & IG Story poster composition."""
    width, height = FORMAT_SPECS["story"]
    img = _build_editorial_backdrop(width, height)
    poster = _load_poster_base()
    draw = ImageDraw.Draw(img)

    organizers_text = (event.organizers or "AFTER DARK EVENTS × HYPE DISTRICT").upper()
    hashtag_text = event.hashtag or "#DripAndRhythm"

    # Subtle outer editorial frame honoring Story safe areas
    draw.rectangle((34, 78, width - 34, height - 78), outline=(145, 110, 66), width=2)

    # Top Masthead
    cy = 114
    cy = _draw_centered_text(draw, organizers_text, cy, width, _load_font("Montserrat-Bold.ttf", 22), CHAMPAGNE_GOLD) + 20
    cy = _draw_centered_text(draw, event.name.upper(), cy, width, _load_font("Anton-Regular.ttf", 112), WARM_IVORY) + 12
    cy = _draw_centered_text(draw, event.subtitle or "Private Party", cy, width, _load_font("WindSong-Medium.ttf", 62), GOLDEN_AMBER)

    # Large Hero Poster (~80% of canvas width when anonymous, ~77% when personalized)
    poster_size = 830 if active_nickname else 880
    poster_x = (width - poster_size) // 2
    poster_y = cy + 28
    _paste_framed_poster(img, poster, poster_x, poster_y, poster_size)
    draw = ImageDraw.Draw(img)

    # Confirmation & Event Details distributed purposefully across the entire lower zone
    footer_y = height - 122
    zone_top = poster_y + poster_size + 40
    zone_bottom = footer_y - 34

    f_official = _load_font("Montserrat-Bold.ttf", 30)
    f_secured = _load_font("Anton-Regular.ttf", 98 if active_nickname else 108)
    f_vibe = _load_font("Montserrat-SemiBold.ttf", 27)
    date_line = _format_date_time_line(event)
    f_date = _load_font("Montserrat-Bold.ttf", 31 if len(date_line) > 36 else 35)
    f_tag = _load_font("Montserrat-Medium.ttf", 24)

    nick_lines: list[str] = []
    nick_font = _load_font("Montserrat-Bold.ttf", 56)
    if active_nickname:
        nick_lines, nick_font = _wrap_nickname(draw, active_nickname, width - 140, 60, 34, max_lines=2)

    # Measure total block height to center vertically inside [zone_top, zone_bottom]
    block_h = _measure_text(draw, "IT'S OFFICIAL", f_official)[3] + 22
    if nick_lines:
        for ln in nick_lines:
            block_h += _measure_text(draw, ln, nick_font)[3] + 12
        block_h += 12
    block_h += _measure_text(draw, "INVITATION SECURED.", f_secured)[3] + 24
    block_h += _measure_text(draw, "The drip is ready. The rhythm is calling.", f_vibe)[3] + 28
    block_h += 3 + 26  # Burnt-orange divider
    block_h += _measure_text(draw, date_line, f_date)[3] + 18
    block_h += _measure_text(draw, event.tagline, f_tag)[3]

    by = zone_top + max(0, (zone_bottom - zone_top - block_h) // 2)
    by = _draw_official_badge(draw, width // 2, by, f_official, rule_len=92) + 22

    if nick_lines:
        for ln in nick_lines:
            by = _draw_centered_text(draw, ln, by, width, nick_font, CHAMPAGNE_GOLD) + 12
        by += 12

    by = _draw_centered_text(draw, "INVITATION SECURED.", by, width, f_secured, WARM_IVORY) + 24
    by = _draw_centered_text(draw, "The drip is ready. The rhythm is calling.", by, width, f_vibe, CHAMPAGNE_GOLD) + 28
    draw.line((width // 2 - 220, by, width // 2 + 220, by), fill=BURNT_ORANGE, width=3)
    by += 26
    by = _draw_centered_text(draw, date_line, by, width, f_date, GOLDEN_AMBER) + 18
    _draw_centered_text(draw, event.tagline, by, width, f_tag, WARM_IVORY)

    # Bottom public privacy & entry notice
    _draw_centered_text(
        draw,
        f"{hashtag_text}  ·  OFFICIAL INVITATION REQUIRED FOR ENTRY  ·  {event.age_restriction}",
        footer_y,
        width,
        _load_font("Montserrat-SemiBold.ttf", 20),
        CHAMPAGNE_GOLD,
    )
    return img


def _render_portrait(event, active_nickname: str) -> Image.Image:
    """Dedicated 1080 x 1350 (4:5) social feed poster composition."""
    width, height = FORMAT_SPECS["portrait"]
    img = _build_editorial_backdrop(width, height)
    poster = _load_poster_base()
    draw = ImageDraw.Draw(img)

    organizers_text = (event.organizers or "AFTER DARK EVENTS × HYPE DISTRICT").upper()
    hashtag_text = event.hashtag or "#DripAndRhythm"

    draw.rectangle((30, 30, width - 30, height - 30), outline=(145, 110, 66), width=2)

    # Compact commanding header so the poster + confirmation fill the entire 4:5 frame
    cy = 52
    cy = _draw_centered_text(draw, organizers_text, cy, width, _load_font("Montserrat-Bold.ttf", 19), CHAMPAGNE_GOLD) + 14
    cy = _draw_centered_text(draw, event.name.upper(), cy, width, _load_font("Anton-Regular.ttf", 84), WARM_IVORY) + 6
    cy = _draw_centered_text(draw, event.subtitle or "Private Party", cy, width, _load_font("WindSong-Medium.ttf", 44), GOLDEN_AMBER)

    # Hero Poster (~68%–73% canvas width without cropping)
    poster_size = 710 if active_nickname else 780
    poster_x = (width - poster_size) // 2
    poster_y = cy + 16
    _paste_framed_poster(img, poster, poster_x, poster_y, poster_size)
    draw = ImageDraw.Draw(img)

    footer_y = height - 66
    zone_top = poster_y + poster_size + 22
    zone_bottom = footer_y - 20

    f_official = _load_font("Montserrat-Bold.ttf", 24)
    f_secured = _load_font("Anton-Regular.ttf", 80 if active_nickname else 92)
    date_line = _format_date_time_line(event)
    f_date = _load_font("Montserrat-Bold.ttf", 28 if len(date_line) > 36 else 32)
    f_tag = _load_font("Montserrat-Medium.ttf", 21)

    nick_lines: list[str] = []
    nick_font = _load_font("Montserrat-Bold.ttf", 48)
    if active_nickname:
        nick_lines, nick_font = _wrap_nickname(draw, active_nickname, width - 130, 50, 30, max_lines=2)

    block_h = _measure_text(draw, "IT'S OFFICIAL", f_official)[3] + 14
    if nick_lines:
        for ln in nick_lines:
            block_h += _measure_text(draw, ln, nick_font)[3] + 8
        block_h += 8
    block_h += _measure_text(draw, "INVITATION SECURED.", f_secured)[3] + 18
    block_h += 3 + 16
    block_h += _measure_text(draw, date_line, f_date)[3] + 12
    block_h += _measure_text(draw, event.tagline, f_tag)[3]

    by = zone_top + max(0, (zone_bottom - zone_top - block_h) // 2)
    by = _draw_official_badge(draw, width // 2, by, f_official, rule_len=74) + 14

    if nick_lines:
        for ln in nick_lines:
            by = _draw_centered_text(draw, ln, by, width, nick_font, CHAMPAGNE_GOLD) + 8
        by += 8

    by = _draw_centered_text(draw, "INVITATION SECURED.", by, width, f_secured, WARM_IVORY) + 18
    draw.line((width // 2 - 200, by, width // 2 + 200, by), fill=BURNT_ORANGE, width=3)
    by += 16
    by = _draw_centered_text(draw, date_line, by, width, f_date, GOLDEN_AMBER) + 12
    _draw_centered_text(draw, event.tagline, by, width, f_tag, WARM_IVORY)

    _draw_centered_text(
        draw,
        f"{hashtag_text}  ·  OFFICIAL INVITATION REQUIRED FOR ENTRY  ·  {event.age_restriction}",
        footer_y,
        width,
        _load_font("Montserrat-SemiBold.ttf", 18),
        CHAMPAGNE_GOLD,
    )
    return img


def _render_square(event, active_nickname: str) -> Image.Image:
    """Dedicated 1080 x 1080 (1:1) asymmetric editorial split composition."""
    width, height = FORMAT_SPECS["square"]
    img = _build_editorial_backdrop(width, height)
    poster = _load_poster_base()
    draw = ImageDraw.Draw(img)

    organizers_text = (event.organizers or "AFTER DARK EVENTS × HYPE DISTRICT").upper()
    hashtag_text = event.hashtag or "#DripAndRhythm"

    draw.rectangle((30, 30, width - 30, height - 30), outline=(145, 110, 66), width=2)

    # Full-width top masthead
    cy = 52
    cy = _draw_centered_text(draw, organizers_text, cy, width, _load_font("Montserrat-Bold.ttf", 19), CHAMPAGNE_GOLD) + 14
    cy = _draw_centered_text(draw, event.name.upper(), cy, width, _load_font("Anton-Regular.ttf", 88), WARM_IVORY) + 8
    cy = _draw_centered_text(draw, event.subtitle or "Private Party", cy, width, _load_font("WindSong-Medium.ttf", 46), GOLDEN_AMBER)

    # Middle asymmetric editorial split: large uncropped 520x520 poster left + confirmation monument right
    poster_size = 520
    poster_x = 58
    poster_y = cy + 20
    _paste_framed_poster(img, poster, poster_x, poster_y, poster_size)
    draw = ImageDraw.Draw(img)

    rx = poster_x + poster_size + 42
    rw = width - rx - 54

    f_official = _load_font("Montserrat-Bold.ttf", 25)
    f_secured_big = _load_font("Anton-Regular.ttf", 88 if active_nickname else 96)
    f_vibe = _load_font("Montserrat-SemiBold.ttf", 22)

    nick_lines: list[str] = []
    nick_font = _load_font("Montserrat-Bold.ttf", 44)
    if active_nickname:
        nick_lines, nick_font = _wrap_nickname(draw, active_nickname, rw, 46, 26, max_lines=3)

    # Measure right stack to vertically center beside the 520px poster
    stack_h = _measure_text(draw, "IT'S OFFICIAL", f_official)[3] + 18
    if nick_lines:
        for ln in nick_lines:
            stack_h += _measure_text(draw, ln, nick_font)[3] + 10
        stack_h += 14
    stack_h += _measure_text(draw, "INVITATION", f_secured_big)[3] + 10
    stack_h += _measure_text(draw, "SECURED.", f_secured_big)[3] + 24
    stack_h += _measure_text(draw, "The drip is ready.", f_vibe)[3] + 8
    stack_h += _measure_text(draw, "The rhythm is calling.", f_vibe)[3]

    ry = poster_y + max(0, (poster_size - stack_h) // 2)
    ry = _draw_left_text(draw, "IT'S OFFICIAL", rx, ry, f_official, SUNSET_ORANGE) + 10
    draw.line((rx, ry, rx + 130, ry), fill=BURNT_ORANGE, width=3)
    ry += 16

    if nick_lines:
        for ln in nick_lines:
            ry = _draw_left_text(draw, ln, rx, ry, nick_font, CHAMPAGNE_GOLD) + 10
        ry += 12

    ry = _draw_left_text(draw, "INVITATION", rx, ry, f_secured_big, WARM_IVORY) + 10
    ry = _draw_left_text(draw, "SECURED.", rx, ry, f_secured_big, WARM_IVORY) + 22
    ry = _draw_left_text(draw, "The drip is ready.", rx, ry, f_vibe, CHAMPAGNE_GOLD) + 8
    _draw_left_text(draw, "The rhythm is calling.", rx, ry, f_vibe, CHAMPAGNE_GOLD)

    # Bottom full-width date, tagline & disclaimer band
    band_y = poster_y + poster_size + 36
    draw.line((58, band_y, width - 58, band_y), fill=BURNT_ORANGE, width=3)
    band_y += 24
    date_line = _format_date_time_line(event)
    f_date = _load_font("Montserrat-Bold.ttf", 31 if len(date_line) > 36 else 35)
    band_y = _draw_centered_text(draw, date_line, band_y, width, f_date, GOLDEN_AMBER) + 16
    band_y = _draw_centered_text(draw, event.tagline, band_y, width, _load_font("Montserrat-Medium.ttf", 23), WARM_IVORY)

    _draw_centered_text(
        draw,
        f"{hashtag_text}  ·  OFFICIAL INVITATION REQUIRED FOR ENTRY  ·  {event.age_restriction}",
        max(band_y + 20, height - 74),
        width,
        _load_font("Montserrat-SemiBold.ttf", 18),
        CHAMPAGNE_GOLD,
    )
    return img


def _render_preview(event, active_nickname: str) -> Image.Image:
    """Dedicated 1200 x 630 (1.91:1) Open Graph social link preview composition."""
    width, height = FORMAT_SPECS["preview"]
    img = _build_editorial_backdrop(width, height)
    poster = _load_poster_base()
    draw = ImageDraw.Draw(img)

    organizers_text = (event.organizers or "AFTER DARK EVENTS × HYPE DISTRICT").upper()
    hashtag_text = event.hashtag or "#DripAndRhythm"

    draw.rectangle((28, 28, width - 28, height - 28), outline=(145, 110, 66), width=2)

    poster_size = 506
    poster_x = 58
    poster_y = (height - poster_size) // 2
    _paste_framed_poster(img, poster, poster_x, poster_y, poster_size)
    draw = ImageDraw.Draw(img)

    rx = poster_x + poster_size + 46
    rw = width - rx - 52

    footer_line = f"{hashtag_text}  ·  Official invitation required for entry  ·  {event.age_restriction}"
    date_line = _format_date_time_line(event)

    f_org = _fit_font_to_width(draw, organizers_text, "Montserrat-Bold.ttf", 17, 13, rw)
    f_title = _fit_font_to_width(draw, event.name.upper(), "Anton-Regular.ttf", 72, 48, rw)
    f_script = _load_font("WindSong-Medium.ttf", 40)
    f_official = _load_font("Montserrat-Bold.ttf", 21)
    f_secured = _fit_font_to_width(
        draw,
        "INVITATION SECURED.",
        "Anton-Regular.ttf",
        62 if active_nickname else 72,
        44,
        rw,
    )
    f_date = _fit_font_to_width(draw, date_line, "Montserrat-Bold.ttf", 23, 14, rw)
    f_small = _fit_font_to_width(draw, footer_line, "Montserrat-SemiBold.ttf", 16, 11, rw)

    nick_lines: list[str] = []
    nick_font = _load_font("Montserrat-Bold.ttf", 38)
    if active_nickname:
        nick_lines, nick_font = _wrap_nickname(draw, active_nickname, rw, 40, 24, max_lines=2)

    # Compute exact stack height so vertical rhythm fills 630px cleanly in both anonymous & personalized modes
    stack_h = _measure_text(draw, organizers_text, f_org)[3] + 12
    stack_h += _measure_text(draw, event.name.upper(), f_title)[3] + 6
    stack_h += _measure_text(draw, event.subtitle or "Private Party", f_script)[3] + 18
    stack_h += 3 + 18
    stack_h += _measure_text(draw, "IT'S OFFICIAL", f_official)[3] + 14
    if nick_lines:
        for ln in nick_lines:
            stack_h += _measure_text(draw, ln, nick_font)[3] + 8
        stack_h += 8
    stack_h += _measure_text(draw, "INVITATION SECURED.", f_secured)[3] + 20
    stack_h += _measure_text(draw, date_line, f_date)[3] + 14
    stack_h += _measure_text(draw, footer_line, f_small)[3]

    ry = max(56, (height - stack_h) // 2)
    ry = _draw_left_text(draw, organizers_text, rx, ry, f_org, CHAMPAGNE_GOLD) + 12
    ry = _draw_left_text(draw, event.name.upper(), rx, ry, f_title, WARM_IVORY) + 6
    ry = _draw_left_text(draw, event.subtitle or "Private Party", rx + 2, ry, f_script, GOLDEN_AMBER) + 18
    draw.line((rx, ry, rx + 260, ry), fill=BURNT_ORANGE, width=3)
    ry += 18
    ry = _draw_left_text(draw, "IT'S OFFICIAL", rx, ry, f_official, SUNSET_ORANGE) + 14

    if nick_lines:
        for ln in nick_lines:
            ry = _draw_left_text(draw, ln, rx, ry, nick_font, CHAMPAGNE_GOLD) + 8
        ry += 8

    ry = _draw_left_text(draw, "INVITATION SECURED.", rx, ry, f_secured, WARM_IVORY) + 20
    ry = _draw_left_text(draw, date_line, rx, ry, f_date, GOLDEN_AMBER) + 14
    _draw_left_text(
        draw,
        footer_line,
        rx,
        ry,
        f_small,
        CHAMPAGNE_GOLD,
    )
    return img


def render_promotional_artwork(
    *,
    event,
    format_name: str,
    nickname: str | None = None,
    show_nickname: bool = False,
) -> bytes:
    if format_name not in FORMAT_SPECS:
        raise ValueError(f"Unsupported artwork format: {format_name}")

    active_nickname = (nickname or "").strip() if show_nickname else ""
    if format_name == "story":
        img = _render_story(event, active_nickname)
    elif format_name == "portrait":
        img = _render_portrait(event, active_nickname)
    elif format_name == "square":
        img = _render_square(event, active_nickname)
    else:
        img = _render_preview(event, active_nickname)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
