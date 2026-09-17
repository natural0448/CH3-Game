"""Local, read-only game replay. No Django, Kafka or third-party packages needed."""
import argparse
import hashlib
import json
import shutil
import webbrowser
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT.parent / 'data-replay/raw/game-events.jsonl'


def load_events(path):
    raw = path.read_bytes()
    events, seen = [], {}
    records = duplicates = ignored = 0
    for line_number, line in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        records += 1
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'Line {line_number}: expected an event object')
        if row.get('event_type') not in ('player.moved', 'player.gathered'):
            ignored += 1
            continue
        payload = row.get('payload', {})
        if not isinstance(payload, dict):
            raise ValueError(f'Line {line_number}: expected a payload object')
        if row.get('schema_version') != 1:
            raise ValueError(f'Line {line_number}: unsupported schema_version')
        for key in ('event_id', 'room_id', 'event_time'):
            if not isinstance(row.get(key), str) or not row[key] or not row[key].isprintable():
                raise ValueError(f'Line {line_number}: invalid {key}')
        if type(row.get('player_id')) is not int or row['player_id'] <= 0:
            raise ValueError(f'Line {line_number}: invalid player_id')
        for key in ('x', 'y', 'coins', 'version'):
            if type(payload.get(key)) is not int or payload[key] < 0:
                raise ValueError(f'Line {line_number}: invalid payload.{key}')
        if payload['x'] >= 20 or payload['y'] >= 15:
            raise ValueError(f'Line {line_number}: position is outside 20 x 15 map')
        moment = datetime.fromisoformat(row['event_time'])
        if moment.tzinfo is None:
            raise ValueError(f'Line {line_number}: event_time must include a timezone')
        event = {key:row[key] for key in ('event_id', 'event_type', 'player_id', 'room_id', 'event_time')}
        event.update({key:payload[key] for key in ('x', 'y', 'coins', 'version')})
        elapsed = moment.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        event['timestamp_us'] = (elapsed.days * 86400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds
        # Kafka metadata is evidence only; it never drives movement or coin calculations.
        event.update(partition=row.get('kafka_partition'), offset=row.get('kafka_offset'))
        signature = {key:value for key,value in event.items() if key not in ('partition','offset')}
        if event['event_id'] in seen:
            if seen[event['event_id']] != signature:
                raise ValueError(f'Line {line_number}: conflicting repeated event_id')
            duplicates += 1
            continue
        seen[event['event_id']] = signature
        events.append(event)
    events.sort(key=lambda r:(r['timestamp_us'],r['player_id'],r['version'],r['event_id']))
    return dict(events=events, rooms=sorted({e['room_id'] for e in events}),
        source_name=path.name, source_path=str(path.resolve()), record_count=records,
        duplicate_count=duplicates, ignored_count=ignored,
        sha256=hashlib.sha256(raw).hexdigest(), built_at=datetime.now(timezone.utc).isoformat())


def build(source=DEFAULT_SOURCE):
    data = load_events(source)
    assets = ROOT / 'assets'
    assets.mkdir(exist_ok=True)
    original = ROOT.parent.parent / 'Game-client/assets'
    for name in ('grass.png','path.png','tree.png','house.png','hero.png','README.md'):
        asset = original / name
        if asset.exists():
            shutil.copy2(asset, assets / name)
    for name in ('town-License.txt', 'dungeon-License.txt'):
        license_path = original / 'sources' / name
        if license_path.exists():
            shutil.copy2(license_path, assets / name)
    # Local script works even when index.html is opened directly, without a web server.
    serialized = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    temporary = ROOT / 'data.js.tmp'
    temporary.write_text('window.REPLAY_DATA = ' + serialized + ';\n', encoding='utf-8')
    temporary.replace(ROOT / 'data.js')
    print(f"Replay ready: {len(data['events'])} events, {len(data['rooms'])} rooms. Source unchanged.")
    return data


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description='작은 마을 움직임 리플레이')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    try:
        build(args.source)
        if args.build_only:
            return 0
        with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
            url = f'http://127.0.0.1:{args.port}/'
            print(f'{url}\nStop with Ctrl+C. Django and Kafka are not required.')
            if args.open:
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print('\nReplay server stopped.')
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Replay could not start: {error}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
