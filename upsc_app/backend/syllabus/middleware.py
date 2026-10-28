import json
import time
import traceback
from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .models import ApiLog


def local_learner():
    """The single learner this local app belongs to — no login involved."""
    User = get_user_model()
    user = User.objects.filter(is_active=True).order_by("id").first()
    return user or User.objects.create_user("local")


class LocalLearnerMiddleware:
    """
    Single-user local app: an unauthenticated request is the learner.

    Views still carry @login_required; this makes them always pass instead of
    bouncing to /accounts/login/. A real login (e.g. /admin/) still wins,
    because only anonymous requests are substituted.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            request.user = local_learner()
        return self.get_response(request)

# Paths you never want to log (static, admin, health checks, etc.)
SKIP_PATHS = getattr(
    settings,
    "API_LOG_SKIP_PATHS",
    [
        "/admin/",
        "/static/",
        "/media/",
        "/favicon.ico",
        "/health/",
    ],
)

# Headers we keep (never log Authorization / Cookie fully)
SAFE_HEADERS = {
    "content-type",
    "accept",
    "user-agent",
    "x-forwarded-for",
    "x-request-id",
}


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _safe_json(data, max_size=50_000):
    """Convert to JSON-serializable form and truncate if too large."""
    try:
        if data is None:
            return None
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8", errors="replace")
        text = json.dumps(data, default=str)
        if len(text) > max_size:
            return {"_truncated": True, "preview": text[:max_size]}
        return json.loads(text)  # round-trip so it is pure JSON
    except Exception:
        return {"_error": "could not serialize"}


class ApiLoggingMiddleware(MiddlewareMixin):
    """
    Saves both request input and response output.
    Logging is performed only inside process_response / process_exception
    so the log entry is always written on the way out.
    """

    def process_request(self, request):
        # Mark start time – we only write the log later
        request._api_log_start = time.perf_counter()
        return None

    def process_response(self, request, response):
        self._write_log(request, response, error_message="", tb="")
        return response

    def process_exception(self, request, exception):
        # Still create a log entry even when the view crashes
        tb = traceback.format_exc()
        # We let Django continue handling the exception;
        # process_response will still be called for the error response.
        # Store the traceback temporarily so process_response can pick it up.
        request._api_log_exception = (str(exception), tb)
        return None

    def _write_log(self, request, response, error_message="", tb=""):
        path = request.path

        # Skip noisy paths
        if any(path.startswith(p) for p in SKIP_PATHS):
            return

        # Only log API-ish routes (optional – remove if you want everything)
        # if not path.startswith("/api/"):
        #     return

        start = getattr(request, "_api_log_start", None)
        duration_ms = int((time.perf_counter() - start) * 1000) if start else None

        # Pull exception info if the view raised
        if hasattr(request, "_api_log_exception"):
            error_message, tb = request._api_log_exception

        # ---- Request side ----
        query_params = dict(request.GET)

        # Body – only try to parse JSON / form data
        request_body = None
        content_type = request.content_type or ""
        if request.method in ("POST", "PUT", "PATCH"):
            if "application/json" in content_type:
                try:
                    request_body = json.loads(request.body or b"{}")
                except Exception:
                    request_body = {
                        "_raw": (request.body or b"")[:2000].decode("utf-8", "replace")
                    }
            elif (
                "multipart/form-data" in content_type
                or "application/x-www-form-urlencoded" in content_type
            ):
                request_body = request.POST.dict()
                # Note: we intentionally do NOT store uploaded files

        # Selected headers
        headers = {
            k.lower(): v
            for k, v in request.headers.items()
            if k.lower() in SAFE_HEADERS
        }

        # ---- Response side ----
        response_body = None
        if hasattr(response, "content"):
            try:
                # Prefer JSON responses
                if "application/json" in (response.get("Content-Type") or ""):
                    response_body = json.loads(response.content.decode("utf-8"))
                else:
                    # Truncate non-JSON
                    text = response.content.decode("utf-8", errors="replace")
                    response_body = {"_text_preview": text[:2000]}
            except Exception:
                response_body = {"_error": "could not parse response body"}

        # ---- Persist ----
        try:
            ApiLog.objects.create(
                path=path[:512],
                method=request.method,
                query_params=_safe_json(query_params),
                request_body=_safe_json(request_body),
                headers=_safe_json(headers),
                status_code=response.status_code,
                response_body=_safe_json(response_body),
                user=(
                    request.user
                    if getattr(request, "user", None) and request.user.is_authenticated
                    else None
                ),
                ip_address=_get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
                duration_ms=duration_ms,
                error_message=error_message[:4000] if error_message else "",
                traceback=tb[:10000] if tb else "",
            )
        except Exception:
            # Never let logging break the real response
            pass
