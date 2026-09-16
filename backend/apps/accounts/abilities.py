"""Token abilities. Order matters: issued abilities follow this order."""

SEARCH_READ = "search:read"
SEARCH_WRITE = "search:write"
REVIEW_WRITE = "review:write"
ERRORS_READ = "errors:read"
IMPORTS_READ = "imports:read"
IMPORTS_WRITE = "imports:write"
SEARCH_RUN = "search:run"
EXPORTS_READ = "exports:read"
# Blog publishing. BLOG_PUBLISH spends AI budget, so none are issued by default.
BLOG_READ = "blog:read"
BLOG_WRITE = "blog:write"
BLOG_PUBLISH = "blog:publish"

ALL = [
    SEARCH_READ,
    SEARCH_WRITE,
    REVIEW_WRITE,
    ERRORS_READ,
    IMPORTS_READ,
    IMPORTS_WRITE,
    SEARCH_RUN,
    EXPORTS_READ,
    BLOG_READ,
    BLOG_WRITE,
    BLOG_PUBLISH,
]

# Granted at login only to staff accounts: they spend AI budget and hand out the WordPress plugin.
STAFF_ONLY = frozenset({BLOG_READ, BLOG_WRITE, BLOG_PUBLISH})

# Issued when a client does not request specific abilities.
DEFAULT = [SEARCH_READ, SEARCH_WRITE, REVIEW_WRITE, ERRORS_READ]


def resolve(requested: list[str] | None, *, staff: bool = False) -> list[str]:
    """Intersect requested abilities with the known set, in canonical order; STAFF_ONLY ones need a staff account."""
    if not requested:
        return list(DEFAULT)
    wanted = set(requested)
    return [ability for ability in ALL if ability in wanted and (staff or ability not in STAFF_ONLY)]
