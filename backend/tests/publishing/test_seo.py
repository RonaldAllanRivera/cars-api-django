"""
The SEO fallbacks, implemented once. The WordPress plugin repeats this logic in
three places (its generate path, its apply path and its JavaScript); here it
lives in a single pure function.
"""

from apps.publishing.services.seo import fill_gaps

VEHICLE = {"year": 1997, "make": "Toyota", "model": "RAV4"}


def fill(**overrides):
    fields = {"title": "", "content": "", "seo_title": "", "seo_description": "", "seo_keywords": []}
    return fill_gaps(**{**fields, **VEHICLE, **overrides})


class TestSeoTitle:
    def test_what_the_model_wrote_is_kept(self):
        assert fill(title="Post title", seo_title="Model SEO title").seo_title == "Model SEO title"

    def test_an_empty_one_falls_back_to_the_post_title(self):
        assert fill(title="1997 Toyota RAV4 Review").seo_title == "1997 Toyota RAV4 Review"

    def test_whitespace_alone_counts_as_empty(self):
        assert fill(title="1997 Toyota RAV4 Review", seo_title="   \n ").seo_title == "1997 Toyota RAV4 Review"

    def test_a_long_title_is_shortened_at_a_word_boundary(self):
        # Character 60 falls inside "Started", so a plain slice would end on "St".
        title = "1997 Toyota RAV4 Review: A Compact Crossover That Quietly Started A Whole Segment"

        assert fill(title=title).seo_title == "1997 Toyota RAV4 Review: A Compact Crossover That Quietly"

    def test_a_single_word_longer_than_the_limit_is_cut_hard(self):
        assert fill(title="A" * 80).seo_title == "A" * 60

    def test_with_no_title_at_all_it_is_the_vehicle_name(self):
        assert fill().seo_title == "1997 Toyota RAV4"

    def test_a_runaway_model_value_is_capped_at_what_the_plugin_editor_accepts(self):
        assert len(fill(seo_title="word " * 100).seo_title) <= 120


class TestSeoDescription:
    def test_what_the_model_wrote_is_kept(self):
        assert fill(content="<p>Body.</p>", seo_description="Model description.").seo_description == (
            "Model description."
        )

    def test_it_comes_from_the_intro_paragraph_not_the_linked_subheadline(self):
        content = (
            '<h2><a href="https://example.test/">A Compact SUV Worth A Look</a></h2>'
            "<p>The <strong>1997 Toyota RAV4</strong> is a compact SUV.</p>"
            "<h2>Vehicle Overview</h2><p>More detail.</p>"
        )

        assert fill(content=content).seo_description == "The 1997 Toyota RAV4 is a compact SUV."

    def test_words_either_side_of_a_tag_do_not_run_together(self):
        assert fill(content="<h2>Overview</h2><div>Solid car</div>").seo_description == "Overview Solid car"

    def test_html_entities_are_decoded(self):
        """Left encoded, WordPress would escape the ampersand a second time in the meta tag."""
        assert fill(content="<p>Performance &amp; Efficiency</p>").seo_description == "Performance & Efficiency"

    def test_a_long_paragraph_is_shortened_at_a_word_boundary(self):
        paragraph = (
            "The 1997 Toyota RAV4 blends car-like handling with genuine off-road ability, "
            "making it a smart pick for drivers who want versatility without the bulk of a full-size SUV today."
        )

        assert fill(content=f"<p>{paragraph}</p>").seo_description == (
            "The 1997 Toyota RAV4 blends car-like handling with genuine off-road ability, "
            "making it a smart pick for drivers who want versatility without the bulk of a"
        )

    def test_no_content_means_no_description_rather_than_invented_copy(self):
        assert fill().seo_description == ""

    def test_a_runaway_model_value_is_capped_at_what_the_plugin_editor_accepts(self):
        assert len(fill(seo_description="word " * 200).seo_description) <= 320


class TestSeoKeywords:
    def test_what_the_model_wrote_is_kept_as_a_comma_separated_list(self):
        keywords = ["used toyota rav4", "rav4 for sale"]

        assert fill(seo_keywords=keywords).seo_keywords == "used toyota rav4, rav4 for sale"

    def test_blank_and_repeated_model_keywords_are_dropped(self):
        # Lower case first: a repeat that differs only by case must still be caught.
        keywords = ["rav4", " RAV4 ", "", "compact   SUV"]

        assert fill(seo_keywords=keywords).seo_keywords == "rav4, compact SUV"

    def test_without_model_keywords_they_are_derived_from_the_vehicle(self):
        assert fill().seo_keywords == "1997 Toyota RAV4, Toyota RAV4, used Toyota, used RAV4, Toyota RAV4 for sale"

    def test_a_vehicle_with_no_model_still_gets_sensible_keywords(self):
        assert fill(model=None).seo_keywords == "1997 Toyota, Toyota, used Toyota, Toyota for sale"

    def test_the_list_fits_the_plugin_limit_without_splitting_a_keyword(self):
        keywords = [f"keyword number {n} about the 1997 toyota rav4" for n in range(20)]

        result = fill(seo_keywords=keywords).seo_keywords

        assert len(result) <= 255
        assert all(part in keywords for part in result.split(", "))


def test_each_field_is_filled_independently():
    result = fill(title="Post title", seo_title="Model SEO title", content="<p>Intro.</p>")

    assert (result.seo_title, result.seo_description) == ("Model SEO title", "Intro.")
