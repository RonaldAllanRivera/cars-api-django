from decimal import Decimal

import pytest

from apps.publishing.services import pricing

OVERRIDES = ("input_usd_per_1m", "output_usd_per_1m", "cache_write_usd_per_1m", "cache_read_usd_per_1m")


def test_the_default_model_is_priced_from_the_built_in_list():
    rates = pricing.rates_for("claude-haiku-4-5")

    assert (rates.input, rates.output) == (Decimal("1.00"), Decimal("5.00"))


def test_cache_writes_cost_a_quarter_more_and_reads_a_tenth_of_input():
    rates = pricing.rates_for("claude-opus-5")

    assert (rates.cache_write, rates.cache_read) == (Decimal("6.25"), Decimal("0.50"))


def test_a_model_with_its_own_cache_read_price_uses_it():
    assert pricing.rates_for("claude-fable-5-1").cache_read == Decimal("0.25")


def test_configured_prices_override_the_list(settings):
    settings.ANTHROPIC = {**settings.ANTHROPIC, **dict(zip(OVERRIDES, ("2", "9", "2.5", "0.2"), strict=True))}

    rates = pricing.rates_for("claude-haiku-4-5")

    assert (rates.input, rates.output, rates.cache_write, rates.cache_read) == (
        Decimal("2"),
        Decimal("9"),
        Decimal("2.5"),
        Decimal("0.2"),
    )


def test_an_unknown_model_without_prices_refuses_rather_than_spending_unmetered():
    with pytest.raises(pricing.UnknownModelPriceError, match="claude-future-9"):
        pricing.rates_for("claude-future-9")


def test_an_unknown_model_needs_all_four_prices_not_just_some(settings):
    settings.ANTHROPIC = {**settings.ANTHROPIC, "input_usd_per_1m": "3", "output_usd_per_1m": "15"}

    with pytest.raises(pricing.UnknownModelPriceError):
        pricing.rates_for("claude-future-9")


def test_an_unknown_model_with_all_four_prices_is_allowed(settings):
    settings.ANTHROPIC = {**settings.ANTHROPIC, **dict(zip(OVERRIDES, ("3", "15", "3.75", "0.3"), strict=True))}

    assert pricing.rates_for("claude-future-9").output == Decimal("15")
