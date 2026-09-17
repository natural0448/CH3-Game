from django.urls import path

from game import auth_views, views


app_name = "game"

urlpatterns = [
    path("", views.delivery_dashboard, name="delivery-dashboard"),
    path("api/auth/csrf/", auth_views.csrf_token, name="csrf"),
    path("api/auth/login/", auth_views.login_view, name="login"),
    path("api/auth/logout/", auth_views.logout_view, name="logout"),
    path("play/", views.play, name="play"),
    path("api/player/", views.player_view, name="player"),
    path("api/delivery/", views.delivery_view, name="delivery"),
    path("api/history/", views.history, name="history"),
]
