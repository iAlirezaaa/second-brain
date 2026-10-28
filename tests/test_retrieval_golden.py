import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '15_SYSTEM' / 'scripts'))
from backend import sources, retrieval_eval


def previous_search(root, query, limit=10):
    with closing(sqlite3.connect(str(root / sources.DATA / 'index.sqlite'))) as db:
        rows = db.execute('SELECT id, kind, origin, filename, imported_at, body FROM sources '
                          'WHERE instr(lower(body), lower(?)) > 0 ORDER BY imported_at DESC LIMIT ?',
                          (query, limit)).fetchall()
    return [dict(zip(('id', 'kind', 'origin', 'filename', 'imported_at', 'text'), row)) for row in rows]


class GoldenRetrieval(unittest.TestCase):
    def test_ranked_retrieval_beats_prior_search_on_small_fixture(self):
        fixture = json.loads((ROOT / 'tests' / 'fixtures' / 'retrieval-golden.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ids = {}
            for doc in fixture['documents']:
                f = root / (doc['name'] + '.txt')
                f.write_text(doc['text'], encoding='utf-8')
                ids[doc['name']] = sources.ingest(root, f, 'document', 'fixture:' + doc['name'])['id']
            sources.rebuild(root)
            cases = [{'query': item['query'], 'expected_ids': [ids[item['expected']]]} for item in fixture['cases']]
            with patch.object(sources, 'search', side_effect=previous_search):
                baseline = retrieval_eval.run(root, cases, limit=1)
            candidate = retrieval_eval.run(root, cases, limit=1)
            comparison = retrieval_eval.compare(baseline, candidate)
            self.assertEqual('improved', comparison['verdict'])
            self.assertEqual(0.5, baseline['mean_recall'])
            self.assertEqual(1.0, candidate['mean_recall'])
            self.assertGreater(candidate['mean_reciprocal_rank'], baseline['mean_reciprocal_rank'])
