from datetime import timedelta

import httpx
import pytest
from django.utils import timezone

from apps.searches.models import CommonsCategoryLookup
from apps.searches.services.category_locator import locate_category
from apps.searches.services.wikimedia import WikimediaBlockedError, WikimediaClient
from tests.searches.fakes import category, category_name, existing_categories, invalid, missing, pages

pytestmark = pytest.mark.django_db


def test_it_returns_the_most_specific_category_that_exists(commons):
    commons.route().mock(side_effect=existing_categories(["Hyundai Santa Fe"]))

    assert locate_category("Hyundai", "Santa Fe XL AWD") == "Hyundai Santa Fe"


def test_candidates_are_probed_most_specific_first_and_the_walk_stops_at_the_first_hit(commons):
    route = commons.route().mock(side_effect=existing_categories(["Hyundai Santa Fe XL", "Hyundai Santa Fe"]))

    assert locate_category("Hyundai", "Santa Fe XL AWD") == "Hyundai Santa Fe XL"
    assert [category_name(call.request) for call in route.calls] == ["Hyundai Santa Fe XL AWD", "Hyundai Santa Fe XL"]


def test_a_resolved_category_is_persisted_and_not_re_probed(commons):
    route = commons.route().mock(side_effect=existing_categories(["Acura CL"]))

    assert locate_category("Acura", "2.3CL/3.0CL") == "Acura CL"
    calls_after_first = route.call_count

    assert locate_category("Acura", "2.3CL/3.0CL") == "Acura CL"
    assert route.call_count == calls_after_first, "A cached hit must cost no API calls."
    assert CommonsCategoryLookup.objects.filter(make="Acura", model="2.3CL/3.0CL", category="Acura CL").exists()


def test_a_miss_is_recorded_and_not_re_probed(commons):
    route = commons.route().mock(side_effect=existing_categories([]))

    assert locate_category("Saturn", "L200") is None
    calls_after_first = route.call_count

    assert locate_category("Saturn", "L200") is None
    assert route.call_count == calls_after_first, "A known miss must cost no API calls."
    assert CommonsCategoryLookup.objects.filter(make="Saturn", model="L200", category=None).exists()


def test_a_stale_miss_is_re_probed_and_refreshed(commons):
    CommonsCategoryLookup.objects.create(
        make="Acura", model="2.3CL/3.0CL", category=None, checked_at=timezone.now() - timedelta(days=31)
    )
    commons.route().mock(side_effect=existing_categories(["Acura CL"]))

    assert locate_category("Acura", "2.3CL/3.0CL") == "Acura CL"
    lookup = CommonsCategoryLookup.objects.get(make="Acura", model="2.3CL/3.0CL")
    assert lookup.category == "Acura CL"
    assert lookup.checked_at > timezone.now() - timedelta(minutes=1)


def test_a_miss_younger_than_the_ttl_is_trusted(commons, settings):
    settings.WIKIMEDIA = {**settings.WIKIMEDIA, "category_miss_ttl_days": 60}
    CommonsCategoryLookup.objects.create(
        make="Acura", model="2.3CL/3.0CL", category=None, checked_at=timezone.now() - timedelta(days=31)
    )
    route = commons.route().mock(side_effect=existing_categories(["Acura CL"]))

    assert locate_category("Acura", "2.3CL/3.0CL") is None
    assert route.call_count == 0


@pytest.mark.parametrize("model", [None, "", "  "])
def test_a_search_with_no_model_resolves_nothing_and_caches_nothing(commons, model):
    route = commons.route().mock(side_effect=existing_categories(["Acura"]))

    assert locate_category("Acura", model) is None
    assert route.call_count == 0
    assert CommonsCategoryLookup.objects.count() == 0, "A blank model must not be cached at all."


def test_a_model_carrying_an_illegal_title_character_falls_through_to_a_real_category(commons):
    def handler(request):
        name = category_name(request)
        title = f"Category:{name}"
        if ">" in name:
            return pages([invalid(title)], batchcomplete=True)
        if name == "Ford F150":
            return pages([category(title, files=0, subcats=0, redirect_to="Ford F-150")], batchcomplete=True)
        if name == "Ford F-150":
            return pages([category(title, files=0, subcats=17)], batchcomplete=True)
        return pages([missing(title)], batchcomplete=True)

    commons.route().mock(side_effect=handler)

    assert locate_category("Ford", "F150 2.7L 2WD GVWR>6649 LBS") == "Ford F-150"
    assert CommonsCategoryLookup.objects.filter(
        make="Ford", model="F150 2.7L 2WD GVWR>6649 LBS", category="Ford F-150"
    ).exists()


def test_a_resolved_category_never_expires(commons):
    CommonsCategoryLookup.objects.create(
        make="Acura", model="2.3CL/3.0CL", category="Acura CL", checked_at=timezone.now() - timedelta(days=3 * 365)
    )
    route = commons.route().mock(side_effect=existing_categories([]))

    assert locate_category("Acura", "2.3CL/3.0CL") == "Acura CL"
    assert route.call_count == 0


def test_a_block_while_probing_propagates_and_is_not_cached_as_a_miss(commons):
    commons.route().mock(return_value=httpx.Response(429, text="Too Many Requests"))

    with pytest.raises(WikimediaBlockedError):
        locate_category("Acura", "2.3CL/3.0CL")

    assert CommonsCategoryLookup.objects.count() == 0


def test_an_injected_client_is_used(commons):
    class StubClient(WikimediaClient):
        def resolve_category(self, name: str, depth: int = 0) -> str | None:
            return "Stubbed" if name == "Acura CL" else None

    assert locate_category("Acura", "CL", client=StubClient()) == "Stubbed"
    assert not commons.calls
