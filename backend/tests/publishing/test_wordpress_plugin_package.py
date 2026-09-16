"""The WordPress plugin kept in this repo, and the zip admins download."""

import io
import os
import re
import shutil
import subprocess
import zipfile

import pytest

from apps.publishing.services import wordpress_plugin

PHP = shutil.which("php")


def needs_php():
    """Locally a missing PHP skips; in CI it fails, so the plugin's tests can never be silently skipped."""
    if PHP:
        return
    if os.environ.get("CI"):
        pytest.fail("PHP is required in CI to test the WordPress plugin")
    pytest.skip("php is not installed")


class TestPackage:
    def test_the_version_comes_from_the_plugin_header(self):
        assert wordpress_plugin.plugin_version() == "1.0.0"

    def test_the_header_version_and_the_version_constant_agree(self):
        main = (wordpress_plugin.plugin_dir() / "cars-images-publisher.php").read_text()

        assert f"define('CIP_VERSION', '{wordpress_plugin.plugin_version()}');" in main

    def test_every_file_sits_in_the_plugin_folder_wordpress_expects(self):
        names = zipfile.ZipFile(io.BytesIO(wordpress_plugin.build_package().data)).namelist()

        assert names
        assert all(name.startswith("cars-images-publisher/") for name in names)
        assert {
            "cars-images-publisher/cars-images-publisher.php",
            "cars-images-publisher/includes/meta.php",
            "cars-images-publisher/includes/seo-mirror.php",
            "cars-images-publisher/includes/head.php",
            "cars-images-publisher/readme.txt",
        } <= set(names)

    def test_tests_are_not_shipped(self):
        names = zipfile.ZipFile(io.BytesIO(wordpress_plugin.build_package().data)).namelist()

        assert not [name for name in names if "/tests/" in name]

    def test_the_same_source_always_builds_the_same_bytes(self):
        """Fixed timestamps and order, so a download can be compared or checksummed."""
        assert wordpress_plugin.build_package().data == wordpress_plugin.build_package().data

    def test_the_filename_carries_the_version(self):
        assert wordpress_plugin.build_package().filename == "cars-images-publisher-1.0.0.zip"


class TestPhp:
    def test_the_plugins_own_tests_pass(self):
        needs_php()
        run = subprocess.run(
            [PHP, "tests/run-tests.php"], cwd=wordpress_plugin.plugin_dir(), capture_output=True, text=True, timeout=60
        )

        assert run.returncode == 0, run.stdout + run.stderr

    def test_every_shipped_php_file_is_valid_syntax(self):
        needs_php()
        for path in wordpress_plugin.plugin_dir().rglob("*.php"):
            run = subprocess.run([PHP, "-l", str(path)], capture_output=True, text=True, timeout=60)
            assert run.returncode == 0, run.stdout + run.stderr

    def test_it_declares_the_minimum_php_it_is_written_for(self):
        header = (wordpress_plugin.plugin_dir() / "cars-images-publisher.php").read_text()

        assert re.search(r"Requires PHP:\s+7\.4", header)
