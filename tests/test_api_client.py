# -*- coding: utf-8 -*-
"""Tests for opensquat.api_client."""
from unittest import TestCase
from unittest.mock import MagicMock

import requests

from opensquat.api_client import (
    APIClient,
    APIAuthError,
    APIBadRequest,
    APIError,
    APIPlanError,
    APIQuotaExhausted,
    APIRateLimited,
    LookalikeDomain,
    LookalikeResult,
)


def _mock_response(status_code, json_body=None, raise_on_json=False,
                   headers=None, text=None):
    """
    Build a MagicMock response.

    The explicit `headers` default to `{}` (not a MagicMock). Without this,
    `response.headers.get("Retry-After")` on a default MagicMock would return
    ANOTHER MagicMock (truthy), breaking the rate-limit vs quota branch.
    """
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers if headers is not None else {}
    if text is not None:
        response.text = text
    if raise_on_json:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = json_body or {}
    return response


SAMPLE_OK_BODY = {
    "keyword": "paypal",
    "count": 4,
    "total": 48,
    "balance": 199,
    "history_days": 7,
    "max_results": 50,
    "query_time": 0.142,
    "results": [
        {"domain": "paypal-verify.com", "tld": "com", "date": "29-03-2026"},
        {"domain": "paypal-login-secure.net", "tld": "net", "date": "29-03-2026"},
        {
            "domain": "xn--pypal-4ve.com",
            "tld": "com",
            "date": "29-03-2026",
            "idn": True,
            "unicode_domain": "p\u0430ypal.com",
        },
        {"domain": "my-paypal-support.org", "tld": "org", "date": "28-03-2026"},
    ],
}


class TestAPIClientInit(TestCase):

    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            APIClient(api_key="")
        with self.assertRaises(ValueError):
            APIClient(api_key=None)

    def test_sets_session_headers(self):
        session = MagicMock()
        session.headers = {}
        APIClient(api_key="os_test_key", session=session)
        self.assertEqual("os_test_key", session.headers["x-api-key"])
        self.assertTrue(session.headers["User-Agent"].startswith("openSquat-"))
        self.assertEqual("application/json", session.headers["Accept"])

    def test_strips_trailing_slash_from_base_url(self):
        client = APIClient(
            api_key="k", base_url="https://example.com/", session=MagicMock(headers={})
        )
        self.assertEqual("https://example.com", client.base_url)

    def test_context_manager_closes_session(self):
        session = MagicMock(headers={})
        with APIClient(api_key="k", session=session) as _:
            pass
        session.close.assert_called_once()


class TestLookalikeHappyPath(TestCase):

    def setUp(self):
        self.session = MagicMock(headers={})
        self.client = APIClient(api_key="os_test_key", session=self.session)

    def test_returns_punycode_domains(self):
        self.session.post.return_value = _mock_response(200, SAMPLE_OK_BODY)

        result = self.client.lookalike("paypal")

        self.assertIsInstance(result, LookalikeResult)
        self.assertEqual("paypal", result.keyword)
        # result.domains is now list[LookalikeDomain]; compare the
        # punycode strings via .domain for the string-ordering check.
        self.assertEqual(
            [
                "paypal-verify.com",
                "paypal-login-secure.net",
                "xn--pypal-4ve.com",
                "my-paypal-support.org",
            ],
            [d.domain for d in result.domains],
        )
        self.assertEqual(199, result.balance)
        self.assertEqual(4, result.count)
        self.assertEqual(48, result.total)
        self.assertEqual(0.142, result.query_time)

    def test_idn_domain_returned_as_punycode(self):
        self.session.post.return_value = _mock_response(200, SAMPLE_OK_BODY)
        result = self.client.lookalike("paypal")
        domain_strings = [d.domain for d in result.domains]
        self.assertIn("xn--pypal-4ve.com", domain_strings)
        self.assertNotIn("p\u0430ypal.com", domain_strings)

    def test_preserves_per_domain_metadata(self):
        """Premium API mode must preserve tld, date, idn flag, and unicode
        rendering from the response body - that's the whole point of the
        enriched schema."""
        self.session.post.return_value = _mock_response(200, SAMPLE_OK_BODY)
        result = self.client.lookalike("paypal")

        # Every entry should have tld and date populated from the fixture.
        for d in result.domains:
            self.assertIsNotNone(d.tld)
            self.assertIsNotNone(d.date)

        # The IDN entry should have idn=True and its unicode rendering.
        idn_entries = [d for d in result.domains if d.idn]
        self.assertEqual(1, len(idn_entries))
        idn = idn_entries[0]
        self.assertEqual("xn--pypal-4ve.com", idn.domain)
        self.assertEqual("com", idn.tld)
        self.assertEqual("p\u0430ypal.com", idn.unicode)

        # Non-IDN entries should have idn=False and unicode=None.
        plain = [d for d in result.domains if not d.idn]
        self.assertEqual(3, len(plain))
        for d in plain:
            self.assertFalse(d.idn)
            self.assertIsNone(d.unicode)

    def test_missing_optional_fields_default_cleanly(self):
        """A server response that omits optional fields (tld, date, idn)
        must not crash - optional fields default to None / False."""
        body = {
            "keyword": "test",
            "results": [{"domain": "minimal.example"}],
        }
        self.session.post.return_value = _mock_response(200, body)
        result = self.client.lookalike("test")
        self.assertEqual(1, len(result.domains))
        d = result.domains[0]
        self.assertEqual("minimal.example", d.domain)
        self.assertIsNone(d.tld)
        self.assertIsNone(d.date)
        self.assertFalse(d.idn)
        self.assertIsNone(d.unicode)
        self.assertIsInstance(d, LookalikeDomain)

    def test_url_encodes_keyword(self):
        self.session.post.return_value = _mock_response(200, SAMPLE_OK_BODY)
        self.client.lookalike("hello world")
        called_url = self.session.post.call_args[0][0]
        self.assertIn("hello%20world", called_url)

    def test_url_encodes_unicode_keyword(self):
        self.session.post.return_value = _mock_response(200, SAMPLE_OK_BODY)
        self.client.lookalike("p\u00e4ypal")
        called_url = self.session.post.call_args[0][0]
        self.assertIn("p%C3%A4ypal", called_url)

    def test_optional_params_omitted_when_none(self):
        self.session.post.return_value = _mock_response(200, SAMPLE_OK_BODY)
        self.client.lookalike("paypal")
        params = self.session.post.call_args[1]["params"]
        self.assertEqual({"format": "json"}, params)

    def test_optional_params_included_when_set(self):
        self.session.post.return_value = _mock_response(200, SAMPLE_OK_BODY)
        self.client.lookalike(
            "paypal", fuzziness="auto", history_days=7, max_results=50
        )
        params = self.session.post.call_args[1]["params"]
        self.assertEqual("json", params["format"])
        self.assertEqual("auto", params["fuzziness"])
        self.assertEqual(7, params["history_days"])
        self.assertEqual(50, params["max_results"])

    def test_empty_results_returns_empty_list(self):
        body = dict(SAMPLE_OK_BODY)
        body["results"] = []
        body["count"] = 0
        self.session.post.return_value = _mock_response(200, body)
        result = self.client.lookalike("nothing")
        self.assertEqual([], result.domains)


class TestLookalikeErrors(TestCase):

    def setUp(self):
        self.session = MagicMock(headers={})
        self.client = APIClient(api_key="os_test_key", session=self.session)

    def test_400_raises_bad_request(self):
        self.session.post.return_value = _mock_response(
            400, {"detail": "Keyword must be 2-64 characters"}
        )
        with self.assertRaises(APIBadRequest) as ctx:
            self.client.lookalike("a")
        self.assertIn("Keyword", str(ctx.exception))

    def test_401_raises_auth_error(self):
        self.session.post.return_value = _mock_response(
            401, {"detail": "Invalid or inactive API key"}
        )
        with self.assertRaises(APIAuthError):
            self.client.lookalike("paypal")

    def test_403_raises_plan_error(self):
        self.session.post.return_value = _mock_response(
            403, {"detail": "Your plan allows max 7 days history"}
        )
        with self.assertRaises(APIPlanError) as ctx:
            self.client.lookalike("paypal")
        self.assertIn("plan", str(ctx.exception).lower())

    def test_429_raises_quota_with_balance(self):
        self.session.post.return_value = _mock_response(
            429,
            {
                "detail": "Quota exceeded. Please upgrade your plan or wait for quota reset.",
                "balance": 0,
            },
        )
        with self.assertRaises(APIQuotaExhausted) as ctx:
            self.client.lookalike("paypal")
        self.assertEqual(0, ctx.exception.balance)

    def test_500_raises_generic_api_error(self):
        self.session.post.return_value = _mock_response(500, {"detail": "internal"})
        with self.assertRaises(APIError) as ctx:
            self.client.lookalike("paypal")
        # Make sure it's NOT one of the typed subclasses
        self.assertNotIsInstance(ctx.exception, APIAuthError)
        self.assertNotIsInstance(ctx.exception, APIPlanError)
        self.assertNotIsInstance(ctx.exception, APIQuotaExhausted)
        self.assertNotIsInstance(ctx.exception, APIBadRequest)

    def test_network_error_wrapped_in_api_error(self):
        self.session.post.side_effect = requests.exceptions.ConnectionError("boom")
        with self.assertRaises(APIError) as ctx:
            self.client.lookalike("paypal")
        self.assertIn("Network error", str(ctx.exception))

    def test_invalid_json_in_200_response_raises(self):
        self.session.post.return_value = _mock_response(200, raise_on_json=True)
        with self.assertRaises(APIError) as ctx:
            self.client.lookalike("paypal")
        self.assertIn("parse JSON", str(ctx.exception))

    def test_empty_keyword_raises(self):
        with self.assertRaises(APIBadRequest):
            self.client.lookalike("")


class TestRateLimitHandling(TestCase):
    """429 responses split: with Retry-After => rate limit, without => quota."""

    def setUp(self):
        self.session = MagicMock(headers={})
        self.client = APIClient(api_key="os_test_key", session=self.session)

    def test_429_with_retry_after_raises_rate_limited(self):
        self.session.post.return_value = _mock_response(
            429,
            raise_on_json=True,
            headers={"Retry-After": "10"},
            text="You are being rate-limited, please wait some more time.",
        )
        with self.assertRaises(APIRateLimited) as ctx:
            self.client.lookalike("paypal")
        self.assertEqual(10, ctx.exception.retry_after)
        self.assertIn("rate-limited", str(ctx.exception).lower())

    def test_429_without_retry_after_still_raises_quota(self):
        # Regression guard: the existing test covers this path, but make the
        # contract explicit now that the 429 branch discriminates on header.
        self.session.post.return_value = _mock_response(
            429, {"detail": "Quota exceeded", "balance": 0}
        )
        with self.assertRaises(APIQuotaExhausted) as ctx:
            self.client.lookalike("paypal")
        self.assertNotIsInstance(ctx.exception, APIRateLimited)

    def test_429_with_non_integer_retry_after_defaults_to_10(self):
        self.session.post.return_value = _mock_response(
            429,
            raise_on_json=True,
            headers={"Retry-After": "garbage"},
            text="Rate limited",
        )
        with self.assertRaises(APIRateLimited) as ctx:
            self.client.lookalike("paypal")
        self.assertEqual(10, ctx.exception.retry_after)


class TestExtractDetailFallback(TestCase):
    """_extract_detail now falls back to response.text when body is not JSON."""

    def test_returns_plain_text_when_not_json(self):
        response = _mock_response(
            429, raise_on_json=True, text="Rate limited: slow down"
        )
        self.assertEqual(
            "Rate limited: slow down",
            APIClient._extract_detail(response),
        )

    def test_strips_whitespace_from_plain_text(self):
        response = _mock_response(
            500, raise_on_json=True, text="  oops  \n"
        )
        self.assertEqual("oops", APIClient._extract_detail(response))

    def test_truncates_long_text_to_200_chars(self):
        long_text = "x" * 500
        response = _mock_response(500, raise_on_json=True, text=long_text)
        result = APIClient._extract_detail(response)
        self.assertIsNotNone(result)
        self.assertLessEqual(len(result), 200)

    def test_empty_text_returns_none(self):
        response = _mock_response(429, raise_on_json=True, text="")
        self.assertIsNone(APIClient._extract_detail(response))

    def test_whitespace_only_text_returns_none(self):
        response = _mock_response(429, raise_on_json=True, text="   \n\t  ")
        self.assertIsNone(APIClient._extract_detail(response))

    def test_json_body_still_preferred_over_text(self):
        # If the JSON parse succeeds, use body.get("detail"); don't fall
        # through to response.text even if it's also set.
        response = _mock_response(
            400, {"detail": "bad keyword"}, text="different text"
        )
        self.assertEqual("bad keyword", APIClient._extract_detail(response))
