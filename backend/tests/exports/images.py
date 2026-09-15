"""Real images for resizer and ZIP tests."""

import io

from PIL import Image


def encode_image(width: int, height: int, fmt: str = "JPEG", mode: str = "RGB", color=None) -> bytes:
    """A real image with a gradient, so JPEG quality settings measurably change the output."""
    if color is not None:
        image = Image.new(mode, (width, height), color)
    else:
        gradient = Image.linear_gradient("L").resize((width, height))
        image = Image.merge("RGB", (gradient, gradient.transpose(Image.Transpose.FLIP_LEFT_RIGHT), gradient))
        image = image.convert(mode)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def dimensions(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size
