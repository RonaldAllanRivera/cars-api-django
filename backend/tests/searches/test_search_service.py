import httpx
import pytest

from apps.images.models import CarImage
from apps.searches.models import CarSearch, CommonsCategoryLookup
from apps.searches.services.search_service import (
    create_search,
    find_existing_completed_search,
    refresh_search,
    run_search,
)
from apps.searches.services.wikimedia import WikimediaBlockedError
from tests.factories import CarImageFactory, CarSearchFactory
from tests.searches.fakes import existing_categories, image_page, pages

pytestmark = pytest.mark.django_db

# Titles as they really appear in Category:Acura CL YA1.
ACURA_CL_FILES = [
    (1, "File:1997 Acura CL -- 01-28-2010.jpg"),
    (2, "File:1997 Acura CL, rear 8.2.20.jpg"),
    (3, "File:1998-1999 Acura CL -- 04-11-2012 1.JPG"),
    (4, "File:'98-'99 Acura CL.jpg"),
    (5, "File:1999 Acura CL 3.0.jpg"),
    (6, "File:1999 Acura CL.jpg"),
    (7, "File:1st gen Acura CL.JPG"),
    (8, "File:Clx.jpg"),
]


@pytest.fixture
def acura_cl(commons):
    """Commons with only Category:Acura CL, holding the real CL YA1 titles."""
    return commons.route().mock(
        side_effect=existing_categories(
            ["Acura CL"], files=lambda request: pages(image_page(pid, title) for pid, title in ACURA_CL_FILES)
        )
    )


def _search(user, **fields) -> CarSearch:
    defaults = {"make": "Acura", "model": "2.3CL/3.0CL", "from_year": 1997, "to_year": 1997, "images_per_year": 10}
    return create_search(requested_by=user, **{**defaults, **fields})


def _titles(search: CarSearch) -> list[str]:
    return sorted(CarImage.objects.filter(car_search=search).values_list("title", flat=True))


class TestCreateSearch:
    def test_reversed_years_are_swapped_and_the_search_starts_pending(self, user, csv_import):
        search = create_search(
            requested_by=user, csv_import=csv_import, make="Acura", model="CL", from_year=1999, to_year=1997
        )

        search.refresh_from_db()
        assert (search.from_year, search.to_year) == (1997, 1999)
        assert search.status == CarSearch.Status.PENDING
        assert search.requested_by == user
        assert search.csv_import == csv_import
        assert search.images_per_year == 10

    def test_unknown_fields_are_rejected(self, user):
        with pytest.raises(TypeError, match="status"):
            create_search(requested_by=user, make="Acura", from_year=1997, to_year=1997, status="completed")


class TestFindExistingCompletedSearch:
    FIELDS = {
        "make": "Toyota",
        "model": "RAV4",
        "from_year": 1997,
        "to_year": 1997,
        "color": None,
        "transmission": None,
        "transparent_background": False,
        "images_per_year": 5,
    }

    def test_returns_the_newest_completed_exact_match(self, user):
        CarSearchFactory(requested_by=user, status=CarSearch.Status.COMPLETED, **self.FIELDS)
        newest = CarSearchFactory(requested_by=user, status=CarSearch.Status.COMPLETED, **self.FIELDS)
        CarSearchFactory(requested_by=user, status=CarSearch.Status.PENDING, **self.FIELDS)

        assert find_existing_completed_search(**self.FIELDS) == newest

    @pytest.mark.parametrize(
        "difference",
        [
            {"model": None},
            {"color": "red"},
            {"transmission": "manual"},
            {"transparent_background": True},
            {"images_per_year": 6},
            {"to_year": 1998},
        ],
    )
    def test_any_differing_field_is_not_a_match(self, user, difference):
        CarSearchFactory(requested_by=user, status=CarSearch.Status.COMPLETED, **{**self.FIELDS, **difference})

        assert find_existing_completed_search(**self.FIELDS) is None

    def test_null_fields_match_null(self, user):
        fields = {**self.FIELDS, "model": None}
        match = CarSearchFactory(requested_by=user, status=CarSearch.Status.COMPLETED, **fields)

        assert find_existing_completed_search(**fields) == match


class TestExactYearImages:
    def test_each_year_gets_only_photographs_naming_that_year(self, user, acura_cl):
        search = run_search(_search(user))

        assert _titles(search) == ["File:1997 Acura CL -- 01-28-2010.jpg", "File:1997 Acura CL, rear 8.2.20.jpg"]

    def test_a_year_named_only_inside_a_range_stores_nothing(self, user, acura_cl):
        search = run_search(_search(user, from_year=1998, to_year=1998))

        search.refresh_from_db()
        assert _titles(search) == []
        assert search.status == CarSearch.Status.COMPLETED, "An empty result is a completed search, not a failed one."
        assert search.commons_category == "Acura CL", "The category resolved; it simply had no 1998 photograph."

    def test_adjacent_years_never_share_a_photograph(self, user, acura_cl):
        first = run_search(_search(user, from_year=1997, to_year=1997))
        second = run_search(_search(user, from_year=1999, to_year=1999))

        a = set(CarImage.objects.filter(car_search=first).values_list("provider_image_id", flat=True))
        b = set(CarImage.objects.filter(car_search=second).values_list("provider_image_id", flat=True))
        assert a
        assert b
        assert not a & b, "A title naming 1997 cannot also name 1999."

    def test_the_concept_car_is_not_reachable(self, user, acura_cl):
        search = run_search(_search(user, from_year=1999, to_year=1999))

        assert "File:Clx.jpg" not in _titles(search)

    def test_images_per_year_limits_what_survives_the_year_filter_not_the_fetch(self, user, acura_cl):
        search = run_search(_search(user, from_year=1999, to_year=1999, images_per_year=1))

        titles = _titles(search)
        assert len(titles) == 1
        assert "1999" in titles[0], "The one stored image must still be a 1999 car, not an arbitrary first file."

    def test_images_per_year_applies_to_each_year_of_a_range(self, user, acura_cl):
        search = run_search(_search(user, from_year=1997, to_year=1999, images_per_year=1))

        years = sorted(CarImage.objects.filter(car_search=search).values_list("year", flat=True))
        assert years == [1997, 1999]

    def test_a_model_with_no_category_stores_nothing(self, user, acura_cl):
        search = run_search(_search(user, make="Saturn", model="L200", from_year=2003, to_year=2003))

        search.refresh_from_db()
        assert _titles(search) == []
        assert search.commons_category is None
        assert search.status == CarSearch.Status.COMPLETED

    def test_stored_images_carry_the_search_and_file_details(self, user, commons):
        extmetadata = {"Categories": {"value": "Acura CL|Coupes"}, "LicenseShortName": {"value": "CC BY 2.0"}}
        page = image_page(42, "File:1997 Acura CL -- 01-28-2010.jpg", extmetadata=extmetadata)
        commons.route().mock(side_effect=existing_categories(["Acura CL"], files=lambda request: pages([page])))

        search = run_search(_search(user, color="silver", transparent_background=True))

        image = CarImage.objects.get(car_search=search)
        assert image.year == 1997
        assert (image.make, image.model, image.color) == ("Acura", "2.3CL/3.0CL", "silver")
        assert image.transparent_background is True
        assert (image.provider, image.provider_image_id) == ("wikimedia", "42")
        assert image.source_url == "https://example.com/42.jpg"
        assert image.thumbnail_url == "https://example.com/42-thumb.jpg"
        assert (image.width, image.height, image.license) == (800, 600, "CC BY 2.0")
        assert image.make_confirmed is True
        assert image.year_confirmed is True
        assert image.download_status == CarImage.DownloadStatus.NOT_DOWNLOADED
        assert image.metadata == page

    def test_a_make_spelled_differently_in_the_title_is_stored_but_left_unconfirmed(self, user, commons):
        # The year matcher accepts "Mercedes Benz" for "Mercedes-Benz"; the make check is a plain substring test.
        page = image_page(43, "File:1963 Mercedes Benz 220 SEb Coupe.jpg")
        commons.route().mock(
            side_effect=existing_categories(["Mercedes-Benz 220"], files=lambda request: pages([page]))
        )

        search = run_search(_search(user, make="Mercedes-Benz", model="220", from_year=1963, to_year=1963))

        image = CarImage.objects.get(car_search=search)
        assert image.make_confirmed is False
        assert image.year_confirmed is True


class TestRunSearchTransaction:
    def test_the_category_lookup_survives_a_failed_search(self, user, commons):
        commons.route().mock(
            side_effect=existing_categories(["Acura CL"], files=lambda request: httpx.Response(429, text="Slow down"))
        )
        search = _search(user)

        with pytest.raises(WikimediaBlockedError):
            run_search(search)

        assert CommonsCategoryLookup.objects.filter(make="Acura", category="Acura CL").exists()
        search.refresh_from_db()
        assert search.status == CarSearch.Status.PENDING, "The running status rolls back with the transaction."
        assert search.commons_category is None


class TestSharedImageOwnership:
    @pytest.fixture
    def shared_file(self, commons):
        page = image_page(4242, "File:1997 Toyota RAV4.jpg", extmetadata={"Categories": {"value": "Toyota RAV4"}})
        return commons.route().mock(
            side_effect=existing_categories(["Toyota RAV4"], files=lambda request: pages([page]))
        )

    def test_a_second_search_does_not_steal_the_first_search_images(self, user, shared_file):
        a = run_search(_search(user, make="Toyota", model="RAV4"))
        b = run_search(_search(user, make="Toyota", model="RAV4"))

        assert CarImage.objects.filter(car_search=a).count() == 1, "The first search must keep its image."
        assert CarImage.objects.filter(car_search=b).count() == 1, "The second search must get its own row."

    def test_each_search_records_its_own_row_for_a_shared_image(self, user, shared_file):
        a = run_search(_search(user, make="Toyota", model="RAV4"))
        b = run_search(_search(user, make="Toyota", model="RAV4"))

        rows = CarImage.objects.filter(provider_image_id="4242")
        assert sorted(rows.values_list("car_search_id", flat=True)) == sorted([a.pk, b.pk])
        assert list(rows.values_list("year", flat=True)) == [1997, 1997]

    def test_re_running_the_same_search_does_not_duplicate_rows(self, user, shared_file):
        search = run_search(_search(user, make="Toyota", model="RAV4"))
        search.refresh_from_db()
        run_search(search)

        assert CarImage.objects.filter(car_search=search).count() == 1


class TestRefreshSearch:
    @pytest.fixture
    def search_with_images(self, user):
        search = CarSearchFactory(
            requested_by=user,
            make="Toyota",
            model="RAV4",
            from_year=2020,
            to_year=2020,
            images_per_year=10,
            status=CarSearch.Status.COMPLETED,
        )
        CarImageFactory.create_batch(3, car_search=search)
        return search

    def test_a_blocked_refresh_keeps_the_existing_images(self, commons, search_with_images):
        commons.route().mock(return_value=httpx.Response(429, text="Too Many Requests"))

        with pytest.raises(WikimediaBlockedError):
            refresh_search(search_with_images)

        assert CarImage.objects.filter(car_search=search_with_images).count() == 3, (
            "A failed refresh must not destroy the images it was replacing."
        )

    def test_a_blocked_refresh_marks_the_search_failed_rather_than_leaving_it_completed(
        self, commons, search_with_images
    ):
        commons.route().mock(return_value=httpx.Response(429, text="Too Many Requests"))

        with pytest.raises(WikimediaBlockedError):
            refresh_search(search_with_images)

        search_with_images.refresh_from_db()
        assert search_with_images.status == CarSearch.Status.FAILED

    def test_a_block_after_resolution_also_keeps_images_and_marks_failed(self, commons, search_with_images):
        commons.route().mock(
            side_effect=existing_categories(["Toyota RAV4"], files=lambda request: httpx.Response(503))
        )

        with pytest.raises(WikimediaBlockedError):
            refresh_search(search_with_images)

        search_with_images.refresh_from_db()
        assert search_with_images.status == CarSearch.Status.FAILED
        assert CarImage.objects.filter(car_search=search_with_images).count() == 3

    def test_a_successful_refresh_replaces_the_images(self, commons, search_with_images):
        page = image_page(999, "File:2020 Toyota RAV4 fresh.jpg", extmetadata={"Categories": {"value": "Toyota RAV4"}})
        commons.route().mock(side_effect=existing_categories(["Toyota RAV4"], files=lambda request: pages([page])))

        refreshed = refresh_search(search_with_images)

        assert _titles(search_with_images) == ["File:2020 Toyota RAV4 fresh.jpg"]
        refreshed.refresh_from_db()
        assert refreshed.status == CarSearch.Status.COMPLETED

    def test_a_refresh_bypasses_the_cached_file_listing_for_every_year(self, user, commons):
        listing = {"title": "File:2020 Toyota RAV4 old.jpg"}

        def files(request):
            year = request.url.params["gsrsearch"].rsplit(":", 1)[1]
            return pages([image_page(int(year), listing["title"].replace("2020", year))])

        commons.route().mock(side_effect=existing_categories(["Toyota RAV4"], files=files))
        search = run_search(_search(user, make="Toyota", model="RAV4", from_year=2020, to_year=2021))
        assert _titles(search) == ["File:2020 Toyota RAV4 old.jpg", "File:2021 Toyota RAV4 old.jpg"]

        listing["title"] = "File:2020 Toyota RAV4 new.jpg"
        refresh_search(search)

        assert _titles(search) == ["File:2020 Toyota RAV4 new.jpg", "File:2021 Toyota RAV4 new.jpg"]
