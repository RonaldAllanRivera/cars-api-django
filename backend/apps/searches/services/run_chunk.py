"""Port of RunChunkAction: run the next time-boxed chunk of a CSV import."""

import time
from dataclasses import asdict, dataclass, field

from django.conf import settings
from django.db.models import QuerySet

from apps.searches.models import CarSearch
from apps.searches.services.run_query import run_search_query
from apps.searches.services.wikimedia import WikimediaBlockedError


@dataclass
class ChunkOutcome:
    id: int
    make: str
    model: str | None
    from_year: int
    outcome: str  # "completed" | "failed"


@dataclass
class ChunkBlocked:
    status: int
    retry_after_seconds: int | None


@dataclass
class ChunkResult:
    outcomes: list[ChunkOutcome] = field(default_factory=list)
    ran_seconds: float = 0.0
    remaining: int = 0
    blocked: ChunkBlocked | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def run_chunk(csv_import_id: int) -> ChunkResult:
    """Run the import's next pending/failed searches, bounded by a query count and a wall clock.

    The rows are the run state, so a client that crashed mid-run resumes simply by calling again.
    A Wikimedia block stops the chunk; any other failure is recorded and the chunk moves on.
    """
    config = settings.CARS_IMAGES
    max_queries = int(config["bulk_run_max_queries_per_chunk"])
    max_seconds = config["bulk_run_auto_chunk_seconds"]
    pause_seconds = config["bulk_run_sleep_seconds_between_queries"]

    queue = list(_runnable(csv_import_id)[:max_queries])
    started_at = time.monotonic()
    result = ChunkResult()

    for index, search in enumerate(queue):
        # The first search always runs, so a slow Commons cannot starve the chunk entirely.
        if index > 0 and time.monotonic() - started_at >= max_seconds:
            break

        try:
            run_search_query(search)
            result.outcomes.append(_describe(search, "completed"))
        except WikimediaBlockedError as error:
            # Not a per-query failure: the block and error events are already written, so just stop asking.
            result.blocked = ChunkBlocked(status=error.status, retry_after_seconds=error.retry_after_seconds)
            break
        except Exception:
            # Already marked failed and logged; it stays runnable for the next chunk.
            result.outcomes.append(_describe(search, "failed"))

        if pause_seconds > 0 and index < len(queue) - 1:
            time.sleep(pause_seconds)

    result.ran_seconds = round(time.monotonic() - started_at, 2)
    # Recounted rather than inferred, so the client's figure survives a dropped response.
    result.remaining = _runnable(csv_import_id).count()
    return result


def _runnable(csv_import_id: int) -> QuerySet[CarSearch]:
    """In id (CSV) order, so a resumed run continues where the import left off."""
    return CarSearch.objects.filter(
        csv_import_id=csv_import_id, status__in=[CarSearch.Status.PENDING, CarSearch.Status.FAILED]
    ).order_by("id")


def _describe(search: CarSearch, outcome: str) -> ChunkOutcome:
    return ChunkOutcome(id=search.pk, make=search.make, model=search.model, from_year=search.from_year, outcome=outcome)
