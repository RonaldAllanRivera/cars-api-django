import pytest

from apps.exports.services.csv_exporter import HEADER, export_rows
from apps.images.models import CarImage
from apps.searches.models import CarSearch
from tests.factories import CarImageFactory, CarSearchFactory, CsvImportFactory

pytestmark = pytest.mark.django_db


def test_exports_selected_images_with_renamed_filenames_and_metadata():
    search = CarSearchFactory(
        make="Toyota",
        model="RAV4",
        from_year=1997,
        to_year=1997,
        transmission="Automatic 4-spd",
        status=CarSearch.Status.COMPLETED,
        csv_import=CsvImportFactory(),
    )
    img1 = CarImageFactory(car_search=search, provider_image_id="A", source_url="https://example.com/a.jpg")
    img2 = CarImageFactory(car_search=search, provider_image_id="B", source_url="https://example.com/b.png")

    rows = list(export_rows([img1, img2]))

    assert len(rows) == 3
    assert rows[0] == ["Year", "Make", "Model", "Transmission", "Filename", "SourceUrl", "SearchId", "ImageId"]
    assert rows[0] == HEADER
    assert rows[1] == [
        "1997",
        "Toyota",
        "RAV4",
        "Automatic 4-spd",
        "1997 Toyota RAV4.jpg",
        "https://example.com/a.jpg",
        str(search.pk),
        str(img1.pk),
    ]
    assert rows[2][4] == "1997 Toyota RAV4 2.png"


def test_an_orphaned_image_exports_blank_search_columns():
    url = "https://example.com/path/no-extension"
    image = CarImageFactory(car_search=None, make="Honda", model=None, year=2010, source_url=url)

    rows = list(export_rows(CarImage.objects.filter(pk=image.pk)))

    assert rows[1] == ["2010", "Honda", "", "", "2010 Honda.jpg", url, "", str(image.pk)]


def test_an_empty_selection_yields_only_the_header():
    assert list(export_rows([])) == [HEADER]


def test_does_not_query_per_image_when_searches_are_preloaded(django_assert_num_queries):
    search = CarSearchFactory(transmission="Manual")
    CarImageFactory.create_batch(3, car_search=search)
    images = list(CarImage.objects.select_related("car_search"))

    with django_assert_num_queries(0):
        rows = list(export_rows(images))

    assert [row[3] for row in rows[1:]] == ["Manual"] * 3
