import json

import pytest


@pytest.fixture(autouse=True)
def _publishing_settings(settings):
    """
    A pinned model, cap and hosts, so money assertions never depend on the
    environment and no test can reach a real API even if a fake is missed.
    """
    settings.ANTHROPIC = {
        **settings.ANTHROPIC,
        "api_key": "sk-ant-test",
        "base_url": "https://api.anthropic.test",
        "model": "claude-haiku-4-5",
        "max_tokens": 8000,
        "effort": "",
        "retry_times": 2,
        "retry_sleep_ms": 0,
        "input_usd_per_1m": "",
        "output_usd_per_1m": "",
        "cache_write_usd_per_1m": "",
        "cache_read_usd_per_1m": "",
    }
    settings.AI_BUDGET = {**settings.AI_BUDGET, "monthly_usd": 10.0, "reservation_stale_minutes": 15}
    settings.WORDPRESS = {
        **settings.WORDPRESS,
        "base_url": "https://wp.test",
        "username": "publisher",
        "app_password": "abcdabcdabcdabcdabcdabcd",
        "retry_sleep_ms": 0,
    }
    settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "sleep_seconds_between_posts": 0}


class FakeMessagesApi:
    """
    Stands in for the Claude Messages API at the HTTP transport, so the real SDK
    builds and parses every request. Queued outcomes are served in order; the
    last one repeats, which is how a persistent failure is expressed.
    """

    def __init__(self):
        self.outcomes: list = []
        self.requests: list = []

    def queue(self, *outcomes):
        self.outcomes.extend(outcomes)

    def handle(self, request):
        self.requests.append(request)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def body(self, index: int = -1) -> dict:
        return json.loads(self.requests[index].content)


@pytest.fixture
def messages_api(monkeypatch):
    import anthropic
    import httpx2

    from apps.publishing.services import claude_client

    api = FakeMessagesApi()
    monkeypatch.setattr(
        claude_client,
        "_http_client",
        lambda: anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(api.handle)),
    )
    return api


@pytest.fixture
def wp_site():
    """A respx router intercepting every httpx call; nothing reaches a real WordPress site."""
    import respx

    with respx.mock(base_url="https://wp.test/wp-json/wp/v2", assert_all_called=False) as router:
        yield router
