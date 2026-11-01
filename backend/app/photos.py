"""Recipe photos: any phone photo in, an upright JPEG of at most 1600 px without metadata (no GPS) out."""

import io
import re
import uuid
import warnings
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

from . import config
from .errors import api_error

pillow_heif.register_heif_opener()  # HEIC photos from iPhones

MAX_BYTES = 25 * 1024 * 1024
MAX_SIDE = 1600
# A picture is decoded only up to this size: a small file can unpack into a giant one (a decompression bomb)
MAX_PIXELS = 40_000_000
NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")


def folder() -> Path:
    return config.data_dir() / "photos"


def photo_path(name: str) -> Path | None:
    """The file for a stored photo's name, or None for anything that isn't one (no path tricks)."""
    if not NAME.fullmatch(name):
        return None
    return folder() / name


def downscale(data: bytes, side: int = MAX_SIDE) -> bytes:
    """Any picture as a JPEG of at most `side` pixels, without the original's metadata."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("too many pixels")
                image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise api_error(400, "photo_unreadable")
    image.thumbnail((side, side))
    out = io.BytesIO()
    # Saved without exif=..., so nothing of the original's metadata is kept
    image.save(out, "JPEG", quality=85)
    return out.getvalue()


def store_photo(data: bytes) -> str:
    jpeg = downscale(data)
    name = f"{uuid.uuid4().hex}.jpg"
    folder().mkdir(parents=True, exist_ok=True)
    (folder() / name).write_bytes(jpeg)
    return name


def delete_photo(name: str | None) -> None:
    path = photo_path(name) if name else None
    if path is not None:
        path.unlink(missing_ok=True)
