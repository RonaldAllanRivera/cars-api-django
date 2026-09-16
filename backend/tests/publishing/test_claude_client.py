"""Every test runs against a fake Messages API: nothing here spends real tokens."""

import json
from decimal import Decimal

import httpx2
import pytest
from django.views.debug import ExceptionReporter

from apps.observability.models import ErrorEvent
from apps.publishing.models import AiUsage, BudgetPeriod
from apps.publishing.services import budget, claude_client
from apps.publishing.services.pricing import UnknownModelPriceError
from apps.publishing.services.prompt import POST_SCHEMA, Prompt
from tests.factories import BlogPostFactory
from tests.publishing.fakes import FIELDS, api_error, message

pytestmark = pytest.mark.django_db

PROMPT = Prompt(system="Write the article.", messages=[{"role": "user", "content": '{"vehicle":{}}'}])


def usage() -> AiUsage:
    return AiUsage.objects.get()


class TestRequest:
    def test_the_response_is_constrained_to_the_post_schema(self, messages_api):
        messages_api.queue(message())

        claude_client.generate(PROMPT)

        body = messages_api.body()
        assert body["output_config"] == {"format": {"type": "json_schema", "schema": POST_SCHEMA}}
        assert (body["model"], body["max_tokens"], body["messages"]) == ("claude-haiku-4-5", 8000, PROMPT.messages)

    def test_the_instructions_are_sent_as_a_cacheable_system_prompt(self, messages_api):
        messages_api.queue(message())

        claude_client.generate(PROMPT)

        assert messages_api.body()["system"] == [
            {"type": "text", "text": PROMPT.system, "cache_control": {"type": "ephemeral"}}
        ]

    def test_the_key_is_sent_in_the_api_key_header(self, messages_api):
        messages_api.queue(message())

        claude_client.generate(PROMPT)

        assert messages_api.requests[-1].headers["x-api-key"] == "sk-ant-test"

    def test_the_model_comes_from_configuration(self, messages_api, settings):
        settings.ANTHROPIC = {**settings.ANTHROPIC, "model": "claude-sonnet-5"}
        messages_api.queue(message(model="claude-sonnet-5"))

        claude_client.generate(PROMPT)

        assert messages_api.body()["model"] == "claude-sonnet-5"

    def test_effort_is_sent_only_when_configured(self, messages_api, settings):
        """Haiku 4.5, the default model, rejects the parameter."""
        messages_api.queue(message())
        claude_client.generate(PROMPT)
        settings.ANTHROPIC = {**settings.ANTHROPIC, "effort": "low"}
        claude_client.generate(PROMPT)

        assert "effort" not in messages_api.body(0)["output_config"]
        assert messages_api.body(1)["output_config"]["effort"] == "low"

    def test_refusal_fallbacks_are_requested_only_for_models_that_support_them(self, messages_api, settings):
        messages_api.queue(message())
        claude_client.generate(PROMPT)
        settings.ANTHROPIC = {**settings.ANTHROPIC, "model": "claude-opus-5"}
        claude_client.generate(PROMPT)

        haiku, opus = messages_api.requests
        assert "fallbacks" not in json.loads(haiku.content)
        assert "anthropic-beta" not in haiku.headers
        assert json.loads(opus.content)["fallbacks"] == "default"
        assert opus.headers["anthropic-beta"] == "server-side-fallback-2026-07-01"


class TestSuccess:
    def test_the_post_fields_come_back_parsed(self, messages_api):
        messages_api.queue(message())

        generation = claude_client.generate(PROMPT)

        assert (generation.title, generation.content, generation.seo_keywords) == (
            FIELDS["title"],
            FIELDS["content"],
            ["used toyota rav4", "1997 rav4"],
        )
        assert (generation.seo_title, generation.seo_description) == (FIELDS["seo_title"], FIELDS["seo_description"])

    def test_blocks_before_the_answer_are_skipped(self, messages_api):
        thinking = {"type": "thinking", "thinking": "", "signature": "sig"}
        messages_api.queue(message(blocks_before=[thinking]))

        assert claude_client.generate(PROMPT).title == FIELDS["title"]

    def test_every_token_count_is_reported_and_priced(self, messages_api):
        messages_api.queue(
            message(input_tokens=1234, cache_creation_input_tokens=100, cache_read_input_tokens=200, output_tokens=567)
        )

        generation = claude_client.generate(PROMPT)

        assert (
            generation.input_tokens,
            generation.cache_creation_input_tokens,
            generation.cache_read_input_tokens,
            generation.output_tokens,
        ) == (1234, 100, 200, 567)
        assert (generation.request_id, generation.model, generation.stop_reason) == (
            "req_abc",
            "claude-haiku-4-5",
            "end_turn",
        )
        # 1234 in at $1, 100 written at $1.25, 200 read at $0.10, 567 out at $5, per million.
        assert generation.cost_usd == Decimal("0.004214")

    def test_the_call_is_settled_at_its_real_cost_against_its_post(self, messages_api):
        post = BlogPostFactory()
        messages_api.queue(message())

        generation = claude_client.generate(PROMPT, blog_post=post)

        record = usage()
        assert (record.status, record.cost_usd, record.blog_post, record.pk) == (
            AiUsage.Status.SUCCEEDED,
            Decimal("0.004069"),
            post,
            generation.usage_id,
        )
        assert BudgetPeriod.objects.get().spent_usd == Decimal("0.004069")

    def test_a_post_served_after_a_fallback_is_charged_for_every_attempt(self, messages_api, settings):
        """Top-level usage covers only the attempt that answered; iterations are the billing record."""
        settings.ANTHROPIC = {**settings.ANTHROPIC, "model": "claude-opus-5"}
        attempts = [
            {"type": "message", "input_tokens": 1000, "output_tokens": 50},
            {"type": "fallback_message", "input_tokens": 1234, "output_tokens": 567},
        ]
        messages_api.queue(message(input_tokens=1234, output_tokens=567, iterations=attempts, model="claude-opus-4-8"))

        generation = claude_client.generate(PROMPT)

        # 2234 in at $5 and 617 out at $25 per million.
        assert generation.cost_usd == Decimal("0.026595")


class TestBudget:
    def test_a_call_that_would_cross_the_cap_is_never_sent(self, messages_api):
        BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("9.9999"))
        messages_api.queue(message())

        with pytest.raises(budget.BudgetExceededError):
            claude_client.generate(PROMPT)

        assert messages_api.call_count == 0
        assert not AiUsage.objects.exists()
        event = ErrorEvent.objects.get()
        assert (event.context, event.severity) == (ErrorEvent.Context.AI_BUDGET, ErrorEvent.Severity.WARNING)

    def test_without_an_api_key_nothing_is_reserved_or_sent(self, messages_api, settings):
        settings.ANTHROPIC = {**settings.ANTHROPIC, "api_key": ""}
        messages_api.queue(message())

        # Blocked, not a per-post failure: every post would fail the same way until the key is set.
        with pytest.raises(claude_client.ClaudeBlockedError, match="ANTHROPIC_API_KEY"):
            claude_client.generate(PROMPT)

        assert messages_api.call_count == 0
        assert not AiUsage.objects.exists()

    def test_a_model_with_no_known_price_is_never_sent(self, messages_api, settings):
        settings.ANTHROPIC = {**settings.ANTHROPIC, "model": "claude-future-9"}
        messages_api.queue(message())

        with pytest.raises(UnknownModelPriceError):
            claude_client.generate(PROMPT)

        assert messages_api.call_count == 0
        assert not AiUsage.objects.exists()


class TestRetries:
    def test_a_server_error_is_retried(self, messages_api):
        messages_api.queue(api_error(500, "api_error"), message())

        claude_client.generate(PROMPT)

        assert messages_api.call_count == 2
        assert usage().status == AiUsage.Status.SUCCEEDED

    def test_an_overloaded_api_is_retried(self, messages_api):
        messages_api.queue(api_error(529, "overloaded_error"), message())

        claude_client.generate(PROMPT)

        assert messages_api.call_count == 2

    def test_a_refused_connection_is_retried(self, messages_api):
        messages_api.queue(httpx2.ConnectError("refused"), message())

        claude_client.generate(PROMPT)

        assert messages_api.call_count == 2

    def test_persistent_server_errors_give_up_and_charge_nothing(self, messages_api):
        messages_api.queue(api_error(503, "api_error"))

        with pytest.raises(claude_client.ClaudeError) as failure:
            claude_client.generate(PROMPT)

        assert (messages_api.call_count, failure.value.status) == (3, 503)
        assert (usage().status, usage().cost_usd) == (AiUsage.Status.FAILED, Decimal("0"))

    def test_a_bad_request_is_not_retried_and_charges_nothing(self, messages_api):
        messages_api.queue(api_error(400, "invalid_request_error", "output_config.format: invalid schema"))

        with pytest.raises(claude_client.ClaudeError, match="invalid schema"):
            claude_client.generate(PROMPT)

        assert messages_api.call_count == 1
        assert (usage().status, usage().cost_usd) == (AiUsage.Status.FAILED, Decimal("0"))

    def test_a_rejected_key_is_not_retried(self, messages_api):
        messages_api.queue(api_error(401, "authentication_error"))

        with pytest.raises(claude_client.ClaudeError):
            claude_client.generate(PROMPT)

        assert messages_api.call_count == 1

    def test_a_rate_limit_stops_with_the_wait_the_api_asked_for(self, messages_api):
        messages_api.queue(api_error(429, "rate_limit_error", headers={"retry-after": "7"}))

        with pytest.raises(claude_client.ClaudeBlockedError) as blocked:
            claude_client.generate(PROMPT)

        assert (messages_api.call_count, blocked.value.status, blocked.value.retry_after_seconds) == (1, 429, 7)
        assert usage().cost_usd == Decimal("0")

    def test_running_out_of_credit_stops_rather_than_failing_post_after_post(self, messages_api):
        messages_api.queue(api_error(402, "billing_error", "Your credit balance is too low."))

        with pytest.raises(claude_client.ClaudeBlockedError, match="credit balance"):
            claude_client.generate(PROMPT)

        assert messages_api.call_count == 1


class TestUnknownOutcome:
    def test_a_timed_out_response_is_not_retried_and_keeps_its_worst_case_cost(self, messages_api):
        """The article may have been generated and billed; a retry would pay for it twice."""
        messages_api.queue(httpx2.ReadTimeout("no response"))

        with pytest.raises(claude_client.ClaudeError):
            claude_client.generate(PROMPT)

        record = usage()
        assert messages_api.call_count == 1
        assert record.status == AiUsage.Status.ABANDONED
        assert record.cost_usd == record.reserved_usd > 0

    def test_a_connection_dropped_mid_response_keeps_its_worst_case_cost(self, messages_api):
        messages_api.queue(httpx2.RemoteProtocolError("peer closed connection"))

        with pytest.raises(claude_client.ClaudeError):
            claude_client.generate(PROMPT)

        assert messages_api.call_count == 1
        assert usage().status == AiUsage.Status.ABANDONED

    def test_a_gateway_timeout_keeps_its_worst_case_cost(self, messages_api):
        messages_api.queue(api_error(504, "api_error"))

        with pytest.raises(claude_client.ClaudeError):
            claude_client.generate(PROMPT)

        assert messages_api.call_count == 1
        assert usage().status == AiUsage.Status.ABANDONED


class TestUnusableResponses:
    def test_a_truncated_article_is_rejected_but_its_tokens_are_charged(self, messages_api):
        messages_api.queue(message(text='{"title": "1997 Toyota', stop_reason="max_tokens"))

        with pytest.raises(claude_client.ClaudeError, match="cut off"):
            claude_client.generate(PROMPT)

        assert (usage().status, usage().cost_usd, usage().stop_reason) == (
            AiUsage.Status.FAILED,
            Decimal("0.004069"),
            "max_tokens",
        )

    def test_a_declined_request_is_rejected_but_charged_for_what_it_used(self, messages_api):
        messages_api.queue(message(text=None, stop_reason="refusal"))

        with pytest.raises(claude_client.ClaudeError, match="declined"):
            claude_client.generate(PROMPT)

        assert (usage().status, usage().cost_usd) == (AiUsage.Status.FAILED, Decimal("0.004069"))

    def test_a_response_missing_a_field_is_rejected_but_charged(self, messages_api):
        incomplete = {key: value for key, value in FIELDS.items() if key != "seo_description"}
        messages_api.queue(message(incomplete))

        with pytest.raises(claude_client.ClaudeError, match="schema"):
            claude_client.generate(PROMPT)

        assert usage().cost_usd == Decimal("0.004069")

    def test_keywords_that_are_not_a_list_are_rejected(self, messages_api):
        messages_api.queue(message({**FIELDS, "seo_keywords": "used toyota rav4, 1997 rav4"}))

        with pytest.raises(claude_client.ClaudeError, match="schema"):
            claude_client.generate(PROMPT)

    def test_an_answer_with_no_text_is_rejected(self, messages_api):
        messages_api.queue(message(text=None))

        with pytest.raises(claude_client.ClaudeError, match="schema"):
            claude_client.generate(PROMPT)


class TestErrorLog:
    def test_a_failure_is_logged_against_its_post_with_the_api_detail(self, messages_api):
        post = BlogPostFactory()
        messages_api.queue(api_error(400, "invalid_request_error", "Invalid schema."))

        with pytest.raises(claude_client.ClaudeError):
            claude_client.generate(PROMPT, blog_post=post)

        event = ErrorEvent.objects.get()
        assert (event.context, event.blog_post, event.car_search_id) == (
            ErrorEvent.Context.AI_GENERATION,
            post,
            post.car_search_id,
        )
        assert (event.details["http_status"], event.details["request_id"], event.details["error_type"]) == (
            400,
            "req_bad",
            "invalid_request_error",
        )
        assert "Invalid schema." in event.details["response_excerpt"]

    def test_the_api_key_never_reaches_the_error_log(self, messages_api):
        messages_api.queue(api_error(401, "authentication_error", "invalid x-api-key: sk-ant-test"))

        with pytest.raises(claude_client.ClaudeError) as failure:
            claude_client.generate(PROMPT)

        event = ErrorEvent.objects.get()
        logged = json.dumps([event.message, event.exception_message, event.details, event.trace_excerpt])
        assert "sk-ant-test" not in logged
        assert "sk-ant-test" not in str(failure.value)

    def test_django_error_reports_never_show_the_key_in_client_frames(self, messages_api):
        """Django's error page and error trackers record each frame's local variables."""
        messages_api.queue(RuntimeError("unexpected"))

        with pytest.raises(claude_client.ClaudeError) as raised:
            claude_client.generate(PROMPT)

        frames = ExceptionReporter(None, raised.type, raised.value, raised.tb).get_traceback_frames()
        client_frames = [frame for frame in frames if frame["filename"].endswith("claude_client.py")]
        assert client_frames, "the client's frames are missing from the report"
        assert "sk-ant-test" not in repr([frame["vars"] for frame in client_frames])
