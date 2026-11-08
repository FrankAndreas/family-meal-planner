"""Recipe photos: any phone photo in, an upright JPEG of at most 1600 px without metadata (no GPS) out."""

import io
import re
import uuid
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config
from .errors import Refused

pillow_heif.register_heif_opener()  # HEIC photos from iPhones

MAX_BYTES = 25 * 1024 * 1024
MAX_SIDE = 1600
# The version recipe cards show (lists, suggestions): about twice their largest size on screen, sharp on a phone
CARD_SIDE = 480
# A picture is decoded only up to this size (48 MP phone photos fit): a small file can unpack into a giant one
# (a decompression bomb)
MAX_PIXELS = 64_000_000
NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")


class PhotoUnreadable(Refused):
    def __init__(self) -> None:
        super().__init__("photo_unreadable")


def folder() -> Path:
    return config.data_dir() / "photos"


def photo_path(name: str) -> Path | None:
    """The file for a stored photo's name, or None for anything that isn't one (no path tricks)."""
    if not NAME.fullmatch(name):
        return None
    return folder() / name


def downscale(data: bytes, side: int = MAX_SIDE, quality: int = 85) -> bytes:
    """Any picture as a JPEG of at most `side` pixels, without the original's metadata (also for thumbnails)."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            # Checked before decoding: the header tells the size
            if source.width * source.height > MAX_PIXELS:
                raise ValueError("too many pixels")
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise PhotoUnreadable()
    image.thumbnail((side, side))
    out = io.BytesIO()
    # Saved without exif=..., so nothing of the original's metadata is kept
    image.save(out, "JPEG", quality=quality)
    return out.getvalue()


def store_photo(data: bytes) -> str:
    jpeg = downscale(data)
    name = f"{uuid.uuid4().hex}.jpg"
    folder().mkdir(parents=True, exist_ok=True)
    (folder() / name).write_bytes(jpeg)
    return name


def card_path(name: str) -> Path | None:
    """The card version of a stored photo, made on first use and kept (performance review 2026-11-08): a list of
    recipes loads 480 px pictures, not 1600 px ones."""
    path = photo_path(name)
    if path is None or not path.is_file():
        return None
    card = folder() / "cards" / name
    if not card.is_file():
        card.parent.mkdir(parents=True, exist_ok=True)
        # Written under another name first: a request at the same moment never serves half a file
        partial = card.with_suffix(f".{uuid.uuid4().hex}.part")
        partial.write_bytes(downscale(path.read_bytes(), CARD_SIDE, quality=80))
        partial.replace(card)
    return card


def delete_photo(name: str | None) -> None:
    path = photo_path(name) if name else None
    if path is not None:
        path.unlink(missing_ok=True)
        (folder() / "cards" / path.name).unlink(missing_ok=True)
