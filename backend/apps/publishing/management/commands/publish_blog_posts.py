from django.core.management.base import BaseCommand, CommandParser

from apps.publishing.services import seeding
from apps.publishing.services.run_chunk import run_chunk


class Command(BaseCommand):
    help = (
        "Write and publish blog posts as WordPress drafts, in time-boxed chunks. "
        "Spends AI budget: one chunk by default, so a single run stays small."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--seed", action="store_true", help="First queue a post for each vehicle that has approved images."
        )
        parser.add_argument("--import", dest="csv_import_id", type=int, help="Only posts from this CSV import.")
        parser.add_argument("--post", dest="post_ids", type=int, action="append", help="Only this post (repeatable).")
        parser.add_argument("--chunks", type=int, default=1, help="Stop after this many chunks (default 1).")

    def handle(self, *args, **options) -> None:
        csv_import_id, post_ids = options["csv_import_id"], options["post_ids"]
        if options["seed"]:
            seeded = seeding.sync_posts(csv_import=csv_import_id)
            self.stdout.write(f"Queued {seeded.created} new post(s); {seeded.existing} already queued.")

        result = None
        for _ in range(max(1, options["chunks"])):
            result = run_chunk(csv_import_id=csv_import_id, post_ids=post_ids)
            for outcome in result.outcomes:
                name = " ".join(str(part) for part in (outcome.year, outcome.make, outcome.model) if part)
                self.stdout.write(f"  {outcome.outcome:9} {name}  wp #{outcome.wp_post_id}  ${outcome.cost_usd}")
            if result.blocked:
                self.stdout.write(self.style.WARNING(f"Stopped ({result.blocked.reason}): {result.blocked.message}"))
                break
            if result.remaining == 0:
                break

        self.stdout.write(f"{result.remaining} post(s) still waiting. AI spend this month: ${result.spent_usd}")
