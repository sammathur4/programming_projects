import traceback
from .models import ApiLog


def log_error(
    request=None,
    *,
    message: str = "",
    exception: Exception | None = None,
    extra: dict | None = None,
    path: str = "",
    method: str = "INTERNAL",
):
    """
    Call this anywhere inside a view / service / helper when you catch an error
    and still want a permanent record in api_logs.

    Example:
        try:
            ...
        except SomeError as e:
            log_error(request, message="Failed to grade answer", exception=e)
            return JsonResponse({"error": "…"}, status=500)
    """
    tb = ""
    if exception is not None:
        tb = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
        if not message:
            message = str(exception)

    try:
        ApiLog.objects.create(
            path=(path or (request.path if request else "internal"))[:512],
            method=method if not request else request.method,
            query_params={},
            request_body=extra or {},
            headers={},
            status_code=500,
            response_body=None,
            user=(
                request.user
                if request
                and getattr(request, "user", None)
                and request.user.is_authenticated
                else None
            ),
            ip_address=None,
            user_agent="",
            duration_ms=None,
            error_message=message[:4000],
            traceback=tb[:10000],
        )
    except Exception:
        # Logging must never raise
        pass
