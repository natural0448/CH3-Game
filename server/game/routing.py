from django.urls import path
from game.consumers import PlayConsumer
websocket_urlpatterns = [path("ws/play/", PlayConsumer.as_asgi())]