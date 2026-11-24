from __future__ import annotations

import hashlib
import io
import logging
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

ARTWORK_RENDERER_VERSION = "v4"

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

# Bounded temporary filesystem cache settings (no Redis, no paid disks)
CACHE_MAX_FILES = int(os.getenv("ARTWORK_CACHE_MAX_FILES", "80"))
CACHE_MAX_BYTES = int(os.getenv("ARTWORK_CACHE_MAX_BYTES", str(96 * 1024 * 1024)))
CACHE_TTL_SECONDS = int(os.getenv("ARTWORK_CACHE_TTL_SECONDS", "86400"))

# Concurrency protection: max 1 expensive Pillow render at a time per process so
# health checks, QR verification, admission, claiming, and webhooks stay fast.
MAX_CONCURRENT_RENDERS = max(1, int(os.getenv("ARTWORK_MAX_CONCURRENT_RENDERS", "1")))
RENDER_ACQUIRE_TIMEOUT_SECONDS = float(os.getenv("ARTWORK_ACQUIRE_TIMEOUT_SECONDS", "1.5"))
INFLIGHT_WAIT_TIMEOUT_SECONDS = float(os.getenv("ARTWORK_INFLIGHT_WAIT_SECONDS", "8.0"))

_RENDER_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_RENDERS)
_INFLIGHT_LOCK = threading.Lock()
_INFLIGHT_EVENTS: dict[str, threading.Event] = {}


class ArtworkRenderBusyError(Exception):
    """Raised when the single artwork rendering slot is occupied."""

    retry_after_seconds: int = 3


@dataclass(frozen=True)
class RenderedArtworkResult:
    png_bytes: bytes
    cache_key: str
    cache_hit: bool


def _read_rss_mb() -> float:
    """Best-effort, zero-dependency RSS lookup on Linux (/proc/self/status)."""
    try:
        status_path = Path("/proc/self/status")
        if status_path.exists():
            for line in status_path.read_text(encoding="ascii", errors="ignore").splitlines():
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return kb / 1024.0
    except Exception:
        pass
    return 0.0


def get_artwork_cache_dir() -> Path:
    configured = getattr(settings, "ARTWORK_CACHE_DIR", None)
    base = Path(configured) if configured else (Path(tempfile.gettempdir()) / "drip_artwork_cache")
    base.mkdir(parents=True, exist_ok=True)
    return base


def build_artwork_cache_key(
    *,
    event,
    format_name: str,
    nickname: str | None = None,
    show_nickname: bool = True,
    invitation_id: str | None = None,
    sharing_version: int | None = None,
) -> str:
    """
    Deterministic, non-sensitive SHA-256 cache identifier.
    Always includes the guest's registered nickname, sharing_version, format,
    renderer version, and event configuration so cached PNGs stay accurate.
    """
    _ = show_nickname  # Personalized nickname is always displayed on promotional artwork
    active_nickname = (nickname or "").strip()
    event_sig = "|".join(
        [
            ARTWORK_RENDERER_VERSION,
            str(getattr(event, "name", "")),
            str(getattr(event, "subtitle", "")),
            str(getattr(event, "tagline", "")),
            str(getattr(event, "organizers", "")),
            str(getattr(event, "hashtag", "")),
            str(getattr(event.event_date, "isoformat", lambda: event.event_date)()),
            str(getattr(event, "start_time", "") or ""),
            str(getattr(event, "location", "")),
            str(getattr(event, "age_restriction", "")),
        ]
    )
    inv_part = str(invitation_id or "")
    ver_part = str(sharing_version if sharing_version is not None else 1)
    raw = f"pers|{format_name}|{event_sig}|{inv_part}|{ver_part}|{active_nickname}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:36]


def _read_cached_png(cache_key: str) -> bytes | None:
    path = get_artwork_cache_dir() / f"{cache_key}.png"
    try:
        if not path.exists():
            return None
        stat = path.stat()
        now = time.time()
        if now - stat.st_mtime > CACHE_TTL_SECONDS or stat.st_size == 0:
            path.unlink(missing_ok=True)
            return None
        data = path.read_bytes()
        # Best-effort LRU touch without failing reads
        try:
            os.utime(path, (now, now))
        except OSError:
            pass
        return data
    except OSError:
        return None


def _evict_cache_if_needed(cache_dir: Path) -> None:
    now = time.time()
    png_entries: list[tuple[float, int, Path]] = []
    total_bytes = 0

    try:
        for entry in cache_dir.iterdir():
            try:
                st = entry.stat()
            except OSError:
                continue
            if entry.suffix == ".tmp":
                if now - st.st_mtime > 120:
                    entry.unlink(missing_ok=True)
                continue
            if entry.suffix != ".png":
                continue
            if now - st.st_mtime > CACHE_TTL_SECONDS:
                entry.unlink(missing_ok=True)
                continue
            png_entries.append((st.st_mtime, st.st_size, entry))
            total_bytes += st.st_size
    except OSError:
        return

    if len(png_entries) <= CACHE_MAX_FILES and total_bytes <= CACHE_MAX_BYTES:
        return

    # Evict oldest-accessed files first
    png_entries.sort(key=lambda item: item[0])
    remaining_count = len(png_entries)
    for _mtime, size, path in png_entries:
        if remaining_count <= CACHE_MAX_FILES and total_bytes <= CACHE_MAX_BYTES:
            break
        try:
            path.unlink(missing_ok=True)
            remaining_count -= 1
            total_bytes -= size
        except OSError:
            continue


def _write_cached_png_atomic(cache_key: str, data: bytes) -> None:
    cache_dir = get_artwork_cache_dir()
    final_path = cache_dir / f"{cache_key}.png"
    tmp_path = cache_dir / f"{cache_key}.{uuid.uuid4().hex[:10]}.tmp"
    try:
        tmp_path.write_bytes(data)
        os.replace(tmp_path, final_path)
        _evict_cache_if_needed(cache_dir)
    except OSError:
        pass
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


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


@lru_cache(maxsize=1)
def _load_poster_base() -> Image.Image | None:
    poster_path = Path(settings.POSTER_IMAGE_PATH)
    if poster_path.exists():
        with Image.open(poster_path) as src:
            return src.convert("RGB")
    return None


@lru_cache(maxsize=6)
def _get_resized_poster(size: int) -> Image.Image | None:
    poster = _load_poster_base()
    if poster is None:
        return None
    return poster.resize((size, size), Image.Resampling.LANCZOS)


@lru_cache(maxsize=8)
def _get_subtle_grain_tile() -> Image.Image:
    return Image.effect_noise((256, 256), 14).convert("RGB")


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    try:
        left = (resized.width - target_w) // 2
        top = (resized.height - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))
    finally:
        resized.close()


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
    """
    Compute the soft-focus stage backdrop at 1/8 scale and upscale smoothly.
    Produces an indistinguishable low-frequency lighting field while cutting CPU
    and peak RAM allocation by >95% compared to full-canvas radius=85 blurs.
    """
    scale_div = 8
    sw = max(64, width // scale_div)
    sh = max(64, height // scale_div)

    small_canvas = Image.new("RGB", (sw, sh), MIDNIGHT_BROWN)
    poster = _load_poster_base()
    if poster is not None:
        bg_small = _cover_crop(poster, sw, sh)
        blurred = bg_small.filter(ImageFilter.GaussianBlur(radius=6))
        bg_small.close()
        darkened = ImageEnhance.Brightness(blurred).enhance(0.24)
        blurred.close()
        saturated = ImageEnhance.Color(darkened).enhance(1.22)
        darkened.close()
        blended = Image.blend(small_canvas, saturated, alpha=0.78)
        small_canvas.close()
        saturated.close()
        small_canvas = blended

    overlay = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse(
        (-int(sw * 0.12), -int(sh * 0.08), int(sw * 1.12), int(sh * 0.52)),
        fill=(232, 93, 25, 74),
    )
    odraw.ellipse(
        (int(sw * 0.08), int(sh * 0.45), int(sw * 0.92), int(sh * 0.95)),
        fill=(255, 190, 85, 34),
    )
    odraw.rectangle((0, int(sh * 0.72), sw, sh), fill=(25, 13, 8, 165))
    overlay_blurred = overlay.filter(ImageFilter.GaussianBlur(radius=11))
    overlay.close()

    small_rgba = small_canvas.convert("RGBA")
    small_canvas.close()
    small_comp_rgba = Image.alpha_composite(small_rgba, overlay_blurred)
    small_rgba.close()
    overlay_blurred.close()

    small_rgb = small_comp_rgba.convert("RGB")
    small_comp_rgba.close()

    composed = small_rgb.resize((width, height), Image.Resampling.BICUBIC)
    small_rgb.close()

    # Tile cached 256x256 subtle film grain instead of generating 2M random pixels per render
    grain_tile = _get_subtle_grain_tile()
    grain_layer = Image.new("RGB", (width, height))
    for gy in range(0, height, 256):
        for gx in range(0, width, 256):
            grain_layer.paste(grain_tile, (gx, gy))
    final = Image.blend(composed, grain_layer, alpha=0.03)
    composed.close()
    grain_layer.close()
    return final


def _paste_framed_poster(
    img: Image.Image,
    poster: Image.Image | None,
    x: int,
    y: int,
    size: int,
) -> None:
    if poster is None:
        return
    # Localize the glow/shadow composite to the poster bounding box instead of the full canvas
    pad = 64
    rx0 = max(0, x - pad)
    ry0 = max(0, y - pad)
    rx1 = min(img.width, x + size + pad)
    ry1 = min(img.height, y + size + pad)
    pw, ph = rx1 - rx0, ry1 - ry0

    # Downscaled 1/4 glow blur on the local patch for speed & silky falloff
    gw, gh = max(16, pw // 4), max(16, ph // 4)
    glow_small = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow_small)
    lx = (x - rx0) // 4
    ly = (y - ry0) // 4
    ls = size // 4
    gdraw.rectangle((lx - 5, ly - 4, lx + ls + 5, ly + ls + 6), fill=(232, 93, 25, 86))
    gdraw.rectangle((lx - 1, ly + 3, lx + ls + 1, ly + ls + 5), fill=(12, 6, 3, 175))
    glow_blurred = glow_small.filter(ImageFilter.GaussianBlur(radius=7))
    glow_small.close()
    glow_patch = glow_blurred.resize((pw, ph), Image.Resampling.BILINEAR)
    glow_blurred.close()

    base_patch = img.crop((rx0, ry0, rx1, ry1)).convert("RGBA")
    merged_rgba = Image.alpha_composite(base_patch, glow_patch)
    base_patch.close()
    glow_patch.close()
    merged_rgb = merged_rgba.convert("RGB")
    merged_rgba.close()
    img.paste(merged_rgb, (rx0, ry0))
    merged_rgb.close()

    poster_thumb = _get_resized_poster(size)
    if poster_thumb is not None:
        draw = ImageDraw.Draw(img)
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

    draw.rectangle((34, 78, width - 34, height - 78), outline=(145, 110, 66), width=2)

    cy = 114
    cy = _draw_centered_text(draw, organizers_text, cy, width, _load_font("Montserrat-Bold.ttf", 22), CHAMPAGNE_GOLD) + 20
    cy = _draw_centered_text(draw, event.name.upper(), cy, width, _load_font("Anton-Regular.ttf", 112), WARM_IVORY) + 12
    cy = _draw_centered_text(draw, event.subtitle or "Private Party", cy, width, _load_font("WindSong-Medium.ttf", 62), GOLDEN_AMBER)

    poster_size = 830 if active_nickname else 880
    poster_x = (width - poster_size) // 2
    poster_y = cy + 28
    _paste_framed_poster(img, poster, poster_x, poster_y, poster_size)
    draw = ImageDraw.Draw(img)

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

    block_h = _measure_text(draw, "IT'S OFFICIAL", f_official)[3] + 22
    if nick_lines:
        for ln in nick_lines:
            block_h += _measure_text(draw, ln, nick_font)[3] + 12
        block_h += 12
    block_h += _measure_text(draw, "INVITATION SECURED.", f_secured)[3] + 24
    block_h += _measure_text(draw, "The drip is ready. The rhythm is calling.", f_vibe)[3] + 28
    block_h += 3 + 26
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

    cy = 52
    cy = _draw_centered_text(draw, organizers_text, cy, width, _load_font("Montserrat-Bold.ttf", 19), CHAMPAGNE_GOLD) + 14
    cy = _draw_centered_text(draw, event.name.upper(), cy, width, _load_font("Anton-Regular.ttf", 84), WARM_IVORY) + 6
    cy = _draw_centered_text(draw, event.subtitle or "Private Party", cy, width, _load_font("WindSong-Medium.ttf", 44), GOLDEN_AMBER)

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

    cy = 52
    cy = _draw_centered_text(draw, organizers_text, cy, width, _load_font("Montserrat-Bold.ttf", 19), CHAMPAGNE_GOLD) + 14
    cy = _draw_centered_text(draw, event.name.upper(), cy, width, _load_font("Anton-Regular.ttf", 88), WARM_IVORY) + 8
    cy = _draw_centered_text(draw, event.subtitle or "Private Party", cy, width, _load_font("WindSong-Medium.ttf", 46), GOLDEN_AMBER)

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


def _render_png_bytes_uncached(event, format_name: str, active_nickname: str) -> bytes:
    if format_name == "story":
        img = _render_story(event, active_nickname)
    elif format_name == "portrait":
        img = _render_portrait(event, active_nickname)
    elif format_name == "square":
        img = _render_square(event, active_nickname)
    else:
        img = _render_preview(event, active_nickname)

    try:
        out = io.BytesIO()
        # Balanced zlib level 6 avoids multi-pass optimize=True CPU spikes on noisy 2MP canvases
        img.save(out, format="PNG", compress_level=6)
        return out.getvalue()
    finally:
        img.close()


def get_or_render_promotional_artwork(
    *,
    event,
    format_name: str,
    nickname: str | None = None,
    show_nickname: bool = True,
    invitation_id: str | None = None,
    sharing_version: int | None = None,
) -> RenderedArtworkResult:
    """
    Serve promotional artwork from bounded disk cache when available, coalesce
    duplicate simultaneous requests for the same cache key, and enforce a strict
    single-slot rendering gate so critical API/admission threads stay responsive.
    """
    if format_name not in FORMAT_SPECS:
        raise ValueError(f"Unsupported artwork format: {format_name}")

    _ = show_nickname
    t0 = time.perf_counter()
    active_nickname = (nickname or "").strip()
    mode_label = "personalized"
    cache_key = build_artwork_cache_key(
        event=event,
        format_name=format_name,
        nickname=active_nickname,
        show_nickname=True,
        invitation_id=invitation_id,
        sharing_version=sharing_version,
    )

    cached = _read_cached_png(cache_key)
    if cached is not None:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            "artwork_cache_hit format=%s mode=%s bytes=%d duration_ms=%.1f",
            format_name,
            mode_label,
            len(cached),
            dt_ms,
        )
        return RenderedArtworkResult(png_bytes=cached, cache_key=cache_key, cache_hit=True)

    # Single-flight coalescing per cache_key
    is_leader = False
    with _INFLIGHT_LOCK:
        wait_event = _INFLIGHT_EVENTS.get(cache_key)
        if wait_event is None:
            wait_event = threading.Event()
            _INFLIGHT_EVENTS[cache_key] = wait_event
            is_leader = True

    if not is_leader:
        finished = wait_event.wait(timeout=INFLIGHT_WAIT_TIMEOUT_SECONDS)
        if finished:
            coalesced = _read_cached_png(cache_key)
            if coalesced is not None:
                dt_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "artwork_inflight_reused format=%s mode=%s bytes=%d duration_ms=%.1f",
                    format_name,
                    mode_label,
                    len(coalesced),
                    dt_ms,
                )
                return RenderedArtworkResult(png_bytes=coalesced, cache_key=cache_key, cache_hit=True)
        logger.warning("artwork_capacity_busy format=%s mode=%s reason=inflight_wait_timeout", format_name, mode_label)
        raise ArtworkRenderBusyError("Artwork rendering is currently busy.")

    acquired = False
    try:
        acquired = _RENDER_SEMAPHORE.acquire(timeout=RENDER_ACQUIRE_TIMEOUT_SECONDS)
        if not acquired:
            logger.warning("artwork_capacity_busy format=%s mode=%s reason=semaphore_busy", format_name, mode_label)
            raise ArtworkRenderBusyError("Artwork rendering capacity is temporarily occupied.")

        # Re-check cache after acquiring semaphore in case another request populated it
        recheck = _read_cached_png(cache_key)
        if recheck is not None:
            return RenderedArtworkResult(png_bytes=recheck, cache_key=cache_key, cache_hit=True)

        png_bytes = _render_png_bytes_uncached(event, format_name, active_nickname)
        _write_cached_png_atomic(cache_key, png_bytes)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        rss_mb = _read_rss_mb()
        logger.info(
            "artwork_rendered format=%s mode=%s bytes=%d duration_ms=%.1f rss_mb=%.1f",
            format_name,
            mode_label,
            len(png_bytes),
            dt_ms,
            rss_mb,
        )
        return RenderedArtworkResult(png_bytes=png_bytes, cache_key=cache_key, cache_hit=False)
    finally:
        if acquired:
            _RENDER_SEMAPHORE.release()
        with _INFLIGHT_LOCK:
            ev = _INFLIGHT_EVENTS.pop(cache_key, None)
            if ev is not None:
                ev.set()


def render_promotional_artwork(
    *,
    event,
    format_name: str,
    nickname: str | None = None,
    show_nickname: bool = True,
    invitation_id: str | None = None,
    sharing_version: int | None = None,
) -> bytes:
    """Backward-compatible helper returning raw PNG bytes (backed by cache + single-flight)."""
    return get_or_render_promotional_artwork(
        event=event,
        format_name=format_name,
        nickname=nickname,
        show_nickname=show_nickname,
        invitation_id=invitation_id,
        sharing_version=sharing_version,
    ).png_bytes
