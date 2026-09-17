from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.utils import timezone
from game.models import Player, GameEvent
from game.services import serialize_player, serialize_event


@require_GET
def delivery_dashboard(request):
    # Local classroom administration uses the connection address, not the Host header.
    if request.META.get("REMOTE_ADDR") not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        return HttpResponseForbidden("서버 관리 화면은 서버 PC에서만 열 수 있습니다.")
    events = GameEvent.objects.all()
    counts = events.aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(published_at__isnull=True)),
        sent=Count("pk", filter=Q(published_at__isnull=False)),
    )
    status = request.GET.get("status", "all")
    if status not in ("all", "pending", "sent"):
        status = "all"
    if status == "pending":
        events = events.filter(published_at__isnull=True)
    elif status == "sent":
        events = events.filter(published_at__isnull=False)
    rows = events.order_by("-event_time", "-event_id").values(
        "event_id", "event_type", "player_id", "room_id", "event_time", "published_at"
    )
    return render(request, "game/delivery_dashboard.html", {
        "counts": counts, "status": status,
        "page": Paginator(rows, 20).get_page(request.GET.get("page")),
        "checked_at": timezone.now(),
    })

@require_GET
def player_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    player = Player.objects.get(user=request.user)
    return JsonResponse(serialize_player(player))

@login_required
def play(request):
    return render(request, "game/play.html")


@require_GET
def history(request):
    """인증된 계정의 최근 20개 사실만 읽는다. 게임 상태는 변경하지 않는다."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    events = GameEvent.objects.filter(player__user=request.user).order_by(
        "-event_time", "-event_id"
    )[:20]
    return JsonResponse({
        "scope": "current-player", "limit": 20,
        "events": [serialize_event(event) for event in events],
    })

@require_GET
def delivery_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    events = GameEvent.objects.filter(player__user=request.user)
    return JsonResponse({
        "source": "mysql-outbox",
        "event_count": events.count(),
        "pending_publish_count": events.filter(published_at__isnull=True).count(),
    })
