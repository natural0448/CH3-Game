import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from analytics.views import summary_view


class SummaryContractTests(SimpleTestCase):
    def test_file_and_api_match_without_launching_a_batch(self):
        summary = {
            "schema_version": 1, "generated_at": "2026-09-15T08:00:00+00:00",
            "source": "raw", "record_count": 3, "event_count": 3,
            "by_action": [{"event_type":"player.moved", "count":3}],
            "by_room": [{"room_id":"room-01", "count":2}, {"room_id":"room-02", "count":1}],
        }
        request = RequestFactory().get('/api/analytics/')
        request.user = SimpleNamespace(is_authenticated=True)
        with TemporaryDirectory() as directory, override_settings(DATA_DIR=Path(directory)):
            self.assertEqual(json.loads(summary_view(request).content), {
                "available": False, "reason": "summary_not_created"})
            target = Path(directory) / "marts" / "game-summary.json"
            target.parent.mkdir()
            target.write_text(json.dumps(summary), encoding='utf-8')
            with patch('subprocess.run') as run:
                self.assertEqual(json.loads(summary_view(request).content), {"available":True, **summary})
                run.assert_not_called()
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), summary)
        request.user = SimpleNamespace(is_authenticated=False)
        self.assertEqual(summary_view(request).status_code, 401)
