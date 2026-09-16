import pytest

from apps.images.models import CarImage
from apps.publishing.models import BlogPost
from apps.publishing.services.seeding import sync_posts, vehicle_slug
from tests.factories import BlogPostFactory, CarImageFactory, CarSearchFactory, CsvImportFactory, UserFactory

pytestmark = pytest.mark.django_db

APPROVED = CarImage.ReviewStatus.APPROVED


def approved(make="Toyota", model="RAV4", year=1997, **fields):
    return CarImageFactory(make=make, model=model, year=year, review_status=APPROVED, **fields)


class TestSlug:
    def test_case_and_spacing_collapse_to_one_vehicle(self):
        assert vehicle_slug(1997, " toyota ", "rav4") == vehicle_slug(1997, "Toyota", "RAV4") == "1997-toyota-rav4"

    def test_a_missing_model_and_an_empty_one_are_the_same_vehicle(self):
        assert vehicle_slug(1997, "Toyota", None) == vehicle_slug(1997, "Toyota", "  ") == "1997-toyota"

    def test_accented_names_become_plain_ascii(self):
        assert vehicle_slug(1997, "Citroën", "2CV") == "1997-citroen-2cv"

    def test_a_very_long_name_still_fits_the_column_without_a_trailing_dash(self):
        slug = vehicle_slug(1997, "Make " * 60, "Model " * 60)

        assert len(slug) <= 255
        assert not slug.endswith("-")


class TestSyncPosts:
    def test_one_pending_post_per_vehicle(self):
        approved(year=1997)
        approved(year=1997)
        approved(year=1998)
        approved(model="Camry")

        result = sync_posts()

        assert (result.created, result.existing) == (3, 0)
        assert set(BlogPost.objects.values_list("slug", "status")) == {
            ("1997-toyota-rav4", BlogPost.Status.PENDING),
            ("1998-toyota-rav4", BlogPost.Status.PENDING),
            ("1997-toyota-camry", BlogPost.Status.PENDING),
        }

    def test_only_approved_images_create_posts(self):
        CarImageFactory(review_status=CarImage.ReviewStatus.PENDING)
        CarImageFactory(review_status=CarImage.ReviewStatus.REJECTED)

        assert sync_posts().created == 0
        assert not BlogPost.objects.exists()

    def test_running_again_creates_nothing_new(self):
        approved()
        approved(model="Camry")
        sync_posts()

        again = sync_posts()

        assert (again.created, again.existing) == (0, 2)
        assert BlogPost.objects.count() == 2

    def test_the_post_takes_its_spelling_and_links_from_the_first_approved_image(self):
        importer = CsvImportFactory()
        search = CarSearchFactory(csv_import=importer)
        first = approved(make="Toyota", model="RAV4", car_search=search)
        approved(make=" toyota ", model="rav4")
        user = UserFactory()

        sync_posts(requested_by=user)

        post = BlogPost.objects.get()
        assert (post.make, post.model, post.year) == ("Toyota", "RAV4", 1997)
        assert (post.car_search, post.csv_import, post.requested_by) == (first.car_search, importer, user)

    def test_a_vehicle_with_no_model_gets_a_post_with_no_model(self):
        approved(model=None, car_search=None)

        sync_posts()

        post = BlogPost.objects.get()
        assert (post.slug, post.model) == ("1997-toyota", None)

    def test_it_can_be_limited_to_one_import(self):
        wanted, other = CsvImportFactory(), CsvImportFactory()
        approved(model="RAV4", car_search=CarSearchFactory(csv_import=wanted))
        approved(model="Camry", car_search=CarSearchFactory(csv_import=other))

        sync_posts(csv_import=wanted)

        assert list(BlogPost.objects.values_list("slug", flat=True)) == ["1997-toyota-rav4"]

    def test_it_can_be_limited_to_selected_images(self):
        chosen = approved(model="RAV4")
        approved(model="Camry")

        sync_posts(CarImage.objects.filter(pk=chosen.pk))

        assert list(BlogPost.objects.values_list("slug", flat=True)) == ["1997-toyota-rav4"]

    def test_selected_images_still_count_only_when_approved(self):
        pending = CarImageFactory(review_status=CarImage.ReviewStatus.PENDING)

        assert sync_posts(CarImage.objects.filter(pk=pending.pk)).created == 0

    def test_an_existing_post_is_left_exactly_as_it_was(self):
        original_requester = UserFactory()
        post = BlogPostFactory(
            slug="1997-toyota-rav4", status=BlogPost.Status.PUBLISHED, wp_post_id=42, requested_by=original_requester
        )
        approved()

        sync_posts(requested_by=UserFactory())

        post.refresh_from_db()
        assert (post.status, post.wp_post_id, post.requested_by) == (
            BlogPost.Status.PUBLISHED,
            42,
            original_requester,
        )
