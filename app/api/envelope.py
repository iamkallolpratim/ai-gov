"""The standard success envelope.

Every JSON response under the versioned API is wrapped as::

    {"success": true, "data": <payload>}

and every error as::

    {"success": false, "error": {"code": ..., "message": ..., "details": {...}}}

Wrapping happens in a custom `APIRoute` rather than in each handler, so endpoints keep
returning their natural Pydantic models and the response models stay meaningful. The
OpenAPI document is rewritten to match, so the published schema describes what clients
actually receive.

Operational endpoints (`/health`, `/ready`, `/metrics`) are deliberately **not** wrapped:
Kubernetes probes and Prometheus scrapers expect their own shapes, and putting a product
envelope in front of them would break standard tooling for no benefit.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from typing import Any, Generic, TypeVar

from fastapi import Request, Response
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    success: bool = Field(default=True, examples=[True])
    data: T


class ErrorBody(BaseModel):
    code: str = Field(examples=["UNAUTHORIZED"])
    message: str = Field(examples=["Authentication required"])
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(default=None, examples=["0f4b9a2e-6c2b-4f0e-9a4a-1c2b3d4e5f60"])


class ErrorEnvelope(BaseModel):
    success: bool = Field(default=False, examples=[False])
    error: ErrorBody


class EnvelopeRoute(APIRoute):
    """Wraps successful JSON payloads in the standard envelope."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            response = await original(request)
            return _wrap_response(response)

        return wrapped


def _wrap_response(response: Response) -> Response:
    """Wrap a successful JSON body in the envelope, in place.

    Keyed off the content type rather than the response class: depending on the FastAPI
    version and whether a `response_model` is declared, a handler's result arrives here
    as `JSONResponse` or as a plain pre-rendered `Response`.
    """
    if response.status_code >= 400 or response.status_code in _NO_BODY_STATUSES:
        return response
    if not response.headers.get("content-type", "").startswith("application/json"):
        return response
    body = getattr(response, "body", None)
    if not body:
        return response

    try:
        payload = json.loads(bytes(body))
    except (ValueError, TypeError):  # not JSON after all; leave it untouched
        return response
    # Never double-wrap: a handler may already have returned an envelope.
    if isinstance(payload, dict) and "success" in payload:
        return response

    rendered = json.dumps(
        {"success": True, "data": payload},
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    response.body = rendered
    response.headers["content-length"] = str(len(rendered))
    return response


#: Statuses that carry no body, so there is nothing to wrap.
_NO_BODY_STATUSES = frozenset({204, 205, 304})


def envelope_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Rewrite 2xx response schemas in the OpenAPI document to match the envelope."""
    for path, operations in schema.get("paths", {}).items():
        if not path.startswith("/api/"):
            continue
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            for status, response in (operation.get("responses") or {}).items():
                if not status.startswith("2"):
                    continue
                content = (response.get("content") or {}).get("application/json")
                if not content or "schema" not in content:
                    continue
                content["schema"] = {
                    "type": "object",
                    "required": ["success", "data"],
                    "properties": {
                        "success": {"type": "boolean", "default": True},
                        "data": content["schema"],
                    },
                }
    return schema
