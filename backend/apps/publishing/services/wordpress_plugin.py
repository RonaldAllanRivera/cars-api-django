"""
Packages the Cars Images Publisher WordPress plugin kept in this repo.

The zip is built from the source on request, so a download is always the
version in this deploy. WordPress installs a zip into a folder named after its
top-level directory, so every entry sits under the plugin slug. Timestamps and
order are fixed, so the same source always produces the same bytes.
"""

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

SLUG = "cars-images-publisher"
# Kept out of the download: they run in CI, not on a WordPress site.
EXCLUDED_DIRECTORIES = frozenset({"tests", "__pycache__"})
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
VERSION_HEADER = re.compile(r"^\s*\*\s*Version:\s*(\S+)", re.MULTILINE)


@dataclass(frozen=True)
class PluginPackage:
    filename: str
    version: str
    data: bytes


def plugin_dir() -> Path:
    return Path(settings.BASE_DIR) / "wordpress-plugin" / SLUG


def plugin_version() -> str:
    match = VERSION_HEADER.search((plugin_dir() / f"{SLUG}.php").read_text())
    if not match:
        raise ValueError(f"{SLUG}.php has no Version header")
    return match.group(1)


def build_package() -> PluginPackage:
    root = plugin_dir()
    files = sorted(path for path in root.rglob("*") if path.is_file() and _shipped(path.relative_to(root)))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in files:
            entry = zipfile.ZipInfo(f"{SLUG}/{path.relative_to(root).as_posix()}", date_time=ZIP_EPOCH)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, path.read_bytes())
    version = plugin_version()
    return PluginPackage(filename=f"{SLUG}-{version}.zip", version=version, data=buffer.getvalue())


def _shipped(relative: Path) -> bool:
    return not any(part in EXCLUDED_DIRECTORIES or part.startswith(".") for part in relative.parts)
