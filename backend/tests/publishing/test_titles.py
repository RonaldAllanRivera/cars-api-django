"""Mirrors web/src/format/__tests__/format.test.ts, so both sides clean titles alike."""

from apps.publishing.services.titles import clean_title


def test_the_commons_prefix_extension_duplicate_marker_and_underscores_are_stripped():
    assert clean_title("File:2001_Audi_RS4_B5_Avant - Flickr (3).jpg") == "2001 Audi RS4 B5 Avant - Flickr"


def test_a_parenthetical_that_is_real_content_is_kept():
    assert clean_title("File:Ferrari F40 (Geneva).JPG") == "Ferrari F40 (Geneva)"


def test_nothing_left_means_none_rather_than_an_empty_string():
    assert clean_title("File:.jpg") is None
    assert clean_title(None) is None
