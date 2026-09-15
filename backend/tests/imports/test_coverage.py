import pytest

from apps.imports.services.coverage import import_coverage
from apps.searches.models import CarSearch
from tests.factories import CarImageFactory, CarSearchFactory, CsvImportFactory

pytestmark = pytest.mark.django_db


def csv_search(csv_import, status: str, with_image: bool = False) -> CarSearch:
    search = CarSearchFactory(csv_import=csv_import, status=status)
    if with_image:
        CarImageFactory(car_search=search)
    return search


def test_it_separates_ran_and_found_nothing_from_never_ran():
    csv_import = CsvImportFactory()
    csv_search(csv_import, CarSearch.Status.COMPLETED, with_image=True)
    csv_search(csv_import, CarSearch.Status.COMPLETED)
    csv_search(csv_import, CarSearch.Status.PENDING)

    assert import_coverage(csv_import.pk) == {
        "total": 3,
        "searched": 2,
        "not_run": 1,
        "failed": 0,
        "with_images": 1,
        "no_images": 1,
    }


def test_it_counts_failures_separately():
    csv_import = CsvImportFactory()
    csv_search(csv_import, CarSearch.Status.FAILED)
    csv_search(csv_import, CarSearch.Status.COMPLETED, with_image=True)

    coverage = import_coverage(csv_import.pk)

    assert coverage["failed"] == 1
    assert coverage["searched"] == 2


def test_running_counts_as_not_run():
    csv_import = CsvImportFactory()
    csv_search(csv_import, CarSearch.Status.RUNNING)

    assert import_coverage(csv_import.pk)["not_run"] == 1


def test_a_search_with_several_images_is_counted_once():
    csv_import = CsvImportFactory()
    search = csv_search(csv_import, CarSearch.Status.COMPLETED, with_image=True)
    CarImageFactory(car_search=search)

    coverage = import_coverage(csv_import.pk)

    assert coverage["total"] == 1
    assert coverage["with_images"] == 1
    assert coverage["no_images"] == 0


def test_it_ignores_searches_from_other_imports():
    mine, theirs = CsvImportFactory(), CsvImportFactory()
    csv_search(mine, CarSearch.Status.COMPLETED, with_image=True)
    csv_search(theirs, CarSearch.Status.COMPLETED, with_image=True)

    assert import_coverage(mine.pk)["total"] == 1


def test_a_null_import_covers_every_csv_derived_search():
    csv_search(CsvImportFactory(), CarSearch.Status.COMPLETED, with_image=True)
    CarSearchFactory(csv_import=None, status=CarSearch.Status.COMPLETED)

    assert import_coverage(None)["total"] == 1
    assert import_coverage()["total"] == 1


def test_it_returns_none_when_there_is_nothing_to_describe():
    assert import_coverage(CsvImportFactory().pk) is None
