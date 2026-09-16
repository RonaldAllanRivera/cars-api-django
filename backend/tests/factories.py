import factory
from django.utils import timezone

from apps.accounts import abilities
from apps.accounts.models import ApiToken, User
from apps.catalog.models import CarMake, CarModel
from apps.images.models import CarImage
from apps.imports.models import CsvImport
from apps.observability.models import ErrorEvent
from apps.publishing.models import BlogPost, BlogPostMedia
from apps.searches.models import CarSearch


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"User {n}")
    email = factory.Sequence(lambda n: f"user{n}@example.test")
    password = factory.PostGenerationMethodCall("set_password", "password")

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        if create:
            instance.save()


class CarMakeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CarMake
        django_get_or_create = ("name",)

    name = "Toyota"


class CarModelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CarModel

    make = factory.SubFactory(CarMakeFactory)
    name = factory.Sequence(lambda n: f"Model {n}")


class CsvImportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CsvImport

    original_filename = "queries.csv"
    total_rows = 1
    unique_combos = 1
    duplicates_skipped = 0
    imported_by = factory.SubFactory(UserFactory)


class CarSearchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CarSearch

    make = "Toyota"
    model = "RAV4"
    from_year = 1997
    to_year = 1997
    images_per_year = 5
    status = CarSearch.Status.PENDING
    requested_by = factory.SubFactory(UserFactory)


class CarImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CarImage

    car_search = factory.SubFactory(CarSearchFactory)
    make = factory.LazyAttribute(lambda o: o.car_search.make if o.car_search else "Toyota")
    model = factory.LazyAttribute(lambda o: o.car_search.model if o.car_search else "RAV4")
    year = factory.LazyAttribute(lambda o: o.car_search.from_year if o.car_search else 1997)
    provider_image_id = factory.Sequence(lambda n: f"page-{n}")
    title = factory.Sequence(lambda n: f"File:1997 Toyota RAV4 {n}.jpg")
    source_url = factory.Sequence(lambda n: f"https://upload.wikimedia.org/example-{n}.jpg")


class ErrorEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ErrorEvent

    context = ErrorEvent.Context.SEARCH_RUN
    severity = ErrorEvent.Severity.ERROR
    message = "The search run failed."
    occurred_at = factory.LazyFunction(timezone.now)


class BlogPostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BlogPost

    car_search = factory.SubFactory(CarSearchFactory)
    make = factory.LazyAttribute(lambda o: o.car_search.make if o.car_search else "Toyota")
    model = factory.LazyAttribute(lambda o: o.car_search.model if o.car_search else "RAV4")
    year = factory.LazyAttribute(lambda o: o.car_search.from_year if o.car_search else 1997)
    slug = factory.Sequence(lambda n: f"1997-toyota-rav4-{n}")


class BlogPostMediaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BlogPostMedia

    blog_post = factory.SubFactory(BlogPostFactory)
    car_image = factory.SubFactory(CarImageFactory)
    wp_media_id = factory.Sequence(lambda n: n + 1)
    wp_source_url = factory.Sequence(lambda n: f"https://wp.test/wp-content/uploads/image-{n}.jpg")
    filename = factory.Sequence(lambda n: f"1997-toyota-rav4-{n}.jpg")


def issue_token(user=None, token_abilities=None) -> tuple[User, str]:
    """Create (user, plain bearer token) with all abilities unless given."""
    user = user or UserFactory()
    _, plain = ApiToken.issue(user, "tests", list(abilities.ALL if token_abilities is None else token_abilities))
    return user, plain
