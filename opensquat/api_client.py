# -*- coding: utf-8 -*-
# Module: api_client.py
"""
openSquat REST API client.

Wraps POST /v1/nrd/lookalike/{keyword} on api.opensquat.com. Used by --api
mode to skip the local NRD feed download and run keyword lookalike queries
against the hosted service.

The client uses a single requests.Session for connection pooling and is
thread-safe for the read-mostly POST pattern used by --api mode.
"""
import json as _json
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import quote

import requests

from opensquat import __VERSION__


DEFAULT_BASE_URL = "https://api.opensquat.com"
DEFAULT_TIMEOUT = 30


@dataclass(frozen=True)
class LookalikeDomain:
    """
    One matched domain plus the per-domain metadata the server returned.

    All fields except `domain` are optional. Community and Premium Feed modes
    populate only `domain` (the NRD feed has no per-domain metadata). Premium
    API mode populates everything the server returned.
    """
    domain: str                          # punycode form, always present
    tld: Optional[str] = None            # e.g. "com"
    date: Optional[str] = None           # NRD first-seen date, e.g. "29-03-2026"
    idn: bool = False                    # True when the domain is an IDN homograph
    unicode: Optional[str] = None        # unicode rendering when idn=True


@dataclass(frozen=True)
class LookalikeResult:
    """Parsed response from POST /v1/nrd/lookalike/{keyword}."""
    keyword: str
    domains: List[LookalikeDomain] = field(default_factory=list)
    balance: Optional[int] = None
    count: int = 0
    total: int = 0
    query_time: Optional[float] = None


class APIError(Exception):
    """Generic openSquat API error."""


class APIAuthError(APIError):
    """401 Unauthorized — missing or invalid API key."""


class APIPlanError(APIError):
    """403 Forbidden — plan limit exceeded."""


class APIQuotaExhausted(APIError):
    """429 Too Many Requests — monthly quota exhausted (permanent until reset)."""

    def __init__(self, message, balance=0):
        super().__init__(message)
        self.balance = balance


class APIRateLimited(APIError):
    """429 Too Many Requests with Retry-After — transient upstream rate limit,
    distinct from permanent quota depletion. Carries the retry delay in seconds."""

    def __init__(self, message, retry_after=10):
        super().__init__(message)
        self.retry_after = retry_after


class APIBadRequest(APIError):
    """400 Bad Request — invalid keyword or parameter."""


class APIClient:
    """
    Thin client for the openSquat lookalike endpoint.

    One instance owns one requests.Session. Safe to share across threads
    in --api mode (read-mostly POST traffic, no concurrent state mutation).
    Use as a context manager to ensure the session is closed.
    """

    def __init__(self, api_key, base_url=None, timeout=DEFAULT_TIMEOUT, session=None):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update({
            "x-api-key": api_key,
            "User-Agent": f"openSquat-{__VERSION__}",
            "Accept": "application/json",
        })

    def lookalike(self, keyword, *, fuzziness=None, history_days=None, max_results=None):
        """
        Query the lookalike endpoint for a single keyword.

        Args:
            keyword: brand/term to search for (URL-encoded internally)
            fuzziness: optional override - one of exact, low, high, auto
            history_days: optional NRD history window in days
            max_results: optional cap on returned results

        Returns:
            LookalikeResult with canonical (punycode) domain strings.

        Raises:
            APIAuthError, APIPlanError, APIQuotaExhausted, APIBadRequest, APIError
        """
        if not keyword:
            raise APIBadRequest("keyword must be non-empty")

        encoded_keyword = quote(keyword, safe="")
        url = f"{self.base_url}/v1/nrd/lookalike/{encoded_keyword}"

        params = {"format": "json"}
        if fuzziness is not None:
            params["fuzziness"] = fuzziness
        if history_days is not None:
            params["history_days"] = history_days
        if max_results is not None:
            params["max_results"] = max_results

        try:
            # allow_redirects=False prevents the session's X-API-Key header
            # from being forwarded to a different host on a 30x response.
            # requests strips Authorization on cross-host redirects but
            # NOT custom headers, so a misconfigured proxy redirecting
            # api.opensquat.com elsewhere would otherwise leak the key.
            response = self._session.post(
                url, params=params, timeout=self.timeout, allow_redirects=False
            )
        except requests.exceptions.RequestException as e:
            raise APIError(f"Network error contacting {url}: {e}")

        status = response.status_code
        if status == 200:
            return self._parse_success(keyword, response)

        # Try to extract a `detail` message from the JSON body for errors
        detail = self._extract_detail(response)

        if status == 400:
            raise APIBadRequest(detail or "Bad request")
        if status == 401:
            raise APIAuthError(detail or "Invalid or missing API key")
        if status == 403:
            raise APIPlanError(detail or "Plan limit exceeded")
        if status == 429:
            # Distinguish transient upstream rate limiting (Retry-After set)
            # from permanent quota depletion (no Retry-After, JSON body with
            # balance: 0). The upstream rate limiter always sets Retry-After;
            # the openSquat API's own quota-zero response does not.
            retry_after_header = response.headers.get("Retry-After")
            if retry_after_header is not None:
                try:
                    retry_after = int(retry_after_header)
                except (TypeError, ValueError):
                    retry_after = 10  # sensible fallback
                raise APIRateLimited(
                    detail or "Rate limit hit",
                    retry_after=retry_after,
                )
            balance = self._extract_balance(response)
            raise APIQuotaExhausted(detail or "Quota exhausted", balance=balance)

        raise APIError(f"Unexpected HTTP {status} from {url}: {detail or 'no detail'}")

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---- helpers ----

    @staticmethod
    def _parse_success(keyword, response):
        try:
            body = response.json()
        except (ValueError, _json.JSONDecodeError) as e:
            raise APIError(f"Could not parse JSON response: {e}")

        results = body.get("results") or []
        domains = []
        for r in results:
            if not isinstance(r, dict):
                continue
            domain = r.get("domain")
            if not domain:
                continue
            domains.append(LookalikeDomain(
                domain=domain,
                tld=r.get("tld"),
                date=r.get("date"),
                idn=bool(r.get("idn", False)),
                unicode=r.get("unicode_domain"),
            ))

        return LookalikeResult(
            keyword=body.get("keyword", keyword),
            domains=domains,
            balance=body.get("balance"),
            count=body.get("count", len(domains)),
            total=body.get("total", 0),
            query_time=body.get("query_time"),
        )

    @staticmethod
    def _extract_detail(response):
        """
        Extract a human-readable error detail from an HTTP response.

        Preference order:
            1. JSON body's "detail" field (for well-formed API errors)
            2. Plain text body, stripped and truncated to 200 chars
               (for upstream proxies/WAFs that return text/plain bodies)
            3. None if neither source yields usable text
        """
        try:
            body = response.json()
        except (ValueError, _json.JSONDecodeError):
            text = (response.text or "").strip()
            return text[:200] if text else None
        if isinstance(body, dict):
            return body.get("detail")
        return None

    @staticmethod
    def _extract_balance(response):
        try:
            body = response.json()
        except (ValueError, _json.JSONDecodeError):
            return 0
        if isinstance(body, dict):
            return body.get("balance", 0)
        return 0
