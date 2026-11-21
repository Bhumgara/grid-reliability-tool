"""
ETag and 304 Not Modified for the API's GET responses.

Each successful GET under ``/api`` gets a weak ETag built from a hash of the
response body. A client that sends it back in ``If-None-Match`` gets
``304 Not Modified`` with no body when nothing changed.

The hash is of the content, not the refresh time, so it also changes when
the model is retrained or a deploy changes a response's format. Weak
(``W/"..."``) because gzip, which runs outside this middleware, changes the
bytes but not the content.
"""

from __future__ import annotations

import hashlib

from fastapi import FastAPI, Request, Response
from starlette.datastructures import MutableHeaders

# Response headers kept on a 304 (RFC 9110 15.4.5); the body and its
# Content-Type and Content-Length are dropped.
_HEADERS_KEPT_ON_304 = {"cache-control", "content-location", "date", "etag", "expires", "vary"}


def etag_for(body: bytes) -> str:
    """Weak ETag for a response body."""
    return f'W/"{hashlib.sha256(body).hexdigest()[:32]}"'


def _opaque(tag: str) -> str:
    """The quoted part of an ETag, for weak comparison."""
    tag = tag.strip()
    return tag[2:] if tag.startswith("W/") else tag


def matches(if_none_match: str, etag: str) -> bool:
    """
    True if the ``If-None-Match`` header matches ``etag`` (weak comparison).

    Accepts a single tag, a comma-separated list, or ``*``.
    """
    candidates = [part.strip() for part in if_none_match.split(",") if part.strip()]
    return "*" in candidates or _opaque(etag) in {_opaque(tag) for tag in candidates}


def add_etag_middleware(app: FastAPI, prefix: str) -> None:
    """Add the ETag middleware for GET requests under ``prefix``."""

    @app.middleware("http")
    async def etag_middleware(request: Request, call_next) -> Response:
        response = await call_next(request)

        if (
            request.method != "GET"
            or response.status_code != 200
            or not request.url.path.startswith(prefix)
        ):
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        etag = etag_for(body)
        headers = MutableHeaders(raw=list(response.raw_headers))
        headers["etag"] = etag

        if matches(request.headers.get("if-none-match", ""), etag):
            kept = {
                name: value
                for name, value in headers.items()
                if name.lower() in _HEADERS_KEPT_ON_304
            }
            return Response(status_code=304, headers=kept)

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(headers),
        )
