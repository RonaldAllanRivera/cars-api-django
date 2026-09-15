import re

import pytest

from apps.searches.services.matching import category_candidates, is_make_confirmed, model_year, normalize_model


class TestNormalizeModel:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param("2.2CL/3.0CL", "CL", id="displacement-prefix-and-slash-variants"),
            pytest.param("2.3CL/3.0CL", "CL", id="displacement-prefix-and-slash-variants-2"),
            pytest.param("2.5TL", "TL", id="single-segment-prefix"),
            pytest.param("3.2CL", "CL", id="single-segment-prefix-2"),
            pytest.param("Camry", "Camry", id="clean-name"),
            pytest.param("RAV4", "RAV4", id="clean-alphanumeric"),
            pytest.param("RSX Type-S", "RSX Type-S", id="clean-with-hyphen"),
            pytest.param("626", "626", id="pure-digits-no-decimal-point"),
            pytest.param("300", "300", id="pure-digits-no-decimal-point-2"),
            pytest.param("A4", "A4", id="letter-digit"),
            pytest.param("M3", "M3", id="letter-digit-2"),
            pytest.param("G37", "G37", id="letter-digits"),
            pytest.param("5.0", "5.0", id="stripping-leaves-nothing"),
            pytest.param("1.8T", "1.8T", id="stripping-leaves-one-char"),
            pytest.param("", "", id="empty"),
            pytest.param("   ", "", id="whitespace"),
            pytest.param("2.2CL/2.3CL/3.0CL", "CL", id="identical-segments-deduplicated"),
        ],
    )
    def test_normalizes_csv_model_strings(self, raw, expected):
        assert normalize_model(raw) == expected


def _index(candidates: list[str], name: str) -> int:
    assert name in candidates, f"{name!r} missing from {candidates!r}"
    return candidates.index(name)


class TestCategoryCandidates:
    def test_candidates_run_most_specific_first(self):
        candidates = category_candidates("Hyundai", "Santa Fe XL AWD")

        assert candidates[0] == "Hyundai Santa Fe XL AWD"
        assert _index(candidates, "Hyundai Santa Fe XL") < _index(candidates, "Hyundai Santa Fe")

    def test_the_engine_displacement_prefix_is_normalized_away(self):
        assert category_candidates("Acura", "2.3CL/3.0CL") == ["Acura CL"]

    @pytest.mark.parametrize(
        ("make", "model", "expected"),
        [
            ("Ford", "F150 Pickup 2WD FFV", "Ford F150"),
            ("BMW", "328i xDrive", "BMW 328i"),
            ("Cadillac", "STS AWD", "Cadillac STS"),
        ],
    )
    def test_drivetrain_and_body_qualifiers_are_stripped(self, make, model, expected):
        assert expected in category_candidates(make, model)

    def test_parentheticals_are_dropped(self):
        assert "BMW i4" in category_candidates("BMW", "i4 eDrive35 Gran Coupe (18 inch Wheels)")

    @pytest.mark.parametrize(
        ("make", "model"),
        [
            ("Mitsubishi", "Truck 2WD"),
            ("Ford", "Pickup 2WD"),
            ("Jeep", "Grand Cherokee 4WD"),
            ("Acura", "CL"),
            ("MINI", "Cooper Hardtop 2 door"),
        ],
    )
    def test_no_model_string_can_reduce_to_the_bare_make(self, make, model):
        candidates = category_candidates(make, model)

        assert candidates
        assert make not in [candidate.strip() for candidate in candidates]

    def test_a_single_token_model_yields_one_candidate(self):
        assert category_candidates("Saturn", "L200") == ["Saturn L200"]

    def test_a_model_beginning_with_a_qualifier_still_reaches_its_own_category(self):
        candidates = category_candidates("Volkswagen", "New Beetle Convertible")

        assert _index(candidates, "Volkswagen New Beetle") < _index(candidates, "Volkswagen Beetle")

    def test_a_qualifier_that_is_part_of_a_real_model_name_is_still_reachable(self):
        candidates = category_candidates("Chrysler", "New Yorker Turbo")

        assert _index(candidates, "Chrysler New Yorker") < _index(candidates, "Chrysler Yorker")

    @pytest.mark.parametrize(
        ("make", "model"),
        [("Volkswagen", "New Beetle Convertible"), ("Hyundai", "Santa Fe XL AWD"), ("Chrysler", "New Yorker Turbo")],
    )
    def test_candidates_are_ordered_from_most_to_least_specific(self, make, model):
        counts = [candidate.count(" ") for candidate in category_candidates(make, model)]

        assert counts == sorted(counts, reverse=True)

    def test_equal_length_candidates_keep_insertion_order(self):
        assert category_candidates("Volkswagen", "New Beetle Convertible") == [
            "Volkswagen New Beetle Convertible",
            "Volkswagen New Beetle",
            "Volkswagen New",
            "Volkswagen Beetle",
        ]

    def test_candidates_containing_mediawiki_illegal_characters_are_dropped(self):
        candidates = category_candidates("Ford", "F150 2.7L 2WD GVWR>6649 LBS")

        assert not [candidate for candidate in candidates if re.search(r"[#<>\[\]|{}]", candidate)]
        assert "Ford F150" in candidates

    @pytest.mark.parametrize(
        ("make", "model", "expected"),
        [("MINI", "Cooper 2 door S", "MINI Cooper S"), ("BMW", "X5 20 inch Wheels xLine", "BMW X5 xLine")],
    )
    def test_door_counts_and_wheel_sizes_are_stripped(self, make, model, expected):
        assert expected in category_candidates(make, model)


class TestModelYear:
    @pytest.mark.parametrize(
        ("title", "make", "expected"),
        [
            pytest.param("File:1999 Acura CL 3.0.jpg", "Acura", 1999, id="leading-year"),
            pytest.param("File:1999 Acura CL.jpg", "Acura", 1999, id="leading-year-2"),
            pytest.param("File:1996 Acura 3.0 CL 2017.1.23.jpg", "Acura", 1996, id="leading-year-with-trailing-date"),
            pytest.param("File:1997 Acura CL -- 01-28-2010.jpg", "Acura", 1997, id="trailing-dashed-photo-date"),
            pytest.param("File:1997 Acura CL, rear 8.2.20.jpg", "Acura", 1997, id="trailing-dotted-photo-date"),
            pytest.param("File:Blue 2005 Cadillac STS.jpg", "Cadillac", 2005, id="year-immediately-before-make"),
            pytest.param("File:2017.1.23 1997 Acura CL.jpg", "Acura", 1997, id="leading-photo-date-stripped"),
            pytest.param(
                "File:2015 Detroit Auto Show 2016 Ford Mustang.jpg", "Ford", 2016, id="make-adjacent-beats-event-year"
            ),
            pytest.param("File:2010 photo of a 1997 Acura CL.jpg", "Acura", 1997, id="make-adjacent-beats-leading"),
            pytest.param(
                "File:1963 Mercedes Benz 220 SEb Coupe.jpg", "Mercedes-Benz", 1963, id="hyphenated-make-with-space"
            ),
            pytest.param("File:1993 Mercedes 300 SE Auto.jpg", "Mercedes", 1993, id="single-word-make"),
            pytest.param("File:2019 Land Rover Range Rover.jpg", "Land Rover", 2019, id="two-word-make"),
        ],
    )
    def test_extracts_the_model_year(self, title, make, expected):
        assert model_year(title, make) == expected

    @pytest.mark.parametrize(
        ("title", "make"),
        [
            pytest.param("File:1997-1999 Acura 3.0CL — 04-25-2026.jpg", "Acura", id="four-digit-range"),
            pytest.param("File:1998-1999 Acura CL -- 04-11-2012 1.JPG", "Acura", id="range-with-photo-date"),
            pytest.param("File:1998-99 Acura CL.JPG", "Acura", id="short-range"),
            pytest.param("File:1997\N{EN DASH}1999 Acura CL.jpg", "Acura", id="en-dash-range"),
            pytest.param("File:1997 \N{EM DASH} 99 Acura CL.jpg", "Acura", id="em-dash-range"),
            pytest.param("File:'98-'99 Acura CL.jpg", "Acura", id="apostrophe-range"),
            pytest.param("File:1st gen Acura CL.JPG", "Acura", id="no-year-ordinal"),
            pytest.param("File:First Acura CL.JPG", "Acura", id="no-year-word"),
            pytest.param("File:1st-Acura-CL-1.jpg", "Acura", id="no-year-hyphenated"),
            pytest.param("File:Clx.jpg", "Acura", id="no-year-no-make"),
            pytest.param("File:1023 Acura CL.jpg", "Acura", id="implausibly-early"),
            pytest.param("File:3500 Acura CL.jpg", "Acura", id="implausibly-late"),
            pytest.param("File:01-28-2010 Acura CL.jpg", "Acura", id="leading-dashed-photo-date-only"),
            pytest.param("File:8.2.20 Cadillac STS.jpg", "Cadillac", id="leading-dotted-photo-date-only"),
            pytest.param("File:2024 08 24 IMG 5653.JPG", "Honda", id="space-separated-upload-date"),
            pytest.param("File:2006 02 13 - College Park - Snowed In.jpg", "Honda", id="space-separated-date-text"),
            pytest.param("File:2016 Sebring DSC 8285 (28278812954).jpg", "Honda", id="race-year-without-make"),
            pytest.param("File:2010 ASA AutoX 4744 (5004598645).jpg", "Honda", id="event-year-without-make"),
            pytest.param("File:2019 Canadian International Auto Show (32198734577).jpg", "Honda", id="auto-show-year"),
            pytest.param(
                "File:2012 North American International Auto Show (6729665331).jpg", "Toyota", id="auto-show-year-2"
            ),
            pytest.param("File:1999 Acura CL.jpg", "  ", id="blank-make"),
        ],
    )
    def test_yields_none_when_no_exact_model_year_is_asserted(self, title, make):
        assert model_year(title, make) is None


class TestIsMakeConfirmed:
    @pytest.mark.parametrize(
        ("make", "title", "description", "categories"),
        [
            pytest.param("Toyota", "File:Toyota Camry 2020.jpg", None, None, id="make-in-title"),
            pytest.param("ACURA", "File:acura nsx 1999.jpg", None, None, id="case-insensitive"),
            pytest.param("Honda", "File:car.jpg", "A red Honda Civic on a road", None, id="make-in-description"),
            pytest.param("Mazda", "File:car.jpg", None, "Mazda MX-5|Cars in Japan", id="make-in-categories"),
            pytest.param("Honda", "File:car.jpg", "<p>A <b>Honda</b> Accord</p>", None, id="html-stripped"),
        ],
    )
    def test_confirms_when_the_make_is_named(self, make, title, description, categories):
        assert is_make_confirmed(make, title, description, categories) is True

    @pytest.mark.parametrize(
        ("make", "title", "description", "categories"),
        [
            pytest.param(
                "Acura", "File:Honda Accord CL3 europe.jpg", "Honda Accord coupe", "Honda Accord", id="make-absent"
            ),
            pytest.param("", "File:Toyota.jpg", None, None, id="empty-make"),
            pytest.param(None, "File:Toyota.jpg", None, None, id="null-make"),
            pytest.param("Toyota", None, None, None, id="no-haystack"),
        ],
    )
    def test_does_not_confirm(self, make, title, description, categories):
        assert is_make_confirmed(make, title, description, categories) is False

    def test_html_tags_cannot_fake_a_match(self):
        assert is_make_confirmed("Honda", "File:car.jpg", '<a title="Honda">A car</a>', None) is False
