from django.urls import path

from game import views


app_name = "game"

urlpatterns = [
    path("play/", views.play, name="play"),
    path("api/player/", views.player_view, name="player"),
]
