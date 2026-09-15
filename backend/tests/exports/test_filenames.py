import pytest

from apps.exports.services.filenames import (
    BaseNameSequence,
    build_filename,
    build_ranked,
    build_unique,
    extension_from_url,
)


def test_builds_basic_filename():
    assert build_filename(1997, "Toyota", "RAV4", "jpg") == "1997 Toyota RAV4.jpg"


def test_replaces_slash_with_dash():
    assert build_filename(1998, "Acura", "2.2CL/3.0CL", "jpg") == "1998 Acura 2.2CL - 3.0CL.jpg"


def test_replaces_all_unsafe_chars():
    name = build_filename(2024, "Make", 'A:B*C?D"E<F>G|H\\I', "png")

    for char in ':*?"<>|\\/':
        assert char not in name
    assert name == "2024 Make A - B - C - D - E - F - G - H - I.png"


def test_collapses_multiple_spaces():
    assert build_filename(2020, "Make  Name", "Model   X", "jpg") == "2020 Make Name Model X.jpg"


def test_caps_length_at_200_chars_plus_extension():
    name = build_filename(2024, "Toyota", "A" * 500, "jpg")

    assert name.endswith(".jpg")
    assert len(name.removesuffix(".jpg")) == 200


def test_length_cap_counts_characters_not_bytes():
    name = build_filename(2024, "Citroën", "é" * 500, "jpg")

    assert len(name.removesuffix(".jpg")) == 200


def test_extension_defaults_to_jpg_when_empty():
    assert build_filename(2015, "Mitsubishi", "Mirage", "") == "2015 Mitsubishi Mirage.jpg"
    assert build_filename(2015, "Mitsubishi", "Mirage", None) == "2015 Mitsubishi Mirage.jpg"


def test_extension_is_lowercased_and_stripped_of_unsafe_characters():
    assert build_filename(2015, "Mitsubishi", "Mirage", "JPEG") == "2015 Mitsubishi Mirage.jpeg"
    assert build_filename(2015, "Mitsubishi", "Mirage", ".p/n g") == "2015 Mitsubishi Mirage.png"
    assert build_filename(2015, "Mitsubishi", "Mirage", "!!!") == "2015 Mitsubishi Mirage.jpg"


def test_a_missing_model_leaves_no_trailing_space():
    assert build_filename(2015, "Mitsubishi", None, "jpg") == "2015 Mitsubishi.jpg"


def test_trim_leading_trailing_whitespace():
    assert build_filename(2020, "  Toyota  ", "  RAV4  ", "jpg") == "2020 Toyota RAV4.jpg"


def test_dedup_returns_base_for_first_occurrence():
    used: set[str] = set()

    assert build_unique(1997, "Toyota", "RAV4", "jpg", used) == "1997 Toyota RAV4.jpg"
    assert "1997 Toyota RAV4.jpg" in used


def test_dedup_appends_counter_on_collision():
    used = {"1997 Toyota RAV4.jpg"}

    assert build_unique(1997, "Toyota", "RAV4", "jpg", used) == "1997 Toyota RAV4 2.jpg"
    assert "1997 Toyota RAV4 2.jpg" in used


def test_dedup_continues_counting():
    used = {"1997 Toyota RAV4.jpg", "1997 Toyota RAV4 2.jpg", "1997 Toyota RAV4 3.jpg"}

    assert build_unique(1997, "Toyota", "RAV4", "jpg", used) == "1997 Toyota RAV4 4.jpg"


def test_build_ranked_returns_base_for_rank_one():
    assert build_ranked(1997, "Toyota", "RAV4", "jpg", 1) == "1997 Toyota RAV4.jpg"
    assert build_ranked(1997, "Toyota", "RAV4", "jpg", 0) == "1997 Toyota RAV4.jpg"


def test_build_ranked_appends_suffix_for_higher_ranks():
    assert build_ranked(1997, "Toyota", "RAV4", "jpg", 2) == "1997 Toyota RAV4 2.jpg"
    assert build_ranked(1997, "Toyota", "RAV4", "jpg", 5) == "1997 Toyota RAV4 5.jpg"


def test_base_name_sequence_shares_one_counter_across_extensions():
    names = BaseNameSequence()

    assert names.next(1997, "Toyota", "RAV4", "jpg") == "1997 Toyota RAV4.jpg"
    assert names.next(1997, "Toyota", "RAV4", "png") == "1997 Toyota RAV4 2.png"
    assert names.next(1997, "Toyota", "RAV4", "jpg") == "1997 Toyota RAV4 3.jpg"
    assert names.next(1998, "Toyota", "RAV4", "jpg") == "1998 Toyota RAV4.jpg"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/a.jpg", "jpg"),
        ("https://example.com/b.PNG?width=100#top", "PNG"),
        ("https://upload.wikimedia.org/wikipedia/commons/4/47/Foo.tar.gz", "gz"),
        ("https://example.com/no-extension", "jpg"),
        ("https://example.com/dir.d/file", "jpg"),
        ("", "jpg"),
    ],
)
def test_extension_from_url(url, expected):
    assert extension_from_url(url) == expected
