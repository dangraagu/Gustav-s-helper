#!/usr/bin/env python3
"""
Gustav's Helper — step-report forwarder.

The plugin ships in a PUBLIC repo, so any URL inside it is public. This tiny service is what the plugin
posts to; it holds the Discord webhook privately in an environment variable and forwards reports to it.

Why this is safer than putting the webhook in the plugin:
  * the webhook URL is never published, so it cannot be extracted, deleted, or auto-revoked by GitHub's
    secret scanning;
  * the payload is REBUILT here, so a direct caller cannot smuggle @everyone pings, embeds, files, a fake
    username/avatar, or any other Discord field — only a plain text report gets through;
  * abuse can be blocked here (rate limit / IP block / turning the service off) with no plugin release.

Run:  DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...' uvicorn app:app --host 127.0.0.1 --port 8123
"""
import os
import time
from collections import deque

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
MAX_CONTENT = 1900          # Discord's hard cap is 2000; leave room for the prefix below
MAX_BODY_BYTES = 8 * 1024   # a report is ~500 bytes; anything larger is not a real report
RATE_WINDOW_S = 60
RATE_MAX_PER_IP = 5         # a human reporting steps sends far fewer than this
RATE_MAX_GLOBAL = 120       # backstop if many clients report at once

app = FastAPI(title="Gustav's Helper report forwarder", docs_url=None, redoc_url=None, openapi_url=None)

_by_ip: dict[str, deque] = {}
_global: deque = deque()


def _allow(ip: str) -> bool:
    """Sliding-window rate limit, per IP and overall. In-memory on purpose: one process, no dependency."""
    now = time.monotonic()
    for bucket in (_by_ip.setdefault(ip, deque()), _global):
        while bucket and now - bucket[0] > RATE_WINDOW_S:
            bucket.popleft()
    if len(_by_ip[ip]) >= RATE_MAX_PER_IP or len(_global) >= RATE_MAX_GLOBAL:
        return False
    _by_ip[ip].append(now)
    _global.append(now)
    if len(_by_ip) > 10000:      # keep the map bounded regardless of traffic
        for k in [k for k, v in _by_ip.items() if not v]:
            _by_ip.pop(k, None)
    return True


def _client_ip(request: Request) -> str:
    # Caddy sets X-Forwarded-For; trust only the first hop since we are behind our own proxy.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


@app.get("/healthz")
async def healthz():
    return {"ok": True, "webhook_configured": bool(WEBHOOK)}


@app.post("/report")
async def report(request: Request):
    if not WEBHOOK:
        return JSONResponse({"error": "not configured"}, status_code=503)

    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        return JSONResponse({"error": "too large"}, status_code=413)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    if not isinstance(data, dict):
        return JSONResponse({"error": "invalid json"}, status_code=400)

    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        return JSONResponse({"error": "missing content"}, status_code=400)

    if not _allow(_client_ip(request)):
        return JSONResponse({"error": "rate limited"}, status_code=429)

    # REBUILD the payload: only the text survives. Nothing the caller sends can become a mention, an
    # embed, a file, or a spoofed username — those fields simply are not forwarded.
    payload = {
        "content": content[:MAX_CONTENT],
        "allowed_mentions": {"parse": []},
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                WEBHOOK,
                json=payload,
                headers={"User-Agent": "GustavsHelper-report-forwarder/1.0"},
            )
    except Exception:
        return JSONResponse({"error": "upstream unreachable"}, status_code=502)

    if r.status_code in (200, 204):
        return Response(status_code=204)
    if r.status_code == 429:
        return JSONResponse({"error": "rate limited"}, status_code=429)
    return JSONResponse({"error": "upstream rejected"}, status_code=502)
