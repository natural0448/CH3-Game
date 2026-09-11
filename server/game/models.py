import uuid

from django.conf import settings
from django.db import models


class Player(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room_id = models.CharField(max_length=32, default="room-01")
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    coins = models.IntegerField(default=0)
    version = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_username()

    
class GameEvent(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=40)
    player = models.ForeignKey(Player, on_delete=models.PROTECT)
    room_id = models.CharField(max_length=32)
    event_time = models.DateTimeField()
    payload = models.JSONField()
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at", "event_time"])]