from django.shortcuts import render

# Create your views here.
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from game.transforms import ACTION_LABELS

@require_GET
def summary_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    path = settings.DATA_DIR / "marts" / "game-summary.json"
    if not path.exists():
        return JsonResponse({"available": False, "reason": "summary_not_created"})
    summary = json.loads(path.read_text(encoding="utf-8"))
    return JsonResponse({"available": True, **summary})


@login_required
def actions_snapshot(request):
    root = settings.DATA_DIR.parent / "data-replay" / "actions"
    summary_path = root / "marts" / "game-summary.json"
    manifest_path = root / "raw" / "game-events.manifest.json"
    if not summary_path.exists() or not manifest_path.exists():
        return JsonResponse({
            "available": False,
            "reason": "snapshot-or-summary-not-created",
            "source_topic": "game.actions.v1",
            "summary": None,
        })

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_action = [
        {
            "event_type": row["event_type"],
            "action_label": ACTION_LABELS.get(
                row["event_type"], row["event_type"]
            ),
            "count": row["count"],
        }
        for row in summary["by_action"]
    ]
    return JsonResponse({
        "available": True,
        "source_topic": manifest["topic"],
        "source_kind": "bounded-kafka-snapshot",
        "raw_record_count": manifest["record_count"],
        "bounds": manifest["bounds"],
        "label_source": "current-display-map",
        "summary": {
            "generated_at": summary["generated_at"],
            "event_count": summary["event_count"],
            "by_action": by_action,
            "by_room": summary["by_room"],
        },
    })