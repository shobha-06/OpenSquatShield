# -*- coding: utf-8 -*-
"""Tests for opensquat.feed_manager."""
import os
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch

from opensquat.feed_manager import FeedManager, PREMIUM_FEED_URL


def _ok_response(content=b"example.com\n", status=200):
    response = MagicMock()
    response.status_code = status
    response.content = content
    response.headers = {"content-length": str(len(content))}
    return response


class TestFeedManagerHeaders(TestCase):

    def test_community_headers_have_no_api_key(self):
        fm = FeedManager()
        headers = fm._build_headers()
        self.assertIn("User-Agent", headers)
        self.assertNotIn("X-API-Key", headers)
        self.assertTrue(headers["User-Agent"].startswith("openSquat-"))

    def test_premium_headers_include_api_key(self):
        fm = FeedManager(
            feed_url=PREMIUM_FEED_URL, api_key="os_test_key", premium=True
        )
        headers = fm._build_headers()
        self.assertEqual("os_test_key", headers["X-API-Key"])
        self.assertTrue(headers["User-Agent"].startswith("openSquat-"))

    def test_premium_without_key_omits_header(self):
        fm = FeedManager(feed_url=PREMIUM_FEED_URL, api_key=None, premium=True)
        headers = fm._build_headers()
        self.assertNotIn("X-API-Key", headers)


class TestPremiumSkipsMD5(TestCase):

    @patch("opensquat.feed_manager.requests.get")
    def test_premium_check_latest_feeds_returns_false_without_network(
        self, mock_get
    ):
        fm = FeedManager(
            feed_url=PREMIUM_FEED_URL, api_key="os_test_key", premium=True
        )
        result = fm.check_latest_feeds()
        self.assertFalse(result)
        mock_get.assert_not_called()


class TestPremiumDownloadHeaders(TestCase):

    @patch("opensquat.feed_manager.requests.get")
    def test_premium_download_sends_x_api_key(self, mock_get):
        mock_get.return_value = _ok_response(b"example.com\n")
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                fm = FeedManager(
                    feed_url=PREMIUM_FEED_URL,
                    api_key="os_test_key",
                    premium=True,
                )
                fm.download()
            finally:
                os.chdir(old_cwd)

        called_kwargs = mock_get.call_args[1]
        self.assertEqual("os_test_key", called_kwargs["headers"]["X-API-Key"])
        # Premium path uses a longer timeout because the feed is larger
        self.assertEqual(120, called_kwargs["timeout"])

    @patch("opensquat.feed_manager.requests.get")
    def test_community_download_does_not_send_x_api_key(self, mock_get):
        mock_get.return_value = _ok_response(b"example.com\n")
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                fm = FeedManager()  # community defaults
                fm.download()
            finally:
                os.chdir(old_cwd)

        called_kwargs = mock_get.call_args[1]
        self.assertNotIn("X-API-Key", called_kwargs["headers"])
        # Both paths now set a timeout so a hung connection cannot hang
        # the whole CLI indefinitely.
        self.assertEqual(60, called_kwargs["timeout"])


class TestSafeFilenameForPremium(TestCase):

    def test_premium_url_filename_accepted(self):
        fm = FeedManager(
            feed_url=PREMIUM_FEED_URL, api_key="k", premium=True
        )
        # The basename of /v1/feeds/nrd-lite is 'nrd-lite' — no extension,
        # but should be accepted by _safe_filename (no dot prefix, no slashes).
        self.assertEqual("nrd-lite", fm.local_filename)
