import logging
import time
from typing import Any, cast
from uuid import UUID, uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from atlas_ml_platform.core.logging import method_var, path_var, request_id_var
from atlas_ml_platform.core.metrics import observe_http_request
from atlas_ml_platform.core.shutdown import RequestTracker

logger = logging.getLogger(__name__)


def _parse_request_id(value: str | None) -> UUID:
    if value:
        try:
            return UUID(value)
        except ValueError:
            pass
    return uuid4()


def _scope_state(scope: Scope) -> dict[str, Any]:
    state = scope.get("state")
    if isinstance(state, dict):
        return cast(dict[str, Any], state)
    state = {}
    scope["state"] = state
    return state


def _route_label(scope: Scope) -> str:
    route = scope.get("route")
    name = getattr(route, "name", None)
    return name if isinstance(name, str) and name else "unmatched"


class RequestContextMiddleware:
    """Bind a request ID, emit one access log, and echo the correlation header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _parse_request_id(Headers(scope=scope).get("x-request-id"))
        method = scope.get("method", "")
        path = scope.get("path", "")
        state = _scope_state(scope)
        state["request_id"] = request_id

        request_token = request_id_var.set(request_id)
        method_token = method_var.set(method)
        path_token = path_var.set(path)

        status_code = 500
        started = time.perf_counter()
        is_metrics_endpoint = path == "/metrics"
        drain_exempt = path in {
            "/api/v1/health",
            "/api/v1/health/ready",
            "/metrics",
        }

        app = scope.get("app")
        app_state = getattr(app, "state", None)
        if getattr(app_state, "shutting_down", False) and not drain_exempt:
            duration_seconds = time.perf_counter() - started
            observe_http_request(
                method=method,
                route="shutting_down",
                status_code=503,
                duration_seconds=duration_seconds,
            )
            logger.warning(
                "request_rejected_during_shutdown",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": 503,
                    "duration_ms": round(duration_seconds * 1000, 2),
                    "error_code": "service_unavailable",
                    "error_type": "ServiceShuttingDown",
                },
            )
            response = JSONResponse(
                status_code=503,
                content={
                    "detail": "Service is shutting down",
                    "error_code": "service_unavailable",
                    "request_id": str(request_id),
                },
                headers={"X-Request-ID": str(request_id)},
            )
            await response(scope, receive, send)
            request_id_var.reset(request_token)
            method_var.reset(method_token)
            path_var.reset(path_token)
            return

        tracker = getattr(app_state, "request_tracker", None)
        tracking = isinstance(tracker, RequestTracker) and not drain_exempt
        if tracking and isinstance(tracker, RequestTracker):
            tracker.begin()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = str(request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            if not is_metrics_endpoint:
                observe_http_request(
                    method=method,
                    route=_route_label(scope),
                    status_code=500,
                    duration_seconds=time.perf_counter() - started,
                )
                logger.exception(
                    "request_failed",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": 500,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                        "error_code": "internal_error",
                        "error_type": type(exc).__name__,
                    },
                )
            raise
        else:
            duration_seconds = time.perf_counter() - started
            if not is_metrics_endpoint:
                observe_http_request(
                    method=method,
                    route=_route_label(scope),
                    status_code=status_code,
                    duration_seconds=duration_seconds,
                )
                extra = {
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(duration_seconds * 1000, 2),
                    "error_code": state.get("error_code"),
                    "error_type": state.get("error_type"),
                }
                if status_code >= 500:
                    logger.error("request_failed", extra=extra)
                elif status_code >= 400:
                    logger.warning("request_failed", extra=extra)
                else:
                    logger.info("request_completed", extra=extra)
        finally:
            if tracking and isinstance(tracker, RequestTracker):
                tracker.end()
            request_id_var.reset(request_token)
            method_var.reset(method_token)
            path_var.reset(path_token)
