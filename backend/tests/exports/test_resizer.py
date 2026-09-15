import io

from PIL import Image

from apps.exports.services.resizer import resize_image
from tests.exports.images import dimensions, encode_image


def test_resizes_a_large_image_down_to_max_width_keeping_aspect_ratio():
    original = encode_image(3000, 2000)

    data, extension = resize_image(original, 1600, "jpg")

    assert dimensions(data) == (1600, 1067)
    assert extension == "jpg"
    assert len(data) < len(original)


def test_does_not_upscale_images_already_within_max_width():
    original = encode_image(800, 600, fmt="PNG")

    data, extension = resize_image(original, 1600, "png")

    assert dimensions(data) == (800, 600)
    assert extension == "jpg"
    assert Image.open(io.BytesIO(data)).format == "JPEG"


def test_uses_the_configured_max_width():
    data, _ = resize_image(encode_image(2000, 1000), 1280, "jpg")

    assert dimensions(data)[0] == 1280


def test_respects_custom_jpeg_quality():
    original = encode_image(2000, 1500)

    low, _ = resize_image(original, 1600, "jpg", 30)
    high, _ = resize_image(original, 1600, "jpg", 95)

    assert len(high) > len(low)


def test_returns_original_bytes_and_fallback_extension_for_non_image_input():
    assert resize_image(b"this is not an image", 1600, "png") == (b"this is not an image", "png")


def test_returns_original_bytes_for_a_truncated_image():
    truncated = encode_image(400, 300)[:200]

    assert resize_image(truncated, 1600, "jpg") == (truncated, "jpg")


def test_flattens_transparency_onto_white():
    transparent = encode_image(40, 20, fmt="PNG", mode="RGBA", color=(0, 0, 0, 0))

    for max_width in (1600, 20):
        data, extension = resize_image(transparent, max_width, "png")

        assert extension == "jpg"
        with Image.open(io.BytesIO(data)) as image:
            assert image.mode == "RGB"
            red, green, blue = image.getpixel((5, 5))
        assert min(red, green, blue) > 245


def test_palette_images_with_transparency_are_flattened_too():
    palette = Image.new("P", (10, 10), 0)
    palette.putpalette([0, 0, 0] * 256)
    buffer = io.BytesIO()
    palette.save(buffer, format="GIF", transparency=0)

    data, _ = resize_image(buffer.getvalue(), 1600, "gif")

    with Image.open(io.BytesIO(data)) as image:
        assert min(image.convert("RGB").getpixel((5, 5))) > 245


def test_applies_exif_orientation_before_measuring_width():
    image = Image.new("RGB", (2000, 1000), "red")
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise on display
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)

    data, _ = resize_image(buffer.getvalue(), 800, "jpg")

    assert dimensions(data) == (800, 1600)
