from getpass import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from game.models import Player


class Command(BaseCommand):
    help = "수업용 사용자를 만들고 기존 플레이 상태는 보존합니다."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--room", default="room-01")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username:
            raise CommandError("사용자 이름을 입력하세요.")
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        if created:
            password = getpass("새 계정 비밀번호: ")
            if not password:
                raise CommandError("빈 비밀번호는 사용할 수 없습니다.")
            user.set_password(password)
            user.save(update_fields=["password"])
        room = options["room"]
        if not Player.objects.filter(user=user).exists() and Player.objects.filter(room_id=room).count() >= 20:
            raise CommandError("이 방은 20명입니다. 다른 --room을 사용하세요.")
        player, player_created = Player.objects.get_or_create(user=user, defaults={"room_id": room})
        self.stdout.write(
            f"username={username} player_id={player.pk} "
            f"created={player_created} position=({player.x},{player.y}) "
            f"coins={player.coins} room={player.room_id} version={player.version}"
        )