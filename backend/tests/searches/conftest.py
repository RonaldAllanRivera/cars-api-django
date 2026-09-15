import pytest
import respx

from tests.factories import CsvImportFactory, UserFactory


@pytest.fixture
def commons():
    """A respx router intercepting every HTTP call; nothing reaches the real Commons."""
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def csv_import(user):
    return CsvImportFactory(imported_by=user)
