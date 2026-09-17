"""6교시: 성공 행동의 전후 상태와 5행 묶음 계약을 검증한다."""
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from game.models import GameEvent, Player
from game.services import apply_command, serialize_event


class TransitionTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="transition-test")
        self.player = Player.objects.create(user=user, room_id="room-13-train")

    def act(self, action, **fields):
        command = {"type": action, "command_id": str(uuid4()), **fields}
        state = apply_command(self.player.user_id, command)
        event = GameEvent.objects.get(player=self.player, payload__command_id=command["command_id"])
        return command, state, event

    def test_five_moves_then_train_and_duplicate(self):
        previous = {"x": 0, "y": 0, "coins": 0}
        episode_id = None
        for step, direction in enumerate(["right", "right", "right", "down", "down"], 1):
            _, state, event = self.act("move", direction=direction)
            transition = event.payload["transition"]
            episode_id = episode_id or transition["episode_id"]
            UUID(episode_id)
            self.assertEqual(transition["episode_id"], episode_id)
            self.assertEqual(transition["step"], step)
            self.assertEqual(transition["observation"], previous)
            self.assertEqual(transition["action"], {"type": "move", "direction": direction})
            self.assertEqual(transition["reward"], 0)
            self.assertEqual(transition["done"], step == 5)
            self.assertEqual(transition["truncated"], step == 5)
            self.assertFalse(transition["terminated"])
            self.assertEqual(transition["policy_version"], "manual-v1")
            previous = {key: state[key] for key in ("x", "y", "coins")}
            self.assertEqual(transition["next_observation"], previous)

        # 클라이언트가 보낸 보상/좌표를 신뢰하지 않고 서버 규칙으로 계산한다.
        command, state, event = self.act("train", reward=999, next_observation={"coins": 999})
        transition = event.payload["transition"]
        self.assertEqual(event.event_type, "player.trained")
        self.assertEqual((state["x"], state["y"], state["coins"], state["version"]), (3, 2, 1, 6))
        self.assertNotEqual(transition["episode_id"], episode_id)
        self.assertEqual(transition["step"], 1)
        self.assertEqual(transition["observation"], previous)
        self.assertEqual(transition["next_observation"], {"x": 3, "y": 2, "coins": 1})
        self.assertEqual(transition["action"], {"type": "train"})
        self.assertEqual(transition["reward"], 1)
        self.assertFalse(transition["done"])
        self.assertEqual(serialize_event(event)["payload"]["transition"], transition)
        self.assertEqual(apply_command(self.player.user_id, command), state)
        self.assertEqual(GameEvent.objects.count(), 6)
        _, _, next_event = self.act("train")
        self.assertEqual(next_event.payload["transition"]["step"], 2)

    def test_gather_records_reward_and_before_after(self):
        for direction in ["right", "right", "down", "down"]:
            self.act("move", direction=direction)
        _, _, event = self.act("gather")
        transition = event.payload["transition"]
        self.assertEqual(event.event_type, "player.gathered")
        self.assertEqual(transition["observation"], {"x": 2, "y": 2, "coins": 0})
        self.assertEqual(transition["next_observation"], {"x": 2, "y": 2, "coins": 1})
        self.assertEqual(transition["reward"], 1)
        self.assertTrue(transition["truncated"])

    def test_failed_actions_leave_state_and_episode_unchanged(self):
        for action, fields, error in [
            ("train", {}, "not_at_train_tile"),
            ("gather", {}, "not_at_gather_tile"),
            ("move", {"direction": "left"}, "outside_map"),
            ("move", {"direction": "invalid"}, "invalid_direction"),
            ("invalid", {}, "unknown_action"),
        ]:
            with self.subTest(action=action, fields=fields):
                with self.assertRaisesMessage(ValueError, error):
                    self.act(action, **fields)
                self.player.refresh_from_db()
                self.assertEqual((self.player.x, self.player.y, self.player.coins, self.player.version), (0, 0, 0, 0))
                self.assertFalse(GameEvent.objects.exists())
        _, _, event = self.act("move", direction="right")
        self.assertEqual(event.payload["transition"]["step"], 1)

    def test_legacy_event_starts_new_episode_without_rewriting_history(self):
        legacy = GameEvent.objects.create(
            player=self.player, room_id=self.player.room_id, event_type="player.moved",
            event_time=timezone.now(), payload={"x": 0, "y": 0, "coins": 0, "version": 0},
        )
        _, _, event = self.act("move", direction="right")
        self.assertEqual(event.payload["transition"]["step"], 1)
        legacy.refresh_from_db()
        self.assertNotIn("transition", legacy.payload)
