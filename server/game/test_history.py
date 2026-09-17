"""개인 이력 API의 소유권, 조회 제한, 읽기 전용 계약."""
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from game.models import GameEvent, Player
from game.services import apply_command


class HistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="history-owner")
        self.other = get_user_model().objects.create_user(username="history-other")
        self.player = Player.objects.create(user=self.user)
        self.other_player = Player.objects.create(user=self.other)

    def test_login_required_get_only_and_empty_history(self):
        self.assertEqual(self.client.get("/api/history/").status_code, 401)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/history/").json(), {
            "scope": "current-player", "limit": 20, "events": [],
        })
        self.assertEqual(self.client.post("/api/history/").status_code, 405)

    def test_own_latest_twenty_even_with_foreign_player_query(self):
        now = timezone.now()
        GameEvent.objects.bulk_create([
            GameEvent(player=self.player, room_id="room-01", event_type="player.moved",
                      event_time=now + timedelta(seconds=index),
                      payload={"x": 0, "y": 0, "coins": 0, "version": index})
            for index in range(25)
        ])
        GameEvent.objects.create(player=self.other_player, room_id="room-01",
                                 event_type="player.moved", event_time=now + timedelta(days=1), payload={})
        self.client.force_login(self.user)
        response = self.client.get("/api/history/", {"player_id": self.other_player.pk})
        events = response.json()["events"]
        self.assertEqual(len(events), 20)
        self.assertEqual({event["player_id"] for event in events}, {self.player.pk})
        self.assertEqual([event["payload"]["version"] for event in events], list(range(24, 4, -1)))
        self.assertNotIn("transition", events[0]["payload"])
        self.assertNotIn("username", events[0])
        self.assertEqual(GameEvent.objects.count(), 26)
        self.player.refresh_from_db()
        self.assertEqual((self.player.x, self.player.coins, self.player.version), (0, 0, 0))
        self.client.force_login(self.other)
        self.assertEqual(len(self.client.get("/api/history/").json()["events"]), 1)

    def test_train_transition_is_returned_with_same_event_id(self):
        for direction in ["right", "right", "right", "down", "down"]:
            apply_command(self.user.pk, {"type": "move", "direction": direction, "command_id": str(uuid4())})
        state = apply_command(self.user.pk, {"type": "train", "command_id": str(uuid4())})
        event = GameEvent.objects.get(player=self.player, event_type="player.trained")
        self.client.force_login(self.user)
        row = self.client.get("/api/history/").json()["events"][0]
        self.assertEqual(row["event_id"], str(event.event_id))
        self.assertEqual(row["payload"]["transition"]["reward"], 1)
        self.assertEqual(row["payload"]["transition"]["step"], 1)
        self.assertEqual(row["payload"]["coins"], state["coins"])
