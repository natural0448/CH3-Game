import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from game.models import GameEvent, Player
from game.services import serialize_event


class ExportGameEventsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="export-test")
        self.player = Player.objects.create(user=user)

    def test_exports_all_rows_across_chunks_and_preserves_database(self):
        now = timezone.now()
        GameEvent.objects.bulk_create([
            GameEvent(player=self.player, event_type="player.moved", room_id="room-01",
                      event_time=now, published_at=now if i % 2 else None,
                      payload={"version":i, "note":"한글"}) for i in range(501)
        ])
        rows = list(GameEvent.objects.order_by("event_time", "event_id"))
        expected = [serialize_event(row) for row in rows]
        before = list(GameEvent.objects.order_by("event_id").values())
        with TemporaryDirectory() as directory, override_settings(DATA_DIR=Path(directory)):
            output = StringIO()
            call_command("export_game_events", stdout=output)
            target = Path(directory) / "raw" / "game-events.jsonl"
            content = target.read_text(encoding="utf-8")
            self.assertEqual([json.loads(line) for line in content.splitlines()], expected)
            self.assertIn("한글", content)
            self.assertIn("events=501", output.getvalue())
            self.assertFalse(target.with_suffix(".jsonl.tmp").exists())
            call_command("export_game_events", stdout=StringIO())
            self.assertEqual(target.read_text(encoding="utf-8"), content)
        self.assertEqual(list(GameEvent.objects.order_by("event_id").values()), before)
        self.player.refresh_from_db()
        self.assertEqual((self.player.x, self.player.y, self.player.coins, self.player.version), (0, 0, 0, 0))

    def test_failed_export_keeps_previous_snapshot(self):
        GameEvent.objects.create(player=self.player, event_type="player.moved", room_id="room-01",
                                 event_time=timezone.now(), payload={})
        with TemporaryDirectory() as directory, override_settings(DATA_DIR=Path(directory)):
            target = Path(directory) / "raw" / "game-events.jsonl"
            target.parent.mkdir()
            target.write_text("previous snapshot\n", encoding="utf-8")
            with patch("game.management.commands.export_game_events.serialize_event", side_effect=ValueError("test failure")):
                with self.assertRaisesMessage(ValueError, "test failure"):
                    call_command("export_game_events", stdout=StringIO())
            self.assertEqual(target.read_text(encoding="utf-8"), "previous snapshot\n")
            self.assertFalse(target.with_suffix(".jsonl.tmp").exists())
