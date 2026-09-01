# -*- coding: utf-8 -*-
"""Tests for opensquat.auth."""
import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from opensquat.auth import (
    AuthError,
    load_api_key,
    mask_key,
)


class TestLoadAPIKey(TestCase):

    def setUp(self):
        # Ensure tests don't accidentally pick up a real env var
        self._saved_env = os.environ.pop("OPENSQUAT_API_KEY", None)

    def tearDown(self):
        if self._saved_env is not None:
            os.environ["OPENSQUAT_API_KEY"] = self._saved_env

    def test_cli_value_takes_precedence(self):
        with patch.dict(os.environ, {"OPENSQUAT_API_KEY": "from_env"}):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                f.write("from_file\n")
                key_file = f.name
            try:
                result = load_api_key(
                    cli_value="from_cli", key_file=key_file
                )
                self.assertEqual("from_cli", result)
            finally:
                os.unlink(key_file)

    def test_env_var_used_when_no_cli(self):
        with patch.dict(os.environ, {"OPENSQUAT_API_KEY": "from_env"}):
            result = load_api_key(
                cli_value=None, key_file="/nonexistent/path.txt"
            )
            self.assertEqual("from_env", result)

    def test_empty_cli_value_falls_through_to_env(self):
        with patch.dict(os.environ, {"OPENSQUAT_API_KEY": "from_env"}):
            result = load_api_key(
                cli_value="", key_file="/nonexistent/path.txt"
            )
            self.assertEqual("from_env", result)

    def test_whitespace_cli_value_falls_through_to_env(self):
        with patch.dict(os.environ, {"OPENSQUAT_API_KEY": "from_env"}):
            result = load_api_key(
                cli_value="   ", key_file="/nonexistent/path.txt"
            )
            self.assertEqual("from_env", result)

    def test_file_used_as_fallback(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("from_file_key\n")
            key_file = f.name
        try:
            result = load_api_key(cli_value=None, key_file=key_file)
            self.assertEqual("from_file_key", result)
        finally:
            os.unlink(key_file)

    def test_file_strips_whitespace_and_skips_comments(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("# This is a comment\n")
            f.write("\n")
            f.write("   actual_key   \n")
            f.write("ignored_second_line\n")
            key_file = f.name
        try:
            result = load_api_key(cli_value=None, key_file=key_file)
            self.assertEqual("actual_key", result)
        finally:
            os.unlink(key_file)

    def test_missing_all_sources_raises(self):
        with self.assertRaises(AuthError) as ctx:
            load_api_key(cli_value=None, key_file="/nonexistent/path.txt")
        message = str(ctx.exception)
        # The error message must name all three sources tried
        self.assertIn("--api-key", message)
        self.assertIn("OPENSQUAT_API_KEY", message)
        self.assertIn("/nonexistent/path.txt", message)

    def test_empty_file_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            key_file = f.name
        try:
            with self.assertRaises(AuthError):
                load_api_key(cli_value=None, key_file=key_file)
        finally:
            os.unlink(key_file)

    def test_file_with_only_comments_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("# only comments\n")
            f.write("# nothing usable\n")
            key_file = f.name
        try:
            with self.assertRaises(AuthError):
                load_api_key(cli_value=None, key_file=key_file)
        finally:
            os.unlink(key_file)


class TestMaskKey(TestCase):

    def test_masks_long_key(self):
        # 29-char openSquat key format: os_<22 random><4 CRC32>
        key = "os_abcdefghijklmnopqrstuvwxyz12"
        masked = mask_key(key)
        self.assertEqual("os_ab...yz12", masked)
        self.assertNotIn("cdefghij", masked)

    def test_short_key_fully_masked(self):
        self.assertEqual("***", mask_key("short"))

    def test_empty_key_fully_masked(self):
        self.assertEqual("***", mask_key(""))

    def test_none_key_fully_masked(self):
        self.assertEqual("***", mask_key(None))
