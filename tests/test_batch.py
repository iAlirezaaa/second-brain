import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '15_SYSTEM' / 'scripts'))
from backend import batch, sources


class BatchTests(unittest.TestCase):
    def test_preview_apply_repeat_and_stale_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / 'note.txt'
            note.write_text('first data', encoding='utf-8')
            manifest = root / 'sources.json'
            manifest.write_text(json.dumps([{'path': 'note.txt', 'kind': 'document', 'origin': 'manual:1'}]), encoding='utf-8')
            preview = batch.run(root, manifest)
            self.assertFalse((root / sources.DATA).exists())
            note.write_text('changed data', encoding='utf-8')
            with self.assertRaises(ValueError):
                batch.run(root, manifest, True, preview['plan_id'])
            self.assertFalse((root / sources.DATA).exists())
            preview = batch.run(root, manifest)
            result = batch.run(root, manifest, True, preview['plan_id'])
            self.assertTrue(result['applied'])
            self.assertEqual(1, result['indexed'])
            self.assertEqual(1, len(sources.search(root, 'changed')))
            self.assertEqual(1, batch.run(root, manifest, True, preview['plan_id'])['indexed'])

    def test_invalid_manifest_does_not_import_any_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'good.txt').write_text('data', encoding='utf-8')
            manifest = root / 'sources.json'
            manifest.write_text(json.dumps([{'path': 'good.txt', 'kind': 'document', 'origin': 'manual'},
                                            {'path': 'missing.txt', 'kind': 'document', 'origin': 'missing'}]), encoding='utf-8')
            with self.assertRaises(OSError):
                batch.run(root, manifest)
            self.assertFalse((root / sources.DATA).exists())

    def test_failure_is_reported_and_index_not_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a.txt').write_text('a', encoding='utf-8')
            (root / 'b.txt').write_text('b', encoding='utf-8')
            manifest = root / 'sources.json'
            manifest.write_text(json.dumps([{'path': 'a.txt', 'kind': 'document', 'origin': 'a'},
                                            {'path': 'b.txt', 'kind': 'document', 'origin': 'b'}]), encoding='utf-8')
            plan = batch.run(root, manifest)
            real = sources.ingest_bytes
            def fail_second(root, raw, filename, *args):
                if filename == 'b.txt':
                    raise OSError('simulated disk failure')
                return real(root, raw, filename, *args)
            with patch.object(sources, 'ingest_bytes', side_effect=fail_second):
                result = batch.run(root, manifest, True, plan['plan_id'])
            self.assertFalse(result['applied'])
            self.assertEqual(1, len(result['imported']))
            self.assertIn('simulated disk failure', result['error'])
            self.assertFalse((root / sources.DATA / 'index.sqlite').exists())

    def test_cli_preview_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'note.txt').write_text('searchable', encoding='utf-8')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps([{'path': 'note.txt', 'kind': 'document', 'origin': 'local'}]), encoding='utf-8')
            cli = ROOT / '15_SYSTEM' / 'scripts' / 'sources.py'
            def run(*args):
                return subprocess.run([sys.executable, str(cli), '--root', str(root), *args],
                                      capture_output=True, text=True, check=True)
            plan = json.loads(run('batch', str(manifest)).stdout)
            result = json.loads(run('batch', str(manifest), '--apply', '--plan-id', plan['plan_id']).stdout)
            self.assertTrue(result['applied'])
            self.assertEqual('local', json.loads(run('search', 'searchable').stdout)[0]['origin'])
