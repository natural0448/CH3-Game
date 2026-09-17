import json
import tempfile
import unittest
from pathlib import Path
from main import load_events


class ReplayLoaderTests(unittest.TestCase):
    def test_order_dedup_and_whitelist(self):
        row = dict(schema_version=1,event_id='a',event_type='player.moved',player_id=1,room_id='room-01',event_time='2026-09-16T00:00:00.000001+00:00',payload=dict(x=1,y=0,coins=0,version=1),secret='must not reach the browser')
        next_row = {**row,'event_id':'b','event_time':'2026-09-16T00:00:00.000002+00:00','payload':dict(x=2,y=0,coins=0,version=2)}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'events.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in [next_row,row,row]),encoding='utf-8')
            before=path.read_bytes(); data=load_events(path)
            self.assertEqual([r['event_id'] for r in data['events']],['a','b'])
            self.assertEqual(data['duplicate_count'],1)
            self.assertNotIn('secret',data['events'][0])
            self.assertEqual(before,path.read_bytes())
            path.write_text(json.dumps(row)+'\n'+json.dumps({**row,'payload':dict(x=9,y=0,coins=0,version=1)}),encoding='utf-8')
            with self.assertRaises(ValueError):load_events(path)
            path.write_text(json.dumps({**row,'payload':dict(x=20,y=0,coins=0,version=1)}),encoding='utf-8')
            with self.assertRaises(ValueError):load_events(path)


if __name__=='__main__':unittest.main()
