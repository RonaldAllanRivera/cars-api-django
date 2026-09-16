"""
Resizes originals to web-ready dimensions with Pillow.

Wikimedia refuses on-demand thumbnails for datacenter IPs, so batch downloads
fetch the original and shrink it here instead.
"""

import io
import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

WHITE = (255, 255, 255)


def resize_image(data: bytes, max_width: int, fallback_extension: str = "jpg", quality: int = 82) -> tuple[bytes, str]:
    """
    Scale down to `max_width` (never up) and re-encode as JPEG, returning
    (bytes, "jpg"). Anything Pillow cannot decode or encode comes back
    unchanged with `fallback_extension`, so an image is never lost.
    """
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image = ImageOps.exif_transpose(source)
            if image.width <= 0 or image.height <= 0:
                return data, fallback_extension
            if image.width > max_width:
                height = max(1, int(image.height * max_width / image.width + 0.5))
                image = image.resize((max_width, height), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            _flatten(image).save(buffer, format="JPEG", quality=quality)
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        logger.info("Keeping original image bytes; Pillow could not process them: %s", exc)
        return data, fallback_extension
    return buffer.getvalue(), "jpg"


def _flatten(image: Image.Image) -> Image.Image:
    """An RGB copy with any transparency composited onto white, since JPEG has no alpha."""
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")
    if image.mode in ("RGBA", "LA", "PA", "RGBa", "La"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, WHITE)
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image if image.mode == "RGB" else image.convert("RGB")
