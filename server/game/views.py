from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from game.models import Player
from game.services import serialize_player

@require_GET
def player_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login_required"}, status=401)
    player = Player.objects.get(user=request.user)
    return JsonResponse(serialize_player(player))

@login_required
def play(request):
    return render(request, "game/play.html")