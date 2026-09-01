# -*- coding: utf-8 -*-
# Module: feed_manager.py
"""
FeedManager module for openSquat.
Handles checking and downloading of domain feeds.
"""
import os
import requests
import hashlib
from urllib.parse import urlparse
from colorama import Fore, Style
from opensquat import __VERSION__


PREMIUM_FEED_URL = "https://api.opensquat.com/v1/feeds/nrd-lite"


class FeedManager:
    def __init__(
        self,
        feed_url="https://feeds.opensquat.com/opensquat-nrd-latest.txt",
        api_key=None,
        premium=False,
    ):
        self.feed_url = feed_url
        self.local_filename = self._safe_filename(feed_url)
        self.user_agent = "openSquat-" + __VERSION__
        self.api_key = api_key
        self.premium = premium

    def _build_headers(self):
        headers = {'User-Agent': self.user_agent}
        if self.premium and self.api_key:
            headers['X-API-Key'] = self.api_key
        return headers

    @staticmethod
    def _safe_filename(feed_url):
        """
        Extract and validate local filename from feed URL.
        Prevents path traversal attacks from crafted URLs.
        """
        parsed = urlparse(feed_url)
        filename = os.path.basename(parsed.path)

        if not filename:
            print(
                Style.BRIGHT + Fore.RED +
                "[SECURITY] Aborted: Feed URL has no valid filename." +
                Style.RESET_ALL
            )
            exit(-1)

        if filename.startswith('.'):
            print(
                Style.BRIGHT + Fore.RED +
                f"[SECURITY] Aborted: Suspicious filename '{filename}' (hidden file)." +
                Style.RESET_ALL
            )
            exit(-1)

        if '/' in filename or '\\' in filename or '..' in filename:
            print(
                Style.BRIGHT + Fore.RED +
                f"[SECURITY] Aborted: Path traversal detected in filename '{filename}'." +
                Style.RESET_ALL
            )
            exit(-1)

        return filename

    def check_latest_feeds(self):
        """
        Checks if the local feed file is up to date by comparing MD5 checksums.
        Premium feeds skip the freshness check entirely (no .md5 sibling exists
        on the API endpoint, and every download already costs plan quota).
        """
        if self.premium:
            return False

        url_md5 = self.feed_url + ".md5"
        print("[*] Checking for the latest feeds...")

        headers = self._build_headers()

        try:
            response = requests.get(url_md5, headers=headers, timeout=30)
        except requests.exceptions.RequestException:
            return False

        if response.status_code != 200:
            return False

        latest_checksum = response.content.decode('utf-8').strip()
        response.close()

        if os.path.exists(self.local_filename):
            try:
                with open(self.local_filename, "rb") as f:
                    local_checksum = hashlib.md5(f.read()).hexdigest()

                if latest_checksum == local_checksum:
                    print("[*] You have the latest feeds\n")
                    return True
                else:
                    return False
            except (OSError, IOError) as e:
                # Surface the failure so users don't silently re-download the
                # feed on every run because of a disk/permission problem.
                print(
                    Style.BRIGHT + Fore.YELLOW +
                    f"[!] Could not read local feed '{self.local_filename}' "
                    f"for checksum comparison: {e}. Will re-download." +
                    Style.RESET_ALL
                )
                return False
        return False

    def download(self):
        """
        Downloads the latest registered domains.
        """
        print("[*] Downloading fresh domain list:", self.feed_url)

        headers = self._build_headers()
        try:
            # Timeout on both paths: a hung TCP connection should not hang
            # the whole CLI. Premium gets a longer budget because the feed
            # is meaningfully larger than community.
            timeout = 120 if self.premium else 60
            response = requests.get(self.feed_url, headers=headers, timeout=timeout)

            if response.status_code != 200:
                if self.premium and response.status_code in (401, 403):
                    print(
                        Style.BRIGHT + Fore.RED +
                        f"[ERROR] Premium feed download failed (HTTP {response.status_code}). "
                        "Check your API key and plan." +
                        Style.RESET_ALL
                    )
                else:
                    print(
                        Style.BRIGHT + Fore.RED +
                        f"[ERROR] Failed to download feeds (Status: {response.status_code})" +
                        Style.RESET_ALL
                    )
                exit(-1)

            # Get content size (handling chunked encoding where header might be missing)
            total_size = int(response.headers.get("content-length", 0))
            data = response.content

            if total_size == 0:
                total_size = len(data)

            total_size_mb = round(float(total_size / 1024 / 1024), 2)

            if total_size == 0:
                print(
                    Style.BRIGHT + Fore.RED + "[ERROR] Feed file not found or empty, " +
                    "Please notify the authors or try again later." + Style.RESET_ALL
                )
                exit(-1)

            print("[*] Download volume:", total_size_mb, "MB")

            with open(self.local_filename, "wb") as f:
                f.write(data)

            return True

        except Exception as e:
            print(Style.BRIGHT + Fore.RED + f"[ERROR] Exception during download: {e}" + Style.RESET_ALL)
            exit(-1)

    def ensure_feeds(self):
        """
        Ensures that the feed file exists and is up to date.
        """
        if not self.check_latest_feeds():
            self.download()
