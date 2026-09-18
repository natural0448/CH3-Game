import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, override_settings
from analytics.ingest_views import ingest_summary_view


class IngestViewTests(SimpleTestCase):
    def request(self, authenticated=True):
        request = RequestFactory().get("/api/analytics/ingest/")
        request.user = SimpleNamespace(is_authenticated=authenticated)
        return request

    def test_login_required(self):
        response = ingest_summary_view(self.request(False))
        self.assertEqual(response.status_code, 401)

    def test_missing_summary_is_not_zero(self):
        with TemporaryDirectory() as directory:
            with override_settings(DATA_DIR=Path(directory)):
                response = ingest_summary_view(self.request())
        result = json.loads(response.content)
        self.assertFalse(result["available"])
        self.assertNotIn("event_count", result)

    def test_existing_summary_is_projected(self):
        fixture = {
            "schema_version": 1, "source": "kafka-parquet",
            "generated_at": "2026-09-11T01:00:00+00:00",
            "record_count": 3, "valid_record_count": 3,
            "invalid_record_count": 0, "unsupported_record_count": 0,
            "event_count": 2, "duplicate_record_count": 1,
            "by_action": [{"event_type": "player.moved", "count": 2}],
            "by_room": [{"room_id": "room-01", "count": 2}],
        }
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            target = data_dir / "marts" / "stream-summary.json"
            target.parent.mkdir()
            target.write_text(json.dumps(fixture), encoding="utf-8")
            with override_settings(DATA_DIR=data_dir):
                response = ingest_summary_view(self.request())
        result = json.loads(response.content)
        self.assertTrue(result["available"])
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(response["Cache-Control"], "no-store")