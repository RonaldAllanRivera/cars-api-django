"""
The gallery and image credits added to a generated article.

Only approved images reach a post. The first becomes the featured image, which
the theme renders itself, so it is left out of the gallery; every image,
featured included, is credited at the end, because Commons licences require
attribution and themes often hide captions.

Markup follows WordPress core's own block output, so a draft opens in the block
editor as an editable gallery rather than an "unexpected content" warning.
Everything interpolated is escaped: Commons titles and attributions are text
anyone can edit.
"""

import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.utils.html import escape

from apps.publishing.services.titles import clean_title


@dataclass(frozen=True)
class GalleryImage:
    wp_media_id: int
    src: str
    alt: str
    title: str
    license: str
    attribution: str
    credit_url: str
    featured: bool = False


def gallery_images(blog_post) -> list[GalleryImage]:
    """A post's uploaded media, in position order, with credits read from their Commons source."""
    media = blog_post.media.select_related("car_image").order_by("position", "id")
    return [_from_media(item) for item in media]


def compose(content: str, images: list[GalleryImage], *, use_blocks: bool) -> str:
    """The gallery after the intro paragraph, the credits after everything else."""
    if not images:
        return content
    gallery = render_gallery(images, use_blocks=use_blocks)
    if gallery:
        head, closing, tail = content.partition("</p>")
        # Placed by rule rather than a placeholder in the prompt, which the model can drop.
        content = f"{head}{closing}\n\n{gallery}\n\n{tail}" if closing else f"{gallery}\n\n{content}"
    return f"{content}\n\n{render_credits(images, use_blocks=use_blocks)}"


def render_gallery(images: list[GalleryImage], *, use_blocks: bool) -> str:
    items = [_image_block(image, use_blocks) for image in images if not image.featured and _http_url(image.src)]
    if not items:
        return ""
    body = "\n".join(items)
    figure = f'<figure class="wp-block-gallery has-nested-images columns-default is-cropped">\n{body}\n</figure>'
    if not use_blocks:
        return figure
    return f'<!-- wp:gallery {{"linkTo":"none"}} -->\n{figure}\n<!-- /wp:gallery -->'


def render_credits(images: list[GalleryImage], *, use_blocks: bool) -> str:
    if not images:
        return ""
    if not use_blocks:
        items = "".join(f"<li>{_credit(image)}</li>" for image in images)
        return f'<h3>Image credits</h3>\n<ul class="ucs-image-credits">{items}</ul>'
    items = "\n".join(f"<!-- wp:list-item -->\n<li>{_credit(image)}</li>\n<!-- /wp:list-item -->" for image in images)
    return (
        '<!-- wp:heading {"level":3} -->\n<h3 class="wp-block-heading">Image credits</h3>\n<!-- /wp:heading -->\n\n'
        '<!-- wp:list {"className":"ucs-image-credits"} -->\n'
        f'<ul class="wp-block-list ucs-image-credits">{items}</ul>\n<!-- /wp:list -->'
    )


def _image_block(image: GalleryImage, use_blocks: bool) -> str:
    caption = " — ".join(part for part in (image.title, image.license, image.attribution) if part)
    figure = (
        f'<figure class="wp-block-image size-large"><img src="{escape(image.src)}" alt="{escape(image.alt)}" '
        f'class="wp-image-{int(image.wp_media_id)}"/>'
        f'<figcaption class="wp-element-caption">{escape(caption)}</figcaption></figure>'
    )
    if not use_blocks:
        return figure
    attributes = json.dumps(
        {"id": int(image.wp_media_id), "sizeSlug": "large", "linkDestination": "none"}, separators=(",", ":")
    )
    return f"<!-- wp:image {attributes} -->\n{figure}\n<!-- /wp:image -->"


def _credit(image: GalleryImage) -> str:
    """Title (linked to its source), author and licence: the attribution Commons licences ask for."""
    url = _http_url(image.credit_url)
    title = escape(image.title)
    named = f'<a href="{escape(url)}" rel="nofollow noopener">{title}</a>' if url else title
    by = f" by {escape(image.attribution)}" if image.attribution else ""
    licence = f", {escape(image.license)}" if image.license and image.attribution else ""
    licence = licence or (f" — {escape(image.license)}" if image.license else "")
    return f"{named}{by}{licence}"


def _http_url(url: str) -> str | None:
    """Only http(s) links are rendered: a javascript: URL in an href would run in the reader's browser."""
    parts = urlsplit(url or "")
    return url if parts.scheme in {"http", "https"} and parts.netloc else None


def _from_media(item) -> GalleryImage:
    source = item.car_image
    return GalleryImage(
        wp_media_id=item.wp_media_id,
        src=item.wp_source_url,
        alt=item.alt_text,
        title=(clean_title(source.title) if source else None) or item.caption or item.filename,
        license=(source.license or "") if source else "",
        attribution=(source.attribution or "") if source else "",
        credit_url=item.credit_url,
        featured=item.is_featured,
    )
