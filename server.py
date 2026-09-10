"""openSquat Web API and frontend server."""
from __future__ import annotations

import asyncio
import os
import re
import socket
import sys
from functools import partial
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OPENSQUAT_DIR = BASE_DIR.parent / "opensquat"
sys.path.insert(0, str(OPENSQUAT_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from scanner_service import ScanRequest, run_scan

STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="openSquat Web",
    description="Web frontend for domain squatting detection",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def strip_ansi(text: str) -> str:
    """Removes terminal ANSI color codes (e.g. [37m, [0m) from scan logs."""
    if not text:
        return ""
    ansi_regex = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_regex.sub("", text)


class ScanBody(BaseModel):
    keywords: list[str] = Field(..., min_length=1, description="Brand names to monitor")
    mode: str = Field(default="community", pattern="^(community|premium_feed|premium_api)$")
    confidence: int = Field(default=1, ge=0, le=4)
    dns: bool = False
    doppelganger: bool = False
    doppelganger_strict: bool = False
    portcheck: bool = False
    vt: bool = False
    strict_filters: bool = False
    api_key: str | None = None
    api_fuzziness: str | None = Field(default=None, pattern="^(exact|low|high|auto)$")
    api_history_days: int | None = Field(default=None, ge=1)
    api_max_results: int | None = Field(default=None, ge=1)
    api_rate_limit: int | None = Field(default=None, ge=1)


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    opensquat_ok = OPENSQUAT_DIR.is_dir() and (OPENSQUAT_DIR / "app.py").is_file()
    vt_key_exists = (OPENSQUAT_DIR / "vt_key.txt").is_file() or (BASE_DIR / "vt_key.txt").is_file()
    
    return {
        "status": "ok" if opensquat_ok else "degraded",
        "opensquat_path": str(OPENSQUAT_DIR),
        "opensquat_found": opensquat_ok,
        "vt_key_found": vt_key_exists,
    }


@app.post("/api/scan")
async def scan(body: ScanBody):
    if not OPENSQUAT_DIR.is_dir():
        raise HTTPException(status_code=500, detail="openSquat installation not found")

    # Load VirusTotal key into environment if present
    vt_file_opensquat = OPENSQUAT_DIR / "vt_key.txt"
    vt_file_web = BASE_DIR / "vt_key.txt"
    
    if vt_file_opensquat.is_file():
        try:
            os.environ["VT_API_KEY"] = vt_file_opensquat.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    elif vt_file_web.is_file():
        try:
            os.environ["VT_API_KEY"] = vt_file_web.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    request = ScanRequest(
        keywords=body.keywords,
        mode=body.mode,  # type: ignore[arg-type]
        confidence=body.confidence,
        dns=body.dns,
        doppelganger=body.doppelganger,
        doppelganger_strict=body.doppelganger_strict,
        portcheck=body.portcheck,
        vt_check=body.vt,
        strict_filters=body.strict_filters,
        api_key=body.api_key,
        api_fuzziness=body.api_fuzziness,
        api_history_days=body.api_history_days,
        api_max_results=body.api_max_results,
        api_rate_limit=body.api_rate_limit,
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        partial(run_scan, request, str(OPENSQUAT_DIR)),
    )

    # Strip ANSI escape sequences from logs prior to response
    cleaned_logs = strip_ansi(result.logs) if result.logs else ""

    if not result.success:
        detail_msg = result.error or "Scan failed"
        if cleaned_logs:
            detail_msg += f"\nLogs:\n{cleaned_logs}"
        raise HTTPException(
            status_code=400 if result.error and "requires" in result.error.lower() else 500,
            detail=detail_msg,
        )

    return {
        "success": result.success,
        "duration_seconds": result.duration_seconds,
        "total_domains": result.total_domains,
        "detected_count": result.detected_count,
        "confidence": result.confidence,
        "confidence_label": result.confidence_label,
        "strict_filters": result.strict_filters,
        "mode": result.mode,
        "keywords_total": result.keywords_total,
        "domains_in_feed": result.domains_in_feed,
        "results": result.results,
        "logs": cleaned_logs,
        "api_calls_made": result.api_calls_made,
        "api_balance": result.api_balance,
    }


def find_free_port(host: str = "127.0.0.1", start_port: int = 8000) -> int:
    """Finds an available port starting from start_port."""
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                port += 1
    return start_port


if __name__ == "__main__":
    import uvicorn

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    
    selected_port = find_free_port("127.0.0.1", 8000)
    
    print("\n" + "="*50)
    print(f"🚀 Server starting on http://127.0.0.1:{selected_port}")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="127.0.0.1", port=selected_port, reload=False)