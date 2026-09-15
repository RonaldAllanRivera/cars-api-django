import itertools
from types import SimpleNamespace

import httpx
import pytest

from apps.searches.services import wikimedia
from apps.searches.services.wikimedia import WikimediaBlockedError, WikimediaClient
from tests.searches.fakes import category, category_name, image_page, invalid, missing, pages, param


def _wikimedia_settings(settings, **overrides) -> None:
    settings.WIKIMEDIA = {**settings.WIKIMEDIA, **overrides}


class TestResolveCategory:
    def test_reports_an_existing_category_by_name_and_a_missing_one_as_none(self, commons):
        commons.route().mock(
            side_effect=lambda request: pages(
                [
                    category(param(request, "titles"), files=17, subcats=2)
                    if category_name(request) == "Acura CL"
                    else missing(param(request, "titles"))
                ]
            )
        )
        client = WikimediaClient()

        assert client.resolve_category("Acura CL") == "Acura CL"
        assert client.resolve_category("Acura Nonexistent") is None

    def test_probes_the_category_page_with_its_info_and_wikitext(self, commons):
        route = commons.route().mock(return_value=pages([category("Category:Acura CL")]))

        WikimediaClient().resolve_category("Acura CL")

        params = route.calls.last.request.url.params
        assert params["titles"] == "Category:Acura CL"
        assert params["prop"] == "categoryinfo|revisions"
        assert params["rvprop"] == "content"
        assert params["rvslots"] == "main"
        assert params["redirects"] == "1"

    def test_an_invalid_title_does_not_read_as_an_existing_category(self, commons):
        commons.route().mock(return_value=pages([invalid("Category:Ford F150 > 8500 lbs GVWR")], batchcomplete=True))

        assert WikimediaClient().resolve_category("Ford F150 > 8500 lbs GVWR") is None

    def test_an_empty_redirect_stub_does_not_count_as_an_existing_category(self, commons):
        commons.route().mock(return_value=pages([category("Category:Ford F150", files=0, subcats=0)]))

        assert WikimediaClient().resolve_category("Ford F150") is None

    def test_a_category_holding_only_subcategories_counts_as_existing(self, commons):
        commons.route().mock(return_value=pages([category("Category:Ford F-150", files=0, subcats=17)]))

        assert WikimediaClient().resolve_category("Ford F-150") == "Ford F-150"

    def test_a_hard_redirect_reports_the_target_name(self, commons):
        commons.route().mock(return_value=pages([category("Category:Ford F-150")]))

        assert WikimediaClient().resolve_category("Ford F150") == "Ford F-150"

    def test_a_category_redirect_is_followed_to_the_page_that_holds_the_files(self, commons):
        def handler(request):
            name = category_name(request)
            if name == "Ford F150":
                return pages([category("Category:Ford F150", files=0, subcats=0, redirect_to="Ford F-150")])
            return pages([category(f"Category:{name}", files=0, subcats=17)])

        commons.route().mock(side_effect=handler)

        assert WikimediaClient().resolve_category("Ford F150") == "Ford F-150"

    def test_a_redirect_target_written_with_its_namespace_is_followed(self, commons):
        def handler(request):
            if category_name(request) == "Old":
                return pages([category("Category:Old", files=0, subcats=0, redirect_to=" Category:New ")])
            return pages([category(param(request, "titles"))])

        route = commons.route().mock(side_effect=handler)

        assert WikimediaClient().resolve_category("Old") == "New"
        assert route.calls.last.request.url.params["titles"] == "Category:New"

    def test_a_category_redirect_cycle_terminates(self, commons):
        route = commons.route().mock(
            side_effect=lambda request: pages(
                [category(param(request, "titles"), files=0, subcats=0, redirect_to="Loop")]
            )
        )

        assert WikimediaClient().resolve_category("Loop") is None
        assert route.call_count == 3, "The original probe plus at most two redirect hops."

    def test_an_empty_response_is_a_miss(self, commons):
        commons.route().mock(return_value=httpx.Response(200, json={}))

        assert WikimediaClient().resolve_category("Acura CL") is None


class TestFilesInCategory:
    def test_a_year_scopes_the_search_and_keys_the_cache(self, commons):
        route = commons.route().mock(return_value=pages([image_page(1, "File:2012 Toyota Corolla.jpg")]))
        client = WikimediaClient()

        client.files_in_category("Toyota Corolla", 2012)
        assert route.calls.last.request.url.params["gsrsearch"] == 'deepcategory:"Toyota Corolla" intitle:2012'

        client.files_in_category("Toyota Corolla", 2013)
        assert route.call_count == 2, "Different years must not share a cache entry."

    def test_the_query_asks_for_image_info_from_the_deep_category(self, commons, settings):
        _wikimedia_settings(settings, category_page_size=50)
        route = commons.route().mock(return_value=pages([]))

        WikimediaClient().files_in_category("Acura CL", 1997)

        params = route.calls.last.request.url.params
        assert params["gsrsearch"] == 'deepcategory:"Acura CL" intitle:1997'
        assert params["generator"] == "search"
        assert params["prop"] == "imageinfo"
        assert params["gsrnamespace"] == "6"
        assert params["gsrlimit"] == "50"
        assert params["iiprop"] == "url|size|mime|extmetadata"
        assert params["iiurlwidth"] == "1200"

    def test_files_are_mapped_to_image_dicts(self, commons):
        page = image_page(1, "File:1997 Acura CL.jpg")
        commons.route().mock(return_value=pages([page]))

        files = WikimediaClient().files_in_category("Acura CL", 1997)

        assert files == [
            {
                "provider": "wikimedia",
                "provider_image_id": "1",
                "title": "File:1997 Acura CL.jpg",
                "description": None,
                "source_url": "https://example.com/1.jpg",
                "thumbnail_url": "https://example.com/1-thumb.jpg",
                "width": 800,
                "height": 600,
                "mime": "image/jpeg",
                "license": None,
                "attribution": None,
                "metadata": page,
            }
        ]

    def test_licence_description_and_attribution_come_from_extmetadata(self, commons):
        page = image_page(
            7,
            "File:1997 Acura CL.jpg",
            extmetadata={
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                "ImageDescription": {"value": "  A <b>1997</b> Acura CL  "},
                "Artist": {
                    "value": '<a rel="nofollow" class="external text" href="https://flickr.com/x">Jane&nbsp;Doe</a>'
                },
                "Credit": {"value": "   "},
                "UsageTerms": {"value": "Creative Commons Attribution-Share Alike 4.0"},
            },
        )
        del page["imageinfo"][0]["thumburl"]
        commons.route().mock(return_value=pages([page]))

        [image] = WikimediaClient().files_in_category("Acura CL", 1997)

        assert image["license"] == "CC BY-SA 4.0"
        assert image["description"] == "A 1997 Acura CL", "Commons HTML is stored as plain text for every client."
        assert image["attribution"] == "Jane Doe | Creative Commons Attribution-Share Alike 4.0"
        assert image["thumbnail_url"] == image["source_url"], "Without a thumbnail the original URL stands in."

    def test_non_image_files_are_excluded(self, commons):
        no_image_info = {"pageid": 3, "title": "File:Broken.jpg"}
        commons.route().mock(
            return_value=pages(
                [
                    image_page(1, "File:Trade-in-vehicles.pdf", "application/pdf"),
                    image_page(2, "File:Toyota Camry car.jpg"),
                    no_image_info,
                ]
            )
        )

        files = WikimediaClient().files_in_category("Toyota Camry", 2020)

        assert [file["title"] for file in files] == ["File:Toyota Camry car.jpg"]
        assert files[0]["mime"] == "image/jpeg"

    def test_pagination_echoes_the_whole_continue_object(self, commons):
        def handler(request):
            if param(request, "iicontinue") is None:
                return pages(
                    [image_page(1, "File:1997 Acura CL.jpg")],
                    **{"continue": {"iicontinue": "Second.jpg|20210805222232", "continue": "||"}},
                )
            return pages([image_page(2, "File:1997 Acura CL rear.jpg")])

        route = commons.route().mock(side_effect=handler)

        files = WikimediaClient().files_in_category("Acura CL", 1997)

        assert len(files) == 2, "A continued response must be followed, not treated as the end."
        assert route.call_count == 2
        second = route.calls.last.request.url.params
        assert second["iicontinue"] == "Second.jpg|20210805222232"
        assert second["continue"] == "||"
        assert second["gsrsearch"] == 'deepcategory:"Acura CL" intitle:1997'

    def test_a_file_repeated_across_pages_is_returned_once(self, commons):
        def handler(request):
            if param(request, "iicontinue") is None:
                return pages(
                    [image_page(1, "File:1997 Acura CL.jpg")],
                    **{"continue": {"iicontinue": "Repeat.jpg|1", "continue": "||"}},
                )
            return pages([image_page(1, "File:1997 Acura CL.jpg"), image_page(2, "File:1997 Acura CL 2.jpg")])

        commons.route().mock(side_effect=handler)

        files = WikimediaClient().files_in_category("Acura CL", 1997)

        assert [file["provider_image_id"] for file in files] == ["1", "2"]

    def test_pagination_stops_when_a_continuation_never_ends(self, commons):
        counter = itertools.count(1)

        def handler(request):
            n = next(counter)
            return pages(
                [image_page(n, f"File:1997 Acura CL {n}.jpg")],
                **{"continue": {"iicontinue": f"page-{n}|1", "continue": "||"}},
            )

        route = commons.route().mock(side_effect=handler)

        files = WikimediaClient().files_in_category("Acura CL", 1997)

        assert route.call_count == 10, "The request loop must be hard-bounded."
        assert len(files) == 10

    def test_paging_stops_once_the_file_cap_is_reached(self, commons, settings):
        _wikimedia_settings(settings, category_max_files=3)
        counter = itertools.count()

        def handler(request):
            n = next(counter)
            return pages(
                [image_page(n * 10 + i, f"File:1997 Acura CL {n}-{i}.jpg") for i in range(2)],
                **{"continue": {"iicontinue": f"page-{n}|1", "continue": "||"}},
            )

        route = commons.route().mock(side_effect=handler)

        files = WikimediaClient().files_in_category("Acura CL", 1997)

        assert route.call_count == 2
        assert len(files) == 3, "The result is truncated to category_max_files."

    def test_results_are_cached_per_category_and_year(self, commons):
        route = commons.route().mock(return_value=pages([image_page(1, "File:1997 Acura CL.jpg")]))
        client = WikimediaClient()

        first = client.files_in_category("Acura CL", 1997)
        second = WikimediaClient().files_in_category("Acura CL", 1997)

        assert route.call_count == 1
        assert first == second

    def test_an_empty_category_is_cached_too(self, commons):
        route = commons.route().mock(return_value=pages([]))
        client = WikimediaClient()

        client.files_in_category("Acura CL", 1997)
        client.files_in_category("Acura CL", 1997)

        assert route.call_count == 1

    def test_forgetting_a_category_forces_a_refetch(self, commons):
        route = commons.route().mock(return_value=pages([image_page(1, "File:1997 Acura CL.jpg")]))
        client = WikimediaClient()

        client.files_in_category("Acura CL", 1997)
        client.forget_category("Acura CL", 1997)
        client.files_in_category("Acura CL", 1997)

        assert route.call_count == 2

    def test_raising_the_file_cap_does_not_serve_a_shorter_cached_answer(self, commons, settings):
        route = commons.route().mock(return_value=pages([image_page(1, "File:1997 Acura CL.jpg")]))
        client = WikimediaClient()

        client.files_in_category("Acura CL", 1997)
        _wikimedia_settings(settings, category_max_files=1000)
        client.files_in_category("Acura CL", 1997)

        assert route.call_count == 2


class TestRequestPolicy:
    def test_every_request_carries_the_etiquette_parameters_user_agent_and_timeout(self, commons, settings):
        _wikimedia_settings(
            settings, user_agent="CarsImagesApi/1.0 (https://example.test; ops@example.test)", maxlag=5, timeout=7
        )
        route = commons.route().mock(return_value=httpx.Response(200, json={"query": {"search": []}}))

        WikimediaClient().files_in_category("Toyota RAV4", 1997)

        request = route.calls.last.request
        assert str(request.url).startswith(settings.WIKIMEDIA["base_url"])
        assert request.headers["User-Agent"] == "CarsImagesApi/1.0 (https://example.test; ops@example.test)"
        assert request.extensions["timeout"]["read"] == 7
        params = request.url.params
        assert params["action"] == "query"
        assert params["format"] == "json"
        assert params["formatversion"] == "2"
        assert params["origin"] == "*"
        assert params["maxlag"] == "5"

    def test_a_429_raises_blocked_with_the_retry_window_and_is_not_retried(self, commons):
        route = commons.route().mock(
            return_value=httpx.Response(429, text="Rate limit exceeded", headers={"Retry-After": "60"})
        )

        with pytest.raises(WikimediaBlockedError) as caught:
            WikimediaClient().files_in_category("Toyota RAV4", 1997)

        assert caught.value.status == 429
        assert caught.value.retry_after_seconds == 60
        assert "Rate limit" in caught.value.response_excerpt
        assert str(caught.value) == "Wikimedia returned HTTP 429 (Retry-After: 60)"
        assert route.call_count == 1

    @pytest.mark.parametrize("status", [403, 503])
    def test_other_block_statuses_raise_blocked_without_a_retry_window(self, commons, status):
        route = commons.route().mock(return_value=httpx.Response(status, text="Forbidden"))

        with pytest.raises(WikimediaBlockedError) as caught:
            WikimediaClient().resolve_category("Toyota RAV4")

        assert caught.value.status == status
        assert caught.value.retry_after_seconds is None
        assert str(caught.value) == f"Wikimedia returned HTTP {status} (Retry-After: n/a)"
        assert route.call_count == 1

    def test_a_non_numeric_retry_after_is_reported_as_unknown(self, commons):
        commons.route().mock(return_value=httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}))

        with pytest.raises(WikimediaBlockedError) as caught:
            WikimediaClient().resolve_category("Toyota RAV4")

        assert caught.value.retry_after_seconds is None

    def test_the_response_excerpt_is_capped_at_1024_characters(self, commons):
        commons.route().mock(return_value=httpx.Response(429, text="é" * 5000))

        with pytest.raises(WikimediaBlockedError) as caught:
            WikimediaClient().resolve_category("Toyota RAV4")

        assert caught.value.response_excerpt == "é" * 1024

    def test_a_server_error_is_retried_then_raised(self, commons):
        route = commons.route().mock(return_value=httpx.Response(500, text="Internal server error"))

        with pytest.raises(httpx.HTTPStatusError):
            WikimediaClient().resolve_category("Toyota RAV4")

        assert route.call_count == 3

    def test_a_transient_failure_recovers_on_retry(self, commons):
        route = commons.route().mock(
            side_effect=[
                httpx.ConnectError("connection reset"),
                httpx.Response(502),
                pages([category("Category:Toyota RAV4")]),
            ]
        )

        assert WikimediaClient().resolve_category("Toyota RAV4") == "Toyota RAV4"
        assert route.call_count == 3

    def test_a_persistent_connection_error_is_raised_after_the_retries(self, commons):
        route = commons.route().mock(side_effect=httpx.ConnectTimeout("timed out"))

        with pytest.raises(httpx.ConnectTimeout):
            WikimediaClient().resolve_category("Toyota RAV4")

        assert route.call_count == 3

    def test_retries_back_off_exponentially(self, commons, settings, monkeypatch):
        _wikimedia_settings(settings, retry_times=4, retry_sleep_ms=200)
        sleeps: list[float] = []
        monkeypatch.setattr(wikimedia, "time", SimpleNamespace(sleep=sleeps.append))
        commons.route().mock(return_value=httpx.Response(500))

        with pytest.raises(httpx.HTTPStatusError):
            WikimediaClient().resolve_category("Toyota RAV4")

        assert sleeps == [0.2, 0.4, 0.8]

    def test_a_body_that_is_not_json_reads_as_empty(self, commons):
        commons.route().mock(return_value=httpx.Response(200, text="<html>maintenance</html>"))

        assert WikimediaClient().resolve_category("Toyota RAV4") is None
