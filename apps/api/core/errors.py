from django.http import JsonResponse
from rest_framework.views import exception_handler


def handler(exc, context):
    result = exception_handler(exc, context)
    if result is None:
        return JsonResponse({"error": "service_unavailable"}, status=503)
    result.data = {"error": "request_rejected", "details": result.data}
    return result


def csrf_failure(request, reason=""):
    return JsonResponse({"error": "csrf_rejected"}, status=403)
