from django.shortcuts import render

# Create your views here.
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def summary_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    path = settings.DATA_DIR / "marts" / "game-summary.json"
    if not path.exists():
        return JsonResponse({"available": False, "reason": "summary_not_created"})
    summary = json.loads(path.read_text(encoding="utf-8"))
    return JsonResponse({"available": True, **summary})