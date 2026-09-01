# -*- coding: utf-8 -*-
# Module: app.py
"""
openSquat

(c) Andre Tenreiro

* https://github.com/atenreiro/opensquat

software licensed under GNU version 3
"""
import concurrent.futures
import functools
import io
import threading
import time
from dataclasses import dataclass
from typing import Optional

from colorama import Fore, Style

from opensquat import file_input
from opensquat.feed_manager import FeedManager, PREMIUM_FEED_URL
from opensquat.dns_validator import DNSValidator
from opensquat.squatting_detector import SquattingDetector
from opensquat.api_client import (
    APIClient,
    APIAuthError,
    APIBadRequest,
    APIError,
    APIPlanError,
    APIQuotaExhausted,
    APIRateLimited,
)


# Maps -c/--confidence (0-4) to the API fuzziness mode.
# Per OPENSQUAT_CORE.md: 0->exact, 1->low, 2->auto, 3->high, 4->high.
_CONFIDENCE_TO_FUZZINESS = {
    0: "exact",
    1: "low",
    2: "auto",
    3: "high",
    4: "high",
}


class _RateLimiter:
    """
    Thread-safe fixed-interval rate limiter shared across worker threads.

    When rate_per_sec is None or <= 0, wait() is a no-op (zero overhead).
    Otherwise, wait() blocks each caller until its assigned time slot,
    guaranteeing at most rate_per_sec requests per second across all
    callers. Slots are serialized under a single lock so concurrent
    workers cannot burst past the limit.
    """

    def __init__(self, rate_per_sec):
        if rate_per_sec and rate_per_sec > 0:
            self._min_interval = 1.0 / rate_per_sec
        else:
            self._min_interval = 0.0
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self):
        if self._min_interval <= 0:
            return
        # Hold the lock while sleeping so slots are strictly serialized —
        # releasing early would let multiple workers read the same next_slot
        # value and pile up on identical timestamps, bursting past the limit.
        with self._lock:
            now = time.monotonic()
            if now < self._next_slot:
                time.sleep(self._next_slot - now)
                now = self._next_slot
            self._next_slot = now + self._min_interval


@dataclass
class ApiOptions:
    """Per-keyword API call options."""
    api_key: str
    fuzziness: Optional[str] = None
    history_days: Optional[int] = None
    max_results: Optional[int] = None
    rate_limit: Optional[int] = None  # max requests/sec, None = unlimited


class Domain:
    """
    Main orchestration class for OpenSquat.
    """

    def __init__(self):
        """Initiator."""
        self.domain_filename = None
        self.keywords_filename = None
        self.domain_total = 0
        self.keywords_total = 0
        self.list_domains = []
        self.keyword_domains = {}
        # Parallel to keyword_domains, but carries the full per-domain
        # metadata (LookalikeDomain objects) instead of bare strings.
        # Populated only in Premium API mode where the server returns
        # tld/date/idn/unicode. JSON and CSV output readers check this
        # and fall back to keyword_domains when it's empty.
        self.keyword_domains_meta = {}
        self.confidence_level = 2
        self.doppelganger_only = False

        self.feed_manager = None
        self.dns_validator = None
        self.squatting_detector = None

        self.list_file_domains = []
        self.list_file_keywords = []

        # Mode + API mode tracking
        self.mode = "community"
        self.api_balance = None           # min seen across calls
        self.api_balance_initial = None   # max seen across calls
        self.api_calls_made = 0
        self.api_fuzziness = None         # the mode actually used in API calls
        self.rate_limited = False         # True if the run hit an upstream 429

    def count_files(self):
        (self.keywords_total, self.domain_total) = file_input.InputFile().main(
            self.keywords_filename,
            self.domain_filename
        )

    def _read_domains(self):
        """Load the domain feed file into self.list_file_domains."""
        with open(self.domain_filename, mode='r', encoding='utf-8') as file_domains:
            for mydomains in file_domains:
                domain = mydomains.replace("\n", "")
                domain = domain.lower().strip()
                # Skip comments and empty lines
                if domain and not domain.startswith("#"):
                    self.list_file_domains.append(domain)

    def _read_keywords(self):
        """Load the keywords file into self.list_file_keywords."""
        with open(self.keywords_filename, mode='r', encoding='utf-8') as file_keywords:
            for line in file_keywords:
                line = line.strip()
                if line and not line.startswith("#"):
                    self.list_file_keywords.append(line)

    def read_files(self):
        """
        Method to read domain and keywords files (community/premium modes).
        """
        self._read_domains()
        self._read_keywords()

    def print_info(self):
        """
        Method to print some configuration information.
        """
        print("[*] keywords:", self.keywords_filename)
        print("[*] keywords total:", self.keywords_total)
        print("[*] Total domains:", f"{self.domain_total:,}")

        print("[*] Threshold:", self.squatting_detector.confidence.get(self.confidence_level, "unknown"))

    def print_info_api(self):
        """
        Method to print configuration info for Premium API mode (no feed).
        """
        print("[*] keywords:", self.keywords_filename)
        print("[*] keywords total:", self.keywords_total)
        print("[*] Mode: Premium API")
        print("[*] Fuzziness:", self.api_fuzziness)

    @staticmethod
    def verify_keyword_task(detector, domains_list, keyword_info):
        """
        Static worker method for parallel execution.
        """
        keyword, keyword_line_number, keywords_total = keyword_info

        result_buffer = io.StringIO()
        print(
            f"[+] Starting Domain Squatting verification for '{keyword}' [{keyword_line_number}/{keywords_total}]",
            file=result_buffer
        )

        print(
            Fore.WHITE + "\n[*] Verifying keyword:",
            keyword,
            "[",
            keyword_line_number,
            "/",
            keywords_total,
            "]" + Style.RESET_ALL,
            file=result_buffer
        )

        result_domains = detector.check(keyword, domains_list, result_buffer)
        return result_buffer, keyword, result_domains

    def worker(self):
        """
        Method that will compute all the similarity calculations between
        the keywords and domain names.
        """
        with concurrent.futures.ProcessPoolExecutor() as executor:
            keyword_infos = [
                (keyword, i + 1, self.keywords_total)
                for i, keyword in enumerate(self.list_file_keywords) if keyword
            ]

            worker_func = functools.partial(self.verify_keyword_task, self.squatting_detector, self.list_file_domains)

            futs = [executor.submit(worker_func, k_info) for k_info in keyword_infos]

        for fut in futs:
            result_buffer, keyword, result_domains = fut.result()
            print(result_buffer.getvalue())
            self.list_domains.extend(result_domains)
            if result_domains:
                self.keyword_domains[keyword] = result_domains

        return self.list_domains

    @staticmethod
    def _api_keyword_task(client, dns_validator, rate_limiter, fuzziness, history_days, max_results,
                          keyword, idx, total):
        """Worker for one keyword in API mode. Runs in a thread."""
        result_buffer = io.StringIO()
        print(
            Fore.WHITE +
            f"\n[*] Querying API for keyword: {keyword} [ {idx} / {total} ]" +
            Style.RESET_ALL,
            file=result_buffer,
        )
        # Respect the shared rate limiter before issuing the HTTP call.
        # No-op when the user didn't set --api-rate-limit.
        rate_limiter.wait()
        try:
            result = client.lookalike(
                keyword,
                fuzziness=fuzziness,
                history_days=history_days,
                max_results=max_results,
            )
        except (APIRateLimited, APIQuotaExhausted, APIAuthError, APIPlanError):
            # Re-raise so the parent can stop the run.
            raise
        except APIBadRequest as e:
            print(
                Fore.YELLOW + f"[!] Bad request for '{keyword}': {e}" + Style.RESET_ALL,
                file=result_buffer,
            )
            return result_buffer, keyword, None
        except APIError as e:
            print(
                Fore.YELLOW + f"[!] API error for '{keyword}': {e}" + Style.RESET_ALL,
                file=result_buffer,
            )
            return result_buffer, keyword, None

        for d in result.domains:
            # d is a LookalikeDomain; stream the punycode form and,
            # for IDN homographs, append the unicode rendering so the
            # operator sees the actual characters being impersonated.
            if d.idn and d.unicode:
                found_line = f"[+] Found {d.domain}  ({d.unicode})"
            else:
                found_line = f"[+] Found {d.domain}"
            print(
                Style.BRIGHT + Fore.RED +
                found_line +
                Style.RESET_ALL,
                file=result_buffer,
            )
            if dns_validator.use_dns:
                dns_validator.check_domain(d.domain, result_buffer)

        return result_buffer, keyword, result

    def _run_api_worker(self, api_options):
        """
        Run --api mode. One APIClient shared across a thread pool, one task
        per keyword. Honors --dns by annotating each returned domain and
        --api-rate-limit by capping outbound request rate across all workers.

        Stops on:
          - quota exhaustion (429 without Retry-After) — red warning, partial
            results, forces api_balance to 0
          - rate limit (429 with Retry-After)          — yellow warning, partial
            results, preserves the real api_balance
          - auth error (401)                           — red error, exit(-1)
          - plan error (403)                           — red error, exit(-1)
        """
        if api_options is None or not api_options.api_key:
            print(
                Style.BRIGHT + Fore.RED +
                "[ERROR] API mode requires an api_key in api_options" +
                Style.RESET_ALL
            )
            exit(-1)

        seen_balances = []
        quota_exhausted = False
        rate_limited = False
        rate_limiter = _RateLimiter(api_options.rate_limit)

        with APIClient(api_options.api_key) as client:
            keyword_count = len(self.list_file_keywords)
            if keyword_count == 0:
                return self.list_domains

            max_workers = max(1, min(8, keyword_count))

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            try:
                fut_to_keyword = {}
                for idx, keyword in enumerate(self.list_file_keywords, start=1):
                    fut = executor.submit(
                        self._api_keyword_task,
                        client,
                        self.dns_validator,
                        rate_limiter,
                        self.api_fuzziness,
                        api_options.history_days,
                        api_options.max_results,
                        keyword,
                        idx,
                        keyword_count,
                    )
                    fut_to_keyword[fut] = keyword

                # Iterate in submission (insertion) order, not completion
                # order, so per-keyword output appears in the same order as
                # the keywords file. All futures are already submitted, so
                # the API calls still run fully in parallel — .result() on
                # each just blocks until that specific future is done.
                for fut in fut_to_keyword:
                    # Skip any already-cancelled futures (after 429 shutdown).
                    if fut.cancelled():
                        continue

                    try:
                        buffer, keyword, result = fut.result()
                    except APIRateLimited as e:
                        if not rate_limited:
                            print(
                                Style.BRIGHT + Fore.YELLOW +
                                f"\n[!] Rate limit hit (retry in {e.retry_after}s): {e}\n"
                                "    Returning partial results for the keywords "
                                "processed so far." +
                                Style.RESET_ALL
                            )
                            rate_limited = True
                            # Prevent new work from starting. In-flight futures
                            # keep running so we can still drain their results.
                            executor.shutdown(wait=False, cancel_futures=True)
                        continue
                    except APIQuotaExhausted as e:
                        if not quota_exhausted:
                            print(
                                Style.BRIGHT + Fore.RED +
                                f"\n[!] API quota exhausted: {e}\n"
                                "    Returning partial results." +
                                Style.RESET_ALL
                            )
                            quota_exhausted = True
                            executor.shutdown(wait=False, cancel_futures=True)
                        continue
                    except APIAuthError as e:
                        print(
                            Style.BRIGHT + Fore.RED +
                            f"\n[ERROR] API authentication failed: {e}" +
                            Style.RESET_ALL
                        )
                        executor.shutdown(wait=False, cancel_futures=True)
                        exit(-1)
                    except APIPlanError as e:
                        print(
                            Style.BRIGHT + Fore.RED +
                            f"\n[ERROR] API plan limit exceeded: {e}" +
                            Style.RESET_ALL
                        )
                        executor.shutdown(wait=False, cancel_futures=True)
                        exit(-1)
                    except concurrent.futures.CancelledError:
                        continue

                    print(buffer.getvalue())
                    self.api_calls_made += 1

                    if result is None:
                        continue

                    if result.balance is not None:
                        seen_balances.append(result.balance)

                    if result.domains:
                        # Flat string view (list_domains + keyword_domains)
                        # is what post-processing filters and TXT output
                        # expect. Rich view (keyword_domains_meta) carries
                        # the per-domain metadata for JSON and CSV output.
                        domain_strings = [d.domain for d in result.domains]
                        self.list_domains.extend(domain_strings)
                        self.keyword_domains[keyword] = domain_strings
                        self.keyword_domains_meta[keyword] = list(result.domains)
            finally:
                executor.shutdown(wait=True)

        if seen_balances:
            self.api_balance_initial = max(seen_balances)
            self.api_balance = min(seen_balances)

        # Quota exhaustion (permanent) forces balance display to 0. Rate
        # limiting (transient) deliberately does NOT — the real balance is
        # preserved so users can see what they actually have remaining.
        if quota_exhausted:
            self.api_balance = 0

        # Surface the rate-limit flag so cli.py can show a distinct reason
        # line in the run summary.
        self.rate_limited = rate_limited

        return self.list_domains

    def main(
        self,
        keywords_file,
        confidence_level,
        domains_file,
        dns,
        doppelganger_only=False,
        feed_url="https://feeds.opensquat.com/opensquat-nrd-latest.txt",
        mode="community",
        api_options=None,
        premium_api_key=None,
    ):
        print("+---------- Checking Domain Squatting ----------+")
        self.keywords_filename = keywords_file
        self.domain_filename = domains_file
        self.confidence_level = confidence_level
        self.doppelganger_only = doppelganger_only
        self.mode = mode

        self.dns_validator = DNSValidator(use_dns=dns)
        self.squatting_detector = SquattingDetector(
            confidence_level=confidence_level,
            doppelganger_only=doppelganger_only,
            dns_validator=self.dns_validator
        )

        if mode == "premium_api":
            # Premium API mode skips feed download and local Levenshtein.
            self.keywords_total = file_input.InputFile().main(keywords_file, None)
            self._read_keywords()
            self.api_fuzziness = (
                api_options.fuzziness
                if api_options and api_options.fuzziness
                else _CONFIDENCE_TO_FUZZINESS.get(confidence_level, "auto")
            )
            self.print_info_api()
            return self._run_api_worker(api_options)

        # community / premium_feed: download or load a local feed, then local detection.
        if mode == "premium_feed":
            self.feed_manager = FeedManager(
                feed_url=PREMIUM_FEED_URL,
                api_key=premium_api_key,
                premium=True,
            )
        else:
            self.feed_manager = FeedManager(feed_url=feed_url)

        if self.domain_filename == "":
            self.domain_filename = self.feed_manager.local_filename
            self.feed_manager.ensure_feeds()

        self.count_files()
        self.read_files()
        self.print_info()

        return self.worker()
