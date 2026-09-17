import json
import asyncio
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from kafka.errors import KafkaTimeoutError

from game.models import GameEvent, Player
from game.services import apply_command, serialize_event


class JsonAuthTests(TestCase):
    def setUp(self):
        self.password = " isolated test password with spaces "
        self.user = get_user_model().objects.create_user(username="json-alice", password=self.password)
        self.player = Player.objects.create(user=self.user)
        self.client = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')

    def csrf(self):
        return self.client.get('/api/auth/csrf/').json()['csrfToken']

    def test_dashboard_server_wide_logs_filters_and_pagination(self):
        self.assertContains(self.client.get('/'), '아직 이벤트가 없습니다.')
        now = timezone.now()
        GameEvent.objects.bulk_create([
            GameEvent(player=self.player, event_type='player.moved', room_id='room-01',
                      event_time=now, published_at=now if i < 2 else None,
                      payload={'private':'not-for-dashboard'}) for i in range(23)
        ])
        other_user = get_user_model().objects.create_user(username='dashboard-other')
        other = Player.objects.create(user=other_user)
        foreign_event = GameEvent.objects.create(player=other, event_type='player.moved',
                                                room_id='room-02', event_time=now, payload={})
        result = self.client.get('/', {'player_id':other.pk})
        self.assertEqual(result.context['counts'], {'total':24, 'pending':22, 'sent':2})
        self.assertEqual(len(result.context['page']), 20)
        all_rows = list(result.context['page']) + list(self.client.get('/?page=2').context['page'])
        self.assertIn(foreign_event.event_id, {row['event_id'] for row in all_rows})
        self.assertEqual({row['player_id'] for row in all_rows}, {self.player.pk, other.pk})
        self.assertContains(result, '모든 사용자 · 모든 방')
        self.assertNotContains(result, 'not-for-dashboard')
        self.assertEqual(len(self.client.get('/?page=2').context['page']), 4)
        sent = self.client.get('/?status=sent')
        self.assertEqual(len(sent.context['page']), 2)
        self.assertTrue(all(row['published_at'] for row in sent.context['page']))
        pending = self.client.get('/?status=pending&page=2')
        self.assertEqual(len(pending.context['page']), 2)
        self.assertTrue(all(row['published_at'] is None for row in pending.context['page']))
        self.assertEqual(self.client.get('/?status=unknown&page=invalid').context['status'], 'all')
        self.assertEqual(GameEvent.objects.count(), 24)

    def test_dashboard_only_allows_local_connections_without_login(self):
        for address in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
            self.assertEqual(self.client.get('/', REMOTE_ADDR=address).status_code, 200)
        self.assertEqual(self.client.get('/', REMOTE_ADDR='192.0.2.1',
                                         HTTP_X_FORWARDED_FOR='127.0.0.1').status_code, 403)
        self.assertEqual(self.client.get('/', REMOTE_ADDR='').status_code, 403)
        self.assertEqual(self.client.get('/api/player/').status_code, 401)
        self.assertEqual(self.client.get('/api/delivery/').status_code, 401)

    def test_delivery_counts_only_authenticated_users_events(self):
        self.assertEqual(self.client.get('/api/delivery/').status_code, 401)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/delivery/').json(), {
            'source':'mysql-outbox', 'event_count':0, 'pending_publish_count':0})
        other = get_user_model().objects.create_user(username='delivery-other')
        Player.objects.create(user=other)
        for user in (self.user, self.user, other):
            apply_command(user.pk, {'type':'move', 'direction':'right', 'command_id':str(uuid4())})
        event = GameEvent.objects.filter(player=self.player).first()
        event.published_at = event.event_time
        event.save(update_fields=['published_at'])
        response = self.client.get('/api/delivery/', {'player_id':other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'source':'mysql-outbox', 'event_count':2, 'pending_publish_count':1})
        self.assertEqual(GameEvent.objects.count(), 3)

    def post(self, data, token=None, origin='http://localhost'):
        return self.client.post('/api/auth/login/', data, content_type='application/json',
                                HTTP_X_CSRFTOKEN=token or self.csrf(), HTTP_ORIGIN=origin)

    def test_json_login_rotation_own_player_and_logout(self):
        old = self.csrf()
        result = self.post({'username': '  json-alice ', 'password': self.password}, old)
        self.assertEqual(result.json(), {'authenticated': True})
        fresh = self.csrf()
        self.assertNotEqual(old, fresh)
        response = self.client.get('/api/player/?player_id=999')
        self.assertEqual(response.json()['player_id'], self.player.pk)
        self.assertEqual(self.client.post('/api/auth/logout/', {}, content_type='application/json',
                                        HTTP_X_CSRFTOKEN=old, HTTP_ORIGIN='http://localhost').status_code, 403)
        self.assertEqual(self.client.post('/api/auth/logout/', {}, content_type='application/json',
                                        HTTP_X_CSRFTOKEN=fresh, HTTP_ORIGIN='http://localhost').json(), {'authenticated': False})
        self.assertEqual(self.client.get('/api/player/').status_code, 401)
        self.player.refresh_from_db()
        self.assertEqual(self.player.version, 0)
        self.assertFalse(GameEvent.objects.exists())

    def test_invalid_json_types_authentication_and_csrf_origin(self):
        for data in ('{', '[]', '{"username":3,"password":"x"}', '{"username":" ","password":"x"}'):
            with self.subTest(data=data):
                self.assertEqual(self.post(data).status_code, 400)
        self.assertEqual(self.post({'username':'json-alice','password':'incorrect'}).status_code, 401)
        self.assertEqual(self.post({'username':'json-alice','password':self.password}, origin='http://other.invalid').status_code, 403)
        self.assertEqual(self.client.post('/api/auth/login/', {}, content_type='application/json').status_code, 403)
        self.assertEqual(self.client.get('/api/auth/login/').status_code, 405)
        self.assertEqual(self.client.get('/api/auth/logout/').status_code, 405)


class EventDeliveryTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='event-user')
        self.player = Player.objects.create(user=user, x=2, y=2)
        self.command = {'type': 'gather', 'command_id': str(uuid4())}
        apply_command(user.pk, self.command)
        self.event = GameEvent.objects.get()

    def test_duplicate_command_does_not_repeat_reward_and_event(self):
        apply_command(self.player.user_id, self.command)
        self.player.refresh_from_db()
        self.assertEqual((self.player.coins, self.player.version), (1, 1))
        self.assertEqual(GameEvent.objects.count(), 1)
        with self.assertRaisesMessage(ValueError, 'outside_map'):
            self.player.x = 0
            self.player.save()
            apply_command(self.player.user_id, {'type':'move','direction':'left','command_id':str(uuid4())})
        self.assertEqual(GameEvent.objects.count(), 1)

    def test_export_preserves_fact_and_does_not_publish(self):
        envelope = serialize_event(self.event)
        self.assertEqual(envelope['schema_version'], 1)
        self.assertNotIn('published_at', envelope)
        with TemporaryDirectory() as directory, override_settings(DATA_DIR=Path(directory)):
            call_command('export_event_sample', stdout=StringIO())
            saved = json.loads((Path(directory)/'samples/game-event.json').read_text(encoding='utf-8'))
            self.assertEqual(saved, envelope)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.published_at)

    @patch('game.management.commands.publish_game_events.KafkaProducer')
    def test_publisher_waits_for_ack_before_db_mark_and_never_changes_player(self, factory):
        producer = factory.return_value
        def ack(timeout):
            self.event.refresh_from_db()
            self.assertIsNone(self.event.published_at)
            return SimpleNamespace(partition=1, offset=7)
        producer.send.return_value.get.side_effect = ack
        call_command('publish_game_events', once=True, stdout=StringIO())
        self.event.refresh_from_db()
        self.assertIsNotNone(self.event.published_at)
        self.assertEqual(producer.send.call_args.kwargs['value'], serialize_event(self.event))
        self.assertEqual(producer.send.call_args.kwargs['key'], self.player.pk)
        self.assertEqual(factory.call_args.kwargs['acks'], 'all')
        self.assertTrue(factory.call_args.kwargs['enable_idempotence'])
        self.player.refresh_from_db()
        self.assertEqual((self.player.coins, self.player.version), (1, 1))
        producer.send.reset_mock()
        call_command('publish_game_events', once=True, stdout=StringIO())
        producer.send.assert_not_called()

    @patch('game.management.commands.publish_game_events.KafkaProducer')
    def test_failed_ack_keeps_original_event_unpublished(self, factory):
        factory.return_value.send.return_value.get.side_effect = KafkaTimeoutError()
        with self.assertRaises(CommandError):
            call_command('publish_game_events', once=True, stdout=StringIO())
        self.event.refresh_from_db()
        self.assertIsNone(self.event.published_at)
        self.assertEqual(self.event.payload['command_id'], self.command['command_id'])
        factory.return_value.close.assert_called_once_with(timeout=10)

    @patch('game.management.commands.watch_game_events.KafkaConsumer')
    def test_watch_prints_then_commits_complete_batch(self, factory):
        consumer = factory.return_value
        record = SimpleNamespace(value=serialize_event(self.event), key=str(self.player.pk),
                                 topic='game.events.v1', partition=1, offset=7)
        consumer.poll.return_value = {1: [record]}
        output = StringIO()
        def committed():
            self.assertIn(str(self.event.pk), output.getvalue())
            self.assertIn('room_id', output.getvalue())
        consumer.commit.side_effect = committed
        call_command('watch_game_events', limit=1, stdout=output)
        consumer.poll.assert_called_once_with(timeout_ms=2000, max_records=1)
        consumer.commit.assert_called_once()
        consumer.close.assert_called_once_with(autocommit=False)
        self.assertFalse(factory.call_args.kwargs['enable_auto_commit'])
        self.assertEqual(GameEvent.objects.count(), 1)

    @patch('game.management.commands.watch_game_events.KafkaConsumer')
    def test_watch_does_not_commit_incomplete_output(self, factory):
        consumer = factory.return_value
        consumer.poll.return_value = {1:[SimpleNamespace(value={}, key='1', topic='game.events.v1',partition=0,offset=0)]}
        with self.assertRaises(CommandError):
            call_command('watch_game_events', limit=1, stdout=StringIO())
        consumer.commit.assert_not_called()
        consumer.close.assert_called_once_with(autocommit=False)

    def test_invalid_limits_fail_before_network(self):
        for command, kwargs in [('publish_game_events', {'batch_size':0}), ('watch_game_events', {'limit':0})]:
            with self.assertRaises(CommandError):
                call_command(command, stdout=StringIO(), **kwargs)


class WebsocketContractTests(TransactionTestCase):
    def test_two_room_members_receive_join_move_and_departure(self):
        from config.asgi import application
        from game.consumers import ONLINE
        players, cookies = [], []
        for name, room in [('room-a','room-01'),('room-b','room-01'),('room-c','room-02')]:
            user = get_user_model().objects.create_user(username=name)
            players.append(Player.objects.create(user=user,room_id=room))
            client = Client()
            client.force_login(user)
            cookies.append(f"sessionid={client.cookies['sessionid'].value}".encode())

        async def exercise():
            sockets = [WebsocketCommunicator(application,'/ws/play/',headers=[
                (b'origin',b'http://localhost'),(b'cookie',cookie)]) for cookie in cookies]
            opened = []
            try:
                a,b,c = sockets
                self.assertTrue((await a.connect())[0]); opened.append(a)
                self.assertEqual((await a.receive_json_from())['player_id'],players[0].pk)
                self.assertEqual(len((await a.receive_json_from())['players']),1)
                self.assertTrue((await b.connect())[0]); opened.append(b)
                self.assertEqual((await b.receive_json_from())['player_id'],players[1].pk)
                for ws in (a,b):
                    snapshot = await ws.receive_json_from()
                    self.assertEqual({p['player_id'] for p in snapshot['players']},{players[0].pk,players[1].pk})
                self.assertTrue((await c.connect())[0]); opened.append(c)
                await c.receive_json_from()
                self.assertEqual([p['player_id'] for p in (await c.receive_json_from())['players']],[players[2].pk])
                duplicate = WebsocketCommunicator(application,'/ws/play/',headers=[
                    (b'origin',b'http://localhost'),(b'cookie',cookies[0])])
                self.assertEqual(await duplicate.connect(),(False,4409))
                await duplicate.disconnect()
                command_id = str(uuid4())
                await a.send_json_to({'type':'move','direction':'right','command_id':command_id})
                mine,peer = await a.receive_json_from(),await b.receive_json_from()
                self.assertEqual(mine,peer)
                self.assertEqual((peer['player_id'],peer['x'],peer['command_id']),(players[0].pk,1,command_id))
                self.assertTrue(await c.receive_nothing(timeout=.05))
                await b.disconnect(); opened.remove(b)
                self.assertEqual([p['player_id'] for p in (await a.receive_json_from())['players']],[players[0].pk])
            finally:
                for ws in reversed(opened):
                    await ws.disconnect()
        async_to_sync(exercise)()
        self.assertFalse(ONLINE)
        self.assertEqual(Player.objects.count(),3)
        self.assertEqual(GameEvent.objects.count(),1)

    def test_session_origin_initial_state_and_commands(self):
        from config.asgi import application
        user = get_user_model().objects.create_user(username='ws-user')
        player = Player.objects.create(user=user, x=2, y=2)
        client = Client()
        client.force_login(user)
        cookie = f"sessionid={client.cookies['sessionid'].value}".encode()
        command_id = str(uuid4())

        async def exercise():
            denied = WebsocketCommunicator(application, '/ws/play/', headers=[(b'origin', b'http://untrusted.invalid')])
            self.assertFalse((await denied.connect())[0])
            await denied.disconnect()
            anonymous = WebsocketCommunicator(application, '/ws/play/', headers=[(b'origin', b'http://localhost')])
            self.assertEqual(await anonymous.connect(), (False, 4401))
            await anonymous.disconnect()
            ws = WebsocketCommunicator(application, '/ws/play/', headers=[(b'origin', b'http://localhost'),(b'cookie',cookie)])
            self.assertTrue((await ws.connect())[0])
            first = await ws.receive_json_from()
            self.assertEqual(first['player_id'], player.pk)
            self.assertNotIn('command_id', first)
            snapshot = await ws.receive_json_from()
            self.assertEqual(snapshot['type'], 'snapshot')
            self.assertEqual([p['player_id'] for p in snapshot['players']], [player.pk])
            command = {'type':'move','direction':'right','command_id':command_id}
            await ws.send_json_to(command)
            moved = await ws.receive_json_from()
            self.assertEqual((moved['x'],moved['version'],moved['command_id']), (3,1,command_id))
            await asyncio.sleep(.21)
            await ws.send_json_to(command)
            self.assertEqual(await ws.receive_json_from(), moved)
            await asyncio.sleep(.21)
            error_id = str(uuid4())
            await ws.send_json_to({'type':'gather','command_id':error_id})
            self.assertEqual(await ws.receive_json_from(), {'type':'error','code':'not_at_gather_tile','command_id':error_id})
            await ws.disconnect()
        async_to_sync(exercise)()
        player.refresh_from_db()
        self.assertEqual((player.x,player.coins,player.version),(3,0,1))
        self.assertEqual(GameEvent.objects.count(),1)
