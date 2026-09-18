import json
from copy import deepcopy
from django.test import SimpleTestCase
from game.transforms import parse_game_event, is_game_action, with_action_label


class TransformTests(SimpleTestCase):
    def fixture(self, event_type="player.trained"):
        return {
            "schema_version": 1,
            "event_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "event_type": event_type,
            "player_id": 7,
            "room_id": "room-test",
            "event_time": "2026-09-11T01:00:00+00:00",
            "payload": {
                "command_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "x": 3,
                "y": 2,
                "coins": 5,
                "version": 9,
                "transition": {
                    "episode_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                    "step": 1,
                    "observation": {"x": 3, "y": 2, "coins": 4},
                    "action": {"type": "train"},
                    "reward": 1,
                    "next_observation": {"x": 3, "y": 2, "coins": 5},
                    "done": False,
                    "terminated": False,
                    "truncated": False,
                    "policy_version": "manual-v1",
                },
            },
        }

    def test_reads_utf8_envelope(self):
        original = self.fixture()
        wire = json.dumps(original, ensure_ascii=False).encode("utf-8")
        self.assertEqual(parse_game_event(wire), original)

    def test_selects_three_action_types(self):
        for event_type in ("player.moved", "player.gathered", "player.trained"):
            self.assertTrue(is_game_action({"event_type": event_type}))
        self.assertFalse(is_game_action({"event_type": "system.notice"}))

    def test_adds_label_without_changing_fact(self):
        original = self.fixture()
        saved_original = deepcopy(original)
        result = with_action_label(original)
        self.assertEqual(original, saved_original)
        self.assertEqual(result["event_id"], original["event_id"])
        self.assertEqual(result["event_time"], original["event_time"])
        self.assertEqual(result["payload"]["transition"],original["payload"]["transition"],)
        self.assertEqual(result["payload"]["action_label"], "개인 수련")
        result["payload"].pop("action_label")
        self.assertEqual(result, original)

    def test_old_event_without_transition_keeps_original_fields(self):
        original = self.fixture()
        original["payload"].pop("transition")
        result = with_action_label(original)
        self.assertNotIn("transition", result["payload"])
        self.assertEqual(result["payload"]["coins"], original["payload"]["coins"])