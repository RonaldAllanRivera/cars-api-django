"""
The only code that talks to the Claude API.

Every call is reserved against the monthly budget before it is sent and
settled once its outcome is known, so no caller can spend outside the cap by
forgetting a step. What a failure is charged depends on what it proves:

- The request never left (connection refused): charged nothing, safe to retry.
- The API answered with an error: charged nothing, since no tokens were used.
  Retried only for server faults and overload.
- The answer arrived but was unusable (cut off, declined, off-schema): charged
  the tokens it reports, because they were billed.
- The response was lost after the request was sent (timeout, dropped
  connection, gateway timeout): the article may have been generated and billed,
  so the call is not retried and keeps its worst-case reservation.

The SDK's own retries are switched off for that last reason: it retries timeouts,
which could pay for the same article twice.
"""

import json
import time
from dataclasses import dataclass
from decimal import Decimal

import anthropic
import httpx2  # the transport under anthropic 1.x, used only to classify connection failures
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from apps.publishing.services import budget
from apps.publishing.services.prompt import POST_SCHEMA, Prompt

RESPONSE_EXCERPT_CHARS = 1024
# Rate limited or out of credit: every further call would fail the same way.
BLOCK_ERROR_TYPES = frozenset({"rate_limit_error", "billing_error"})
# The API failed before generating anything, so another attempt cannot double-bill.
RETRY_STATUSES = frozenset({500, 502, 503, 529})
# A gateway gave up waiting; the generation behind it may still have completed.
UNKNOWN_OUTCOME_STATUSES = frozenset({504})
# Raised before the request reached the API.
NOT_SENT = (httpx2.ConnectError, httpx2.ConnectTimeout, httpx2.PoolTimeout)
# Models whose safety classifiers can decline a request; the API re-runs a decline on
# a fallback model instead of returning it. Other models do not take the parameter.
REFUSAL_FALLBACK_MODELS = frozenset({"claude-opus-5", "claude-fable-5-1"})
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"
TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
TEXT_FIELDS = ("title", "content", "seo_title", "seo_description")
REDACTED = "[redacted]"


class ClaudeError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        error_type: str = "",
        retry_after_seconds: int | None = None,
        response_excerpt: str = "",
        request_id: str = "",
        outcome_unknown: bool = False,
    ):
        super().__init__(_redact(message))
        self.status = status
        self.error_type = error_type
        self.retry_after_seconds = retry_after_seconds
        self.response_excerpt = _redact(response_excerpt)
        self.request_id = request_id
        self.outcome_unknown = outcome_unknown


class ClaudeBlockedError(ClaudeError):
    """Rate limited or out of credit: stop asking until the API allows it."""


@dataclass(frozen=True)
class Generation:
    title: str
    content: str
    seo_title: str
    seo_description: str
    seo_keywords: list[str]
    model: str
    request_id: str
    stop_reason: str
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: Decimal
    usage_id: int


# Error pages and error trackers record each frame's locals; config holds the key.
@sensitive_variables("config")
def generate(prompt: Prompt, *, blog_post=None) -> Generation:
    """
    One post's fields from one call. Raises BudgetExceededError or
    UnknownModelPriceError before anything is sent, ClaudeBlockedError when rate
    limited or out of credit, and ClaudeError otherwise.
    """
    config = settings.ANTHROPIC
    if not config["api_key"]:
        raise ClaudeBlockedError("ANTHROPIC_API_KEY is not set, so nothing was sent.")

    params = _params(prompt, config)
    rates = budget.current_rates()
    estimate = budget.estimate_usd(params, max_tokens=config["max_tokens"], rates=rates)
    try:
        usage = budget.reserve(blog_post=blog_post, estimate_usd=estimate, model=config["model"], rates=rates)
    except budget.BudgetExceededError as refused:
        error_logger.record(
            ErrorEvent.Context.AI_BUDGET,
            refused,
            blog_post=blog_post,
            car_search=getattr(blog_post, "car_search_id", None),
            severity=ErrorEvent.Severity.WARNING,
            details={
                "spent_usd": str(refused.spent_usd),
                "cap_usd": str(refused.cap_usd),
                "estimate_usd": str(refused.estimate_usd),
            },
        )
        raise

    started = time.monotonic()
    try:
        message = _send(params, config)
        return _read(message, usage, _elapsed_ms(started))
    except ClaudeError as error:
        if error.outcome_unknown:
            budget.abandon(usage)
        else:
            # A no-op when _read already settled with the tokens an unusable answer used.
            budget.settle(usage, succeeded=False, request_id=error.request_id, latency_ms=_elapsed_ms(started))
        _log(error, blog_post)
        raise
    except Exception:
        # An unexpected failure proves nothing about what was billed.
        budget.abandon(usage)
        raise


def _params(prompt: Prompt, config: dict) -> dict:
    output_config = {"format": {"type": "json_schema", "schema": POST_SCHEMA}}
    if config["effort"]:
        output_config["effort"] = config["effort"]
    params = {
        "model": config["model"],
        "max_tokens": config["max_tokens"],
        # Identical for every vehicle, so it caches once a model's minimum prefix is met.
        "system": [{"type": "text", "text": prompt.system, "cache_control": {"type": "ephemeral"}}],
        "messages": prompt.messages,
        "output_config": output_config,
    }
    if config["model"] in REFUSAL_FALLBACK_MODELS:
        params.update(betas=[REFUSAL_FALLBACK_BETA], fallbacks="default")
    return params


def _http_client():
    """The SDK's default transport; tests replace this with a fake Messages API."""
    return None


@sensitive_variables("config")
def _send(params: dict, config: dict):
    attempts = max(1, int(config["retry_times"]) + 1)
    with anthropic.Anthropic(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=anthropic.Timeout(config["timeout"], connect=config["connect_timeout"]),
        max_retries=0,
        http_client=_http_client(),
    ) as client:
        for attempt in range(1, attempts + 1):
            try:
                return client.beta.messages.create(**params)
            except anthropic.APIConnectionError as error:
                # Includes APITimeoutError. Only a failure to connect proves nothing was sent.
                if not isinstance(error.__cause__, NOT_SENT):
                    raise ClaudeError(
                        f"The response from the Claude API was lost after the request was sent: {error}",
                        outcome_unknown=True,
                    ) from error
                if attempt == attempts:
                    raise ClaudeError(f"Could not reach the Claude API: {error}") from error
            except anthropic.APIStatusError as error:
                if error.type in BLOCK_ERROR_TYPES:
                    raise _status_error(error, ClaudeBlockedError) from error
                if error.status_code in UNKNOWN_OUTCOME_STATUSES:
                    raise _status_error(error, ClaudeError, outcome_unknown=True) from error
                if error.status_code not in RETRY_STATUSES or attempt == attempts:
                    raise _status_error(error, ClaudeError) from error
            time.sleep(config["retry_sleep_ms"] * 2 ** (attempt - 1) / 1000)
    raise AssertionError("unreachable: the last attempt always returns or raises")


def _read(message, usage, latency_ms: int) -> Generation:
    counts = _billed_tokens(message.usage)
    stop_reason = str(message.stop_reason or "")
    request_id = str(getattr(message, "_request_id", "") or "")
    receipt = {"request_id": request_id, "stop_reason": stop_reason, "latency_ms": latency_ms, **counts}

    fields = None
    if stop_reason == "max_tokens":
        problem = "The article hit ANTHROPIC_MAX_TOKENS and was cut off, so it was discarded."
    elif stop_reason == "refusal":
        problem = "The Claude API declined to write this post."
    else:
        text = next((block.text for block in message.content if block.type == "text"), None)
        fields = _fields(text)
        problem = None if fields else "The response did not match the post schema, so it was discarded."

    if problem:
        # Unusable, but the tokens behind it were billed.
        budget.settle(usage, succeeded=False, **receipt)
        raise ClaudeError(problem, request_id=request_id)

    settled = budget.settle(usage, succeeded=True, **receipt)
    return Generation(
        **{field: fields[field] for field in TEXT_FIELDS},
        seo_keywords=fields["seo_keywords"],
        model=str(message.model or settings.ANTHROPIC["model"]),
        cost_usd=settled.cost_usd,
        usage_id=settled.pk,
        **receipt,
    )


def _billed_tokens(usage) -> dict:
    """
    Every attempt's tokens. When a refusal fallback ran, top-level usage covers
    only the attempt that answered; the iterations are the billing record. A
    fallback model is never dearer than the model that fell back, so pricing
    them all at the configured model's rates can only over-count.
    """
    attempts = getattr(usage, "iterations", None) or [usage]
    return {field: sum(int(getattr(attempt, field, 0) or 0) for attempt in attempts) for field in TOKEN_FIELDS}


def _fields(text) -> dict | None:
    """The five post fields with the right types, or None. Structured output should guarantee this; verify anyway."""
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict) or not all(isinstance(parsed.get(field), str) for field in TEXT_FIELDS):
        return None
    keywords = parsed.get("seo_keywords")
    if not isinstance(keywords, list) or not all(isinstance(keyword, str) for keyword in keywords):
        return None
    return parsed


def _status_error(
    error: anthropic.APIStatusError, kind: type[ClaudeError], *, outcome_unknown: bool = False
) -> ClaudeError:
    detail = error.body.get("error", {}).get("message", "") if isinstance(error.body, dict) else ""
    retry_after = error.response.headers.get("retry-after", "").strip()
    return kind(
        f"The Claude API returned HTTP {error.status_code}" + (f": {detail}" if detail else "."),
        status=error.status_code,
        error_type=str(error.type or ""),
        retry_after_seconds=int(retry_after) if retry_after.isdigit() else None,
        response_excerpt=error.response.text[:RESPONSE_EXCERPT_CHARS],
        request_id=str(error.request_id or ""),
        outcome_unknown=outcome_unknown,
    )


def _log(error: ClaudeError, blog_post) -> None:
    error_logger.record(
        ErrorEvent.Context.AI_GENERATION,
        error,
        blog_post=blog_post,
        car_search=getattr(blog_post, "car_search_id", None),
        details={
            "http_status": error.status,
            "error_type": error.error_type,
            "request_id": error.request_id,
            "response_excerpt": error.response_excerpt,
            "model": settings.ANTHROPIC["model"],
            "outcome_unknown": error.outcome_unknown,
        },
    )


def _redact(text: str) -> str:
    """API error bodies can echo the key back; it must never reach the error log."""
    key = settings.ANTHROPIC["api_key"]
    return text.replace(key, REDACTED) if key and text else text


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
