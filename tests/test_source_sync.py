import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '15_SYSTEM' / 'scripts'))
from backend import sources, source_sync, learning


class TransferTests(unittest.TestCase):
    def test_preview_copy_idempotency_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a, b = base / 'a', base / 'b'
            f = base / 'doc.txt'
            f.write_text('first version', encoding='utf-8')
            one = sources.ingest(a, f, 'document', 'manual:one')
            preview = source_sync.transfer(a / sources.DATA, b / sources.DATA)
            self.assertEqual([one['id']], preview['new'])
            self.assertFalse((b / sources.DATA).exists())
            source_sync.transfer(a / sources.DATA, b / sources.DATA, apply=True)
            self.assertEqual(1, source_sync.transfer(a / sources.DATA, b / sources.DATA)['already_present'])
            self.assertEqual(1, sources.rebuild(b))
            f.write_text('second version', encoding='utf-8')
            two = sources.ingest(a, f, 'document', 'manual:one')
            self.assertEqual(two['id'], source_sync.transfer(a / sources.DATA, b / sources.DATA)['conflicts'][0]['incoming'])
            with self.assertRaises(ValueError):
                source_sync.transfer(a / sources.DATA, b / sources.DATA, apply=True)
            source_sync.transfer(a / sources.DATA, b / sources.DATA, apply=True, allow_conflicts=True)
            self.assertEqual(2, sources.rebuild(b))
            self.assertEqual(1, len(sources.search(b, 'first')))
            self.assertEqual(1, len(sources.search(b, 'second')))

    def test_corruption_fails_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            file = base / 'note.txt'
            file.write_text('original', encoding='utf-8')
            record = sources.ingest(base / 'a', file, 'document', 'manual')
            (base / 'a' / sources.DATA / 'sources' / record['id'] / 'raw.txt').write_text('tampered', encoding='utf-8')
            with self.assertRaises(ValueError):
                source_sync.transfer(base / 'a' / sources.DATA, base / 'b' / sources.DATA, apply=True)
            self.assertFalse((base / 'b' / sources.DATA).exists())

    def test_missing_source_is_not_a_successful_empty_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaises(ValueError):
                source_sync.transfer(base / 'missing', base / 'destination', apply=True)
            self.assertFalse((base / 'destination').exists())

    def test_transfer_refuses_hidden_incomplete_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            directory = base / 'a' / sources.DATA / 'sources' / '.incomplete'
            directory.mkdir(parents=True)
            (directory / 'raw.txt').write_text('partial', encoding='utf-8')
            with self.assertRaises((ValueError, OSError)):
                source_sync.transfer(base / 'a' / sources.DATA, base / 'b' / sources.DATA, apply=True)
            self.assertFalse((base / 'b' / sources.DATA).exists())

    def test_lesson_transfer_requires_explicit_approval_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a, b = base / 'a', base / 'b'
            f = base / 'source.txt'
            f.write_text('evidence is here', encoding='utf-8')
            source = sources.ingest(a, f, 'document', 'manual')
            sources.rebuild(a)
            proposal = learning.propose(a, source['id'], 'evidence', 'lesson from evidence', 'evidence')
            learning.approve(a, proposal['id'], approved=True)
            preview = source_sync.transfer(a / sources.DATA, b / sources.DATA)
            self.assertEqual([proposal['id']], preview['new_proposals'])
            self.assertEqual([proposal['id']], preview['new_approvals'])
            source_sync.transfer(a / sources.DATA, b / sources.DATA, apply=True)
            self.assertEqual([], learning.recall(b, 'lesson'))
            self.assertFalse(source_sync.verify_copy(a / sources.DATA, b / sources.DATA)['verified'])
            source_sync.transfer(a / sources.DATA, b / sources.DATA, apply=True, include_approvals=True)
            self.assertEqual('manual', learning.recall(b, 'lesson')[0]['origin'])
            self.assertTrue(source_sync.verify_copy(a / sources.DATA, b / sources.DATA)['verified'])
            with self.assertRaises(ValueError):
                source_sync.verify_copy(a / sources.DATA, a / sources.DATA)

    def test_invalid_proposal_stops_transfer_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a, b = base / 'a', base / 'b'
            f = base / 'source.txt'
            f.write_text('evidence', encoding='utf-8')
            source = sources.ingest(a, f, 'document', 'manual')
            proposal = learning.propose(a, source['id'], 'evidence', 'lesson', 'evidence')
            learning._proposal_path(a, proposal['id']).write_text('{}', encoding='utf-8')
            with self.assertRaises((ValueError, KeyError)):
                source_sync.transfer(a / sources.DATA, b / sources.DATA, apply=True)
            self.assertFalse((b / sources.DATA).exists())

    def test_invalid_receipt_is_not_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a, b = base / 'a', base / 'b'
            f = base / 'source.txt'
            f.write_text('evidence', encoding='utf-8')
            source = sources.ingest(a, f, 'document', 'manual')
            sources.rebuild(a)
            proposal = learning.propose(a, source['id'], 'evidence', 'lesson', 'evidence')
            learning.approve(a, proposal['id'], approved=True)
            path = a / sources.DATA / 'learning' / 'approved' / (proposal['id'] + '.json')
            receipt = json.loads(path.read_text(encoding='utf-8'))
            receipt['evaluation']['passed'] = False
            path.write_text(json.dumps(receipt), encoding='utf-8')
            with self.assertRaises(ValueError):
                source_sync.transfer(a / sources.DATA, b / sources.DATA, apply=True, include_approvals=True)
            self.assertFalse((b / sources.DATA).exists())
