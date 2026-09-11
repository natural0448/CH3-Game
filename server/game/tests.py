from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse

from game.models import GameEvent, Player


User = get_user_model()
TEST_PASSWORD = "Only-for-the-isolated-test-database!"


class CreatePlayerCommandTests(TestCase):
    def test_repeat_preserves_password_room_and_game_state(self):
        output = StringIO()
        with patch("game.management.commands.create_player.getpass", return_value=TEST_PASSWORD):
            call_command("create_player", username="learner", stdout=output)

        player = Player.objects.get(user__username="learner")
        self.assertEqual((player.x, player.y, player.coins, player.version), (0, 0, 0, 0))
        player.x, player.y, player.coins, player.version = 5, 2, 9, 3
        player.save()
        previous_updated_at = player.updated_at

        with patch("game.management.commands.create_player.getpass") as password_prompt:
            call_command("create_player", username="learner", room="room-02", stdout=output)
            password_prompt.assert_not_called()

        player.refresh_from_db()
        self.assertEqual(Player.objects.filter(user=player.user).count(), 1)
        self.assertEqual((player.x, player.y, player.coins, player.version), (5, 2, 9, 3))
        self.assertEqual(player.room_id, "room-01")
        self.assertEqual(player.updated_at, previous_updated_at)
        self.assertTrue(player.user.check_password(TEST_PASSWORD))
        self.assertNotIn(TEST_PASSWORD, output.getvalue())

    def test_existing_user_receives_player_without_password_prompt(self):
        user = User.objects.create_user(username="existing", password=TEST_PASSWORD)
        with patch("game.management.commands.create_player.getpass") as password_prompt:
            call_command("create_player", username="existing", room="room-03", stdout=StringIO())
            password_prompt.assert_not_called()
        self.assertEqual(Player.objects.get(user=user).room_id, "room-03")
        user.refresh_from_db()
        self.assertTrue(user.check_password(TEST_PASSWORD))

    def test_empty_username_and_password_do_not_create_users(self):
        with self.assertRaises(CommandError):
            call_command("create_player", username="   ", stdout=StringIO())
        with patch("game.management.commands.create_player.getpass", return_value=""):
            with self.assertRaises(CommandError):
                call_command("create_player", username="empty-password", stdout=StringIO())
        self.assertFalse(User.objects.exists())
        self.assertFalse(Player.objects.exists())

    def test_full_room_rolls_back_the_new_user(self):
        User.objects.bulk_create([
            User(username=f"room-member-{index}", password="!") for index in range(20)
        ])
        Player.objects.bulk_create([
            Player(user=user, room_id="room-01") for user in User.objects.all()
        ])
        with patch("game.management.commands.create_player.getpass", return_value=TEST_PASSWORD):
            with self.assertRaisesMessage(CommandError, "20명"):
                call_command("create_player", username="extra-member", stdout=StringIO())
        self.assertFalse(User.objects.filter(username="extra-member").exists())
        self.assertEqual(Player.objects.filter(room_id="room-01").count(), 20)


class LoginAndPlayerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(username="alice", password=TEST_PASSWORD)
        cls.bob = User.objects.create_user(username="bob", password=TEST_PASSWORD)
        cls.alice_player = Player.objects.create(
            user=cls.alice, room_id="room-01", x=3, y=1, coins=2, version=4,
        )
        cls.bob_player = Player.objects.create(
            user=cls.bob, room_id="room-02", x=8, y=7, coins=20, version=9,
        )

    def test_anonymous_api_returns_json_and_play_redirects_to_login(self):
        response = self.client.get(reverse("game:player"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "login_required"})

        response = self.client.get(reverse("game:play"))
        self.assertEqual(response.status_code, 302)
        redirect = urlparse(response["Location"])
        self.assertEqual(redirect.path, reverse("login"))
        self.assertEqual(parse_qs(redirect.query)["next"], [reverse("game:play")])

    def test_two_sessions_only_read_their_own_unchanged_state(self):
        bob_client = Client()
        self.client.force_login(self.alice)
        bob_client.force_login(self.bob)
        for client, player, other in (
            (self.client, self.alice_player, self.bob_player),
            (bob_client, self.bob_player, self.alice_player),
        ):
            with self.subTest(player=player.pk):
                original = (player.x, player.y, player.coins, player.version, player.updated_at)
                first = client.get(reverse("game:player"), {"player_id": other.pk})
                second = client.get(reverse("game:player"))
                expected = {
                    "player_id": player.pk, "type": "state", "room_id": player.room_id,
                    "x": player.x, "y": player.y, "coins": player.coins, "version": player.version,
                }
                self.assertEqual(first.status_code, 200)
                self.assertEqual(first.json(), expected)
                self.assertEqual(second.json(), expected)
                player.refresh_from_db()
                self.assertEqual(
                    (player.x, player.y, player.coins, player.version, player.updated_at), original,
                )
        self.assertEqual(GameEvent.objects.count(), 0)

    def test_player_api_rejects_post_without_changing_state(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("game:player"), {"x": 99, "coins": 999})
        self.assertEqual(response.status_code, 405)
        self.alice_player.refresh_from_db()
        self.assertEqual((self.alice_player.x, self.alice_player.coins), (3, 2))
        self.assertFalse(GameEvent.objects.exists())

    def test_login_play_and_post_logout_with_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("login"), {"next": reverse("game:play")})
        self.assertContains(response, "작은 마을 입장")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'name="next"')

        response = client.post(reverse("login"), {
            "username": "alice", "password": TEST_PASSWORD,
            "next": reverse("game:play"),
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, reverse("game:play"), fetch_redirect_response=False)
        response = client.get(reverse("game:play"))
        self.assertContains(response, "마을 준비 중")
        self.assertContains(response, "alice")
        self.assertContains(response, "room-01")
        self.assertContains(response, "내 상태 조회")
        self.assertContains(response, f'href="{reverse("game:player")}"')
        self.assertContains(response, f'action="{reverse("logout")}"')

        self.assertEqual(client.get(reverse("logout")).status_code, 405)
        self.assertEqual(client.post(reverse("logout")).status_code, 403)
        response = client.post(reverse("logout"), {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertEqual(client.get(reverse("game:player")).status_code, 401)

    def test_play_displays_the_logged_in_players_room(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("game:play"))
        self.assertContains(response, "bob")
        self.assertContains(response, "room-02")
        self.assertNotContains(response, "room-01")

    def test_invalid_login_keeps_the_form_and_next_value(self):
        response = self.client.post(reverse("login"), {
            "username": "alice", "password": "incorrect-test-password",
            "next": reverse("game:player"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertContains(response, 'name="next" value="/api/player/"')
        self.assertNotContains(response, "incorrect-test-password")
        self.assertEqual(self.client.get(reverse("game:player")).status_code, 401)
