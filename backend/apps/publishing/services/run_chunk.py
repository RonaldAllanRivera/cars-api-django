"""
Publishes the next time-boxed chunk of blog posts.

The rows are the run state, so a request that died mid-chunk resumes simply by
calling again; clients loop until nothing remains or the chunk reports a block.
A block stops the chunk at once, because every remaining post would fail the
same way: the AI budget is spent, the daily limit is reached, the model has no
known price, or Claude or WordPress refused the credentials or the rate.
"""

import time
from dataclasses import asdict, dataclass, field
from datetime import timedelta

from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.publishing.models import BlogPost
from apps.publishing.services import budget, media, publish, wordpress
from apps.publishing.services.claude_client import ClaudeBlockedError
from apps.publishing.services.pricing import UnknownModelPriceError
from apps.publishing.services.publish import PostOutcome

RUNNABLE = (BlogPost.Status.PENDING, BlogPost.Status.GENERATED, BlogPost.Status.FAILED, BlogPost.Status.BLOCKED)
IN_FLIGHT = (BlogPost.Status.GENERATING, BlogPost.Status.PUBLISHING)


@dataclass
class ChunkBlocked:
    reason: str  # "budget" | "daily_cap" | "pricing" | "claude" | "wordpress"
    status: int | None
    retry_after_seconds: int | None
    message: str


@dataclass
class PublishChunkResult:
    outcomes: list[PostOutcome] = field(default_factory=list)
    ran_seconds: float = 0.0
    remaining: int = 0
    spent_usd: str = "0"
    blocked: ChunkBlocked | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def run_chunk(*, csv_import_id: int | None = None, post_ids: list[int] | None = None) -> PublishChunkResult:
    limits = settings.CARS_PUBLISHING
    budget.reconcile_stale_reservations()
    _reclaim_stale(limits["stale_run_minutes"])

    queue = list(_runnable(csv_import_id, post_ids)[: limits["max_posts_per_chunk"]])
    started_at = time.monotonic()
    result = PublishChunkResult()
    if queue:
        try:
            with wordpress.client() as wp, media.fetch_client() as fetcher:
                _work_through(queue, result, started_at, wp=wp, fetcher=fetcher)
        except wordpress.WordPressError as error:
            # Only a failure to open the connection reaches here, such as a missing setting.
            result.blocked = ChunkBlocked("wordpress", error.status, error.retry_after_seconds, str(error))

    result.ran_seconds = round(time.monotonic() - started_at, 2)
    # Recounted rather than inferred, so the client's figure survives a dropped response.
    result.remaining = _runnable(csv_import_id, post_ids).count()
    result.spent_usd = str(budget.month_to_date()["spent_usd"])
    return result


def _work_through(queue: list[BlogPost], result: PublishChunkResult, started_at: float, *, wp, fetcher) -> None:
    limits = settings.CARS_PUBLISHING
    allowance = _daily_allowance(limits["max_posts_per_day"])

    for index, post in enumerate(queue):
        # The first post always runs, so a slow WordPress or model cannot starve the chunk entirely.
        if index > 0 and time.monotonic() - started_at >= limits["chunk_seconds"]:
            break

        if not (post.generated_at and post.content) and allowance is not None:
            if allowance <= 0:
                # New writing waits for tomorrow; text already paid for still publishes.
                result.blocked = ChunkBlocked(
                    "daily_cap", None, None, f"The daily limit of {limits['max_posts_per_day']} new posts is reached."
                )
                continue
            allowance -= 1

        try:
            result.outcomes.append(publish.generate_and_publish(post, wp=wp, fetcher=fetcher))
        except budget.BudgetExceededError as error:
            result.blocked = ChunkBlocked("budget", None, None, str(error))
            break
        except UnknownModelPriceError as error:
            result.blocked = ChunkBlocked("pricing", None, None, str(error))
            break
        except ClaudeBlockedError as error:
            result.blocked = ChunkBlocked("claude", error.status, error.retry_after_seconds, str(error))
            break
        except wordpress.WordPressBlockedError as error:
            result.blocked = ChunkBlocked("wordpress", error.status, error.retry_after_seconds, str(error))
            break
        except Exception:
            # Already recorded on the post and in the error log; it stays runnable.
            result.outcomes.append(publish.describe(post, "failed"))

        pause = limits["sleep_seconds_between_posts"]
        if pause > 0 and index < len(queue) - 1:
            time.sleep(pause)


def _runnable(csv_import_id: int | None, post_ids: list[int] | None) -> QuerySet[BlogPost]:
    """In id order, so a resumed run continues where it left off."""
    has_text = Q(generated_at__isnull=False) & ~Q(content="")
    # A post whose writing keeps failing stops being paid for; one with its text can always retry publishing.
    affordable = Q(attempts__lt=settings.CARS_PUBLISHING["max_generation_attempts"])
    queryset = BlogPost.objects.filter(Q(status__in=RUNNABLE) & (has_text | affordable))
    if csv_import_id is not None:
        queryset = queryset.filter(csv_import_id=csv_import_id)
    if post_ids:
        queryset = queryset.filter(pk__in=post_ids)
    return queryset.order_by("id")


def _reclaim_stale(minutes: int) -> int:
    """A post left generating or publishing by a killed worker becomes retryable instead of stuck."""
    now = timezone.now()
    return BlogPost.objects.filter(status__in=IN_FLIGHT, updated_at__lt=now - timedelta(minutes=minutes)).update(
        status=BlogPost.Status.FAILED,
        last_error="Interrupted mid-run by a stopped worker; it will be retried.",
        updated_at=now,
    )


def _daily_allowance(limit: int) -> int | None:
    """New posts that may still be written today (UTC); None when there is no daily limit."""
    if limit <= 0:
        return None
    start_of_day = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return limit - BlogPost.objects.filter(generated_at__gte=start_of_day).count()
