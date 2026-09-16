"""
What each Claude model costs, so the monthly cap is enforced in dollars.

Prices live with the model name rather than in separate settings: changing
ANTHROPIC_MODEL then reprices the budget automatically, instead of relying on
someone remembering to change the rates too. A model missing from the list
refuses to run until all four prices are configured, so nothing is ever spent
unmetered.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

# Anthropic first-party list prices, USD per 1M tokens: (input, output).
LIST_PRICES = {
    "claude-haiku-4-5": ("1.00", "5.00"),
    "claude-sonnet-5": ("2.00", "10.00"),
    "claude-sonnet-4-6": ("3.00", "15.00"),
    "claude-opus-5": ("5.00", "25.00"),
    "claude-opus-4-8": ("5.00", "25.00"),
    "claude-opus-4-7": ("5.00", "25.00"),
    "claude-opus-4-6": ("5.00", "25.00"),
    "claude-fable-5": ("10.00", "50.00"),
    "claude-fable-5-1": ("10.00", "50.00"),
}
# 5-minute cache writes cost 1.25x input and reads 0.1x, except where a model sets its own read price.
CACHE_WRITE_MULTIPLIER = Decimal("1.25")
CACHE_READ_MULTIPLIER = Decimal("0.1")
CACHE_READ_PRICES = {"claude-fable-5-1": "0.25"}
OVERRIDE_KEYS = ("input_usd_per_1m", "output_usd_per_1m", "cache_write_usd_per_1m", "cache_read_usd_per_1m")


class UnknownModelPriceError(Exception):
    """Raised before any request, so an unpriced model can never spend outside the cap."""


@dataclass(frozen=True)
class Rates:
    """USD per 1M tokens."""

    input: Decimal
    output: Decimal
    cache_write: Decimal
    cache_read: Decimal


def rates_for(model: str) -> Rates:
    configured = [str(settings.ANTHROPIC.get(key, "")).strip() for key in OVERRIDE_KEYS]
    if all(configured):
        # Through str: Decimal(0.15) would carry the float's binary error into every total.
        return Rates(*(Decimal(value) for value in configured))

    if model not in LIST_PRICES:
        raise UnknownModelPriceError(
            f"No price is known for {model!r}. Set ANTHROPIC_INPUT_USD_PER_1M, ANTHROPIC_OUTPUT_USD_PER_1M, "
            "ANTHROPIC_CACHE_WRITE_USD_PER_1M and ANTHROPIC_CACHE_READ_USD_PER_1M so its spend can be capped."
        )
    input_price, output_price = (Decimal(price) for price in LIST_PRICES[model])
    cache_read = CACHE_READ_PRICES.get(model)
    return Rates(
        input=input_price,
        output=output_price,
        cache_write=input_price * CACHE_WRITE_MULTIPLIER,
        cache_read=Decimal(cache_read) if cache_read else input_price * CACHE_READ_MULTIPLIER,
    )
