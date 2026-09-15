"""Boot-time management commands used by bin/start.sh (no shell on Render's free tier)."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import User
from apps.catalog.management.commands.seed_catalog import CATALOG
from apps.catalog.models import CarMake, CarModel
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "owner@example.test")
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    monkeypatch.setenv("ADMIN_NAME", "Owner")


def run(command, *args):
    out = StringIO()
    call_command(command, *args, stdout=out)
    return out.getvalue()


def test_ensure_admin_is_a_no_op_without_env(monkeypatch):
    for key in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "ADMIN_NAME"):
        monkeypatch.delenv(key, raising=False)
    assert "skipping" in run("ensure_admin")
    assert not User.objects.exists()


def test_ensure_admin_requires_both_email_and_password(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "owner@example.test")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with pytest.raises(CommandError, match="ADMIN_PASSWORD"):
        run("ensure_admin")


def test_ensure_admin_creates_then_is_idempotent(admin_env):
    first = run("ensure_admin")
    user = User.objects.get(email="owner@example.test")
    assert user.is_superuser and user.is_staff and user.name == "Owner"
    assert user.check_password(PASSWORD)
    assert "created" in first
    assert PASSWORD not in first

    assert "unchanged" in run("ensure_admin")
    assert User.objects.count() == 1


def test_ensure_admin_promotes_and_resets_an_existing_user(admin_env):
    UserFactory(email="Owner@Example.test", is_staff=False, is_active=False)
    assert "updated" in run("ensure_admin")
    user = User.objects.get()
    assert user.is_superuser and user.is_active and user.check_password(PASSWORD)


def test_ensure_admin_rejects_a_weak_password_without_echoing_it(admin_env, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "12345678")
    with pytest.raises(CommandError, match="rejected") as exc:
        run("ensure_admin")
    assert "12345678" not in str(exc.value)
    assert not User.objects.exists()


def test_seed_catalog_is_idempotent():
    run("seed_catalog")
    run("seed_catalog")
    assert CarMake.objects.count() == len(CATALOG)
    assert CarModel.objects.count() == sum(len(models) for models in CATALOG.values())
    assert set(CarMake.objects.get(name="Toyota").models.values_list("name", flat=True)) == set(CATALOG["Toyota"])


def test_seed_catalog_if_empty_leaves_an_existing_catalog_alone():
    CarMake.objects.create(name="Lada")
    assert "skipping" in run("seed_catalog", "--if-empty")
    assert list(CarMake.objects.values_list("name", flat=True)) == ["Lada"]
