"""Programmatic openSquat runner for the web API."""
from __future__ import annotations

import concurrent.futures
import io
import os
import tempfile
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Literal

import requests

from opensquat import app as opensquat_app
from opensquat.app import ApiOptions
from opensquat.cli import _build_json_content
from opensquat import port_check, vt


Mode = Literal["community", "premium_feed", "premium_api"]

CONFIDENCE_LABELS = {
    0: "very high confidence",
    1: "high confidence",
    2: "medium confidence",
    3: "low confidence",
    4: "very low confidence",
}


@dataclass
class ScanRequest:
    keywords: list[str]
    mode: Mode = "community"
    confidence: int = 1
    dns: bool = False
    doppelganger: bool = False
    doppelganger_strict: bool = False
    portcheck: bool = False
    vt_check: bool = False
    strict_filters: bool = False
    api_key: str | None = None
    api_fuzziness: str | None = None
    api_history_days: int | None = None
    api_max_results: int | None = None
    api_rate_limit: int | None = None
    feed_url: str = "https://feeds.opensquat.com/opensquat-nrd-latest.txt"


@dataclass
class ScanResult:
    success: bool
    duration_seconds: float
    total_domains: int
    detected_count: int
    mode: str
    confidence: int
    confidence_label: str
    keywords_total: int
    domains_in_feed: int
    results: list[dict[str, Any]] = field(default_factory=list)
    logs: str = ""
    error: str | None = None
    api_calls_made: int | None = None
    api_balance: int | None = None
    strict_filters: bool = False


def _resolve_api_key(request: ScanRequest, opensquat_dir: str) -> str | None:
    if request.api_key and request.api_key.strip():
        clean_key = request.api_key.strip()
        # Ensure escaped literals or placeholders from the UI are ignored
        if not clean_key.startswith("os\\") and "\\x" not in clean_key:
            return clean_key

    key_file = os.path.join(opensquat_dir, "api_key.txt")
    if os.path.isfile(key_file):
        try:
            from opensquat.auth import _read_first_usable_line
            return _read_first_usable_line(key_file)
        except Exception:
            pass

    env_key = os.environ.get("OPENSQUAT_API_KEY", "").strip()
    if env_key and "\\x" not in env_key:
        return env_key
    return None


def _write_keywords_file(keywords: list[str]) -> str:
    cleaned = [k.strip() for k in keywords if k.strip() and not k.strip().startswith("#")]
    if not cleaned:
        raise ValueError("At least one keyword is required")
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".txt",
        delete=False,
    )
    handle.write("\n".join(cleaned))
    handle.write("\n")
    handle.close()
    return handle.name


def _check_https_reachable(domain: str) -> tuple[bool, str]:
    try:
        response = requests.get(f"https://{domain}", timeout=5, allow_redirects=True)
        return True, str(response.status_code)
    except Exception as exc:
        return False, str(exc)


def _safe_vt_check(domain: str) -> int | None:
    """Safely query VirusTotal without crashing on empty responses or missing keys."""
    try:
        vt_instance = vt.VirusTotal()
        votes = vt_instance.main(domain)
        if votes is not None and isinstance(votes, (list, tuple)) and len(votes) > 1:
            return votes[1]
    except Exception:
        pass
    return None


def _domain_passes_checks(entry: dict[str, Any], request: ScanRequest) -> bool:
    if request.doppelganger and not entry.get("reachable"):
        return False
    if request.portcheck and not entry.get("ports_open"):
        return False
    if request.vt_check:
        vt_val = entry.get("vt_malicious")
        if vt_val is None or vt_val <= 0:
            return False
    return True


def _enrich_domains(scanner, request: ScanRequest) -> list[dict[str, Any]]:
    """Run optional checks on every detected domain and return flat enriched rows."""
    meta = getattr(scanner, "keyword_domains_meta", {}) or {}
    rows: list[dict[str, Any]] = []

    for keyword, domains in scanner.keyword_domains.items():
        rich_list = meta.get(keyword, [])
        rich_by_domain = {d.domain: d for d in rich_list}
        for domain in domains:
            entry: dict[str, Any] = {"keyword": keyword, "domain": domain}
            d = rich_by_domain.get(domain)
            if d is not None:
                if d.tld is not None:
                    entry["tld"] = d.tld
                if d.date is not None:
                    entry["date"] = d.date
                entry["idn"] = d.idn
                if d.idn and d.unicode:
                    entry["unicode"] = d.unicode
            else:
                entry["idn"] = False

            rows.append(entry)

    if request.doppelganger:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                row["domain"]: executor.submit(_check_https_reachable, row["domain"])
                for row in rows
            }
        for row in rows:
            reachable, info = futures[row["domain"]].result()
            row["reachable"] = reachable
            row["reachability"] = info

    if request.portcheck:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                row["domain"]: executor.submit(port_check.PortCheck().main, row["domain"])
                for row in rows
            }
        for row in rows:
            ports = futures[row["domain"]].result()
            row["ports_open"] = bool(ports)
            row["ports"] = ports or ""

    if request.vt_check:
        for row in rows:
            malicious = _safe_vt_check(row["domain"])
            row["vt_malicious"] = malicious
            if malicious is not None:
                row["vt_flagged"] = malicious > 0 or malicious < 0
            else:
                row["vt_flagged"] = False

    for row in rows:
        row["passes_filters"] = _domain_passes_checks(row, request)

    return rows


def _rows_to_grouped_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        domain_entry = {k: v for k, v in row.items() if k != "keyword"}
        grouped.setdefault(row["keyword"], []).append(domain_entry)
    return [{"keyword": kw, "domains": doms} for kw, doms in grouped.items()]


def run_scan(request: ScanRequest, opensquat_dir: str) -> ScanResult:
    """Run an openSquat scan and return structured JSON-friendly results."""
    original_cwd = os.getcwd()
    log_buffer = io.StringIO()
    keywords_file = None
    start = time.time()
    confidence_label = CONFIDENCE_LABELS.get(request.confidence, "unknown")

    try:
        os.chdir(opensquat_dir)

        if request.mode == "premium_api" and request.doppelganger_strict:
            raise ValueError("Doppelgänger-strict mode is incompatible with Premium API mode")

        keywords_file = _write_keywords_file(request.keywords)
        api_key = _resolve_api_key(request, opensquat_dir)

        api_options = None
        premium_api_key = None
        if request.mode == "premium_api":
            if not api_key:
                raise ValueError(
                    "Premium API mode requires an openSquat API key "
                    "(api_key field, api_key.txt, or OPENSQUAT_API_KEY)"
                )
            api_options = ApiOptions(
                api_key=api_key,
                fuzziness=request.api_fuzziness,
                history_days=request.api_history_days,
                max_results=request.api_max_results,
                rate_limit=request.api_rate_limit,
            )
        elif request.mode == "premium_feed":
            if not api_key:
                raise ValueError(
                    "Premium Feed mode requires an openSquat API key "
                    "(api_key field, api_key.txt, or OPENSQUAT_API_KEY)"
                )
            premium_api_key = api_key

        scanner = opensquat_app.Domain()

        with redirect_stdout(log_buffer):
            scanner.main(
                keywords_file,
                request.confidence,
                "",
                request.dns,
                doppelganger_only=request.doppelganger_strict,
                feed_url=request.feed_url,
                mode=request.mode,
                api_options=api_options,
                premium_api_key=premium_api_key,
            )

        detected_count = sum(len(d) for d in scanner.keyword_domains.values())

        if request.doppelganger or request.portcheck or request.vt_check:
            enriched_rows = _enrich_domains(scanner, request)
            if request.strict_filters:
                enriched_rows = [r for r in enriched_rows if r["passes_filters"]]
            json_results = _rows_to_grouped_results(enriched_rows)
            total = len(enriched_rows)
        else:
            all_domains = [d for doms in scanner.keyword_domains.values() for d in doms]
            filtered_set = set(all_domains)
            json_results = _build_json_content(scanner, filtered_set)
            total = len(all_domains)

        duration = round(time.time() - start, 2)
        return ScanResult(
            success=True,
            duration_seconds=duration,
            total_domains=total,
            detected_count=detected_count,
            mode=request.mode,
            confidence=request.confidence,
            confidence_label=confidence_label,
            keywords_total=scanner.keywords_total,
            domains_in_feed=scanner.domain_total,
            results=json_results,
            logs=log_buffer.getvalue(),
            strict_filters=request.strict_filters,
            api_calls_made=getattr(scanner, "api_calls_made", None) if request.mode == "premium_api" else None,
            api_balance=getattr(scanner, "api_balance", None) if request.mode == "premium_api" else None,
        )
    except SystemExit as exc:
        return ScanResult(
            success=False,
            duration_seconds=round(time.time() - start, 2),
            total_domains=0,
            detected_count=0,
            mode=request.mode,
            confidence=request.confidence,
            confidence_label=confidence_label,
            keywords_total=0,
            domains_in_feed=0,
            logs=log_buffer.getvalue(),
            error=f"Scan aborted (exit {exc.code})",
            strict_filters=request.strict_filters,
        )
    except Exception as exc:
        return ScanResult(
            success=False,
            duration_seconds=round(time.time() - start, 2),
            total_domains=0,
            detected_count=0,
            mode=request.mode,
            confidence=request.confidence,
            confidence_label=confidence_label,
            keywords_total=0,
            domains_in_feed=0,
            logs=log_buffer.getvalue(),
            error=str(exc),
            strict_filters=request.strict_filters,
        )
    finally:
        if keywords_file and os.path.isfile(keywords_file):
            try:
                os.unlink(keywords_file)
            except Exception:
                pass
        os.chdir(original_cwd)