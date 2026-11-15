"""Consistent JSON responses for the API."""

from django.http import JsonResponse


def json_error(message, status=400, fields=None):
    payload = {"error": message}
    if fields:
        payload["fields"] = fields
    return JsonResponse(payload, status=status)
