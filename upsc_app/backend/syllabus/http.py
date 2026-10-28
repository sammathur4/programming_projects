from django.http import JsonResponse


def json_error(message, status=400, fields=None):
    data = {"error": message}
    if fields:
        data["fields"] = fields
    return JsonResponse(data, status=status)
