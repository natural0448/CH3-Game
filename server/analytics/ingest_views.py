import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET


COUNT_FIELDS = (
    "record_count", "valid_record_count", "invalid_record_count",
    "unsupported_record_count", "event_count", "duplicate_record_count",
)


@require_GET
def ingest_summary_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    target = settings.DATA_DIR / "marts" / "stream-summary.json"
    if not target.is_file():
        return JsonResponse({
            "available": False, "reason": "ingest_summary_not_created"
        })
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("summary must be an object")
        if document.get("schema_version") != 1:
            raise ValueError("unsupported summary schema")
        if document.get("source") != "kafka-parquet":
            raise ValueError("unexpected summary source")
        for field in COUNT_FIELDS:
            value = document[field]
            if type(value) is not int or value < 0:
                raise ValueError(f"invalid count: {field}")
        response = JsonResponse({"available": True, **document})
        response["Cache-Control"] = "no-store"
        return response
    except (OSError, ValueError, KeyError, TypeError):
        return JsonResponse({
            "available": False, "reason": "ingest_summary_unreadable"
        }, status=503)