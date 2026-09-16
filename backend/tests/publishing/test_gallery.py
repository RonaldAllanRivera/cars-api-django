import pytest

from apps.publishing.services.gallery import GalleryImage, compose, gallery_images, render_credits, render_gallery
from tests.factories import BlogPostFactory, BlogPostMediaFactory, CarImageFactory


def image(n, *, featured=False, **overrides):
    fields = {
        "wp_media_id": 100 + n,
        "src": f"https://wp.test/wp-content/uploads/1997-toyota-rav4-{n}.jpg",
        "alt": f"1997 Toyota RAV4 view {n}",
        "title": f"1997 Toyota RAV4 view {n}",
        "license": "CC BY-SA 4.0",
        "attribution": "Jane Photographer",
        "credit_url": f"https://commons.wikimedia.org/wiki/File:1997_Toyota_RAV4_{n}.jpg",
        "featured": featured,
    }
    return GalleryImage(**{**fields, **overrides})


FEATURED, SECOND, THIRD = image(1, featured=True), image(2), image(3)
ARTICLE = "<h2>Headline</h2><p>Intro paragraph.</p><h2>Vehicle Overview</h2><p>More.</p>"


class TestGallery:
    def test_the_featured_image_is_left_out_because_the_theme_already_shows_it(self):
        html = render_gallery([FEATURED, SECOND, THIRD], use_blocks=True)

        assert "wp-image-101" not in html
        assert ("wp-image-102" in html, "wp-image-103" in html) == (True, True)

    def test_each_image_is_an_editable_gutenberg_image_block_inside_a_gallery_block(self):
        html = render_gallery([SECOND], use_blocks=True)

        assert html.startswith('<!-- wp:gallery {"linkTo":"none"} -->')
        assert '<!-- wp:image {"id":102,"sizeSlug":"large","linkDestination":"none"} -->' in html
        assert html.rstrip().endswith("<!-- /wp:gallery -->")

    def test_without_blocks_the_same_markup_is_emitted_without_block_comments(self):
        html = render_gallery([SECOND], use_blocks=False)

        assert "<!-- wp:" not in html
        assert '<figure class="wp-block-image size-large">' in html

    def test_every_gallery_image_carries_its_credit_in_a_caption(self):
        html = render_gallery([SECOND], use_blocks=True)

        assert "1997 Toyota RAV4 view 2 — CC BY-SA 4.0 — Jane Photographer" in html

    def test_only_a_featured_image_means_no_gallery_at_all(self):
        assert render_gallery([FEATURED], use_blocks=True) == ""


class TestCredits:
    @pytest.mark.parametrize("use_blocks", [True, False])
    def test_every_image_is_credited_including_the_featured_one(self, use_blocks):
        """A featured image has no caption, and themes often hide captions: licences cannot rely on them."""
        html = render_credits([FEATURED, SECOND], use_blocks=use_blocks)

        assert html.count("<li>") == 2
        assert "File:1997_Toyota_RAV4_1.jpg" in html

    def test_a_credit_names_title_author_licence_and_links_the_source(self):
        html = render_credits([SECOND], use_blocks=False)

        assert (
            '<a href="https://commons.wikimedia.org/wiki/File:1997_Toyota_RAV4_2.jpg" rel="nofollow noopener">'
            "1997 Toyota RAV4 view 2</a> by Jane Photographer, CC BY-SA 4.0"
        ) in html

    def test_a_missing_author_or_licence_is_left_out_rather_than_shown_blank(self):
        html = render_credits([image(2, attribution="", license="")], use_blocks=False)

        assert "1997 Toyota RAV4 view 2</a></li>" in html
        assert " by ," not in html

    def test_no_images_means_no_credits_heading(self):
        assert render_credits([], use_blocks=True) == ""


class TestEscaping:
    def test_commons_text_is_escaped_because_anyone_can_edit_it(self):
        hostile = image(2, attribution='<script>alert("x")</script>', title='"><img src=x onerror=alert(1)>')

        html = render_gallery([hostile], use_blocks=True) + render_credits([hostile], use_blocks=True)

        assert "<script>" not in html
        assert "<img src=x" not in html
        assert "&lt;script&gt;" in html

    def test_a_link_that_is_not_http_is_dropped_rather_than_rendered(self):
        html = render_credits([image(2, credit_url="javascript:alert(1)")], use_blocks=False)

        assert "javascript:" not in html
        assert "1997 Toyota RAV4 view 2 by Jane Photographer" in html


class TestCompose:
    def test_the_gallery_goes_after_the_intro_paragraph_and_the_credits_at_the_end(self):
        html = compose(ARTICLE, [FEATURED, SECOND], use_blocks=True)

        intro, gallery, overview, credits = (
            html.index("Intro paragraph."),
            html.index("wp:gallery"),
            html.index("Vehicle Overview"),
            html.index("Image credits"),
        )
        assert intro < gallery < overview < credits

    def test_an_article_without_a_paragraph_gets_the_gallery_first(self):
        html = compose("<h2>Only a heading</h2>", [FEATURED, SECOND], use_blocks=True)

        assert html.index("wp:gallery") < html.index("Only a heading")

    def test_without_images_the_article_is_unchanged(self):
        assert compose(ARTICLE, [], use_blocks=True) == ARTICLE


@pytest.mark.django_db
class TestFromStoredMedia:
    def test_uploaded_media_become_gallery_images_in_position_order_with_commons_credits(self):
        post = BlogPostFactory()
        car_image = CarImageFactory(
            title="File:1997_Toyota_RAV4_front (2).jpg", license="CC BY 2.0", attribution="Photo Person"
        )
        # Created out of position order, so position order differs from id order either way.
        BlogPostMediaFactory(blog_post=post, position=1, wp_media_id=8)
        BlogPostMediaFactory(
            blog_post=post,
            car_image=car_image,
            position=0,
            is_featured=True,
            wp_media_id=7,
            alt_text="1997 Toyota RAV4",
            credit_url="https://commons.wikimedia.org/wiki/File:1997_Toyota_RAV4_front_(2).jpg",
        )
        BlogPostMediaFactory(blog_post=post, position=2, wp_media_id=9)

        first, second, third = gallery_images(post)

        assert (first.wp_media_id, first.featured, second.wp_media_id, third.wp_media_id) == (7, True, 8, 9)
        assert (first.title, first.license, first.attribution, first.alt) == (
            "1997 Toyota RAV4 front",
            "CC BY 2.0",
            "Photo Person",
            "1997 Toyota RAV4",
        )

    def test_media_whose_source_image_was_deleted_still_renders_from_its_stored_caption(self):
        media = BlogPostMediaFactory(car_image=None, filename="1997-toyota-rav4-3.jpg", caption="Stored caption")

        (only,) = gallery_images(media.blog_post)

        assert (only.title, only.license, only.attribution) == ("Stored caption", "", "")
