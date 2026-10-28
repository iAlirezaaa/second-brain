import json
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '15_SYSTEM' / 'scripts'))
from backend import learning, sources, retrieval_eval
import mcp_server


class LearningTests(unittest.TestCase):
    def test_source_to_proposal_evaluation_approval_and_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / 'chat.txt'
            f.write_text('A useful observation: restore backups regularly.', encoding='utf-8')
            source = sources.ingest(root, f, 'conversation', 'chat:example')
            sources.rebuild(root)
            args = {'source_id': source['id'], 'quote': 'restore backups regularly',
                    'lesson': 'Test restore procedures regularly', 'query': 'restore backups'}
            answer = mcp_server.handle_tool_call(root, {'name': 'lesson_propose', 'arguments': args})
            proposal = json.loads(answer['content'][0]['text'])
            self.assertEqual([], learning.recall(root, 'restore'))
            self.assertTrue(learning.evaluate(root, proposal['id'])['passed'])
            with self.assertRaises(ValueError):
                learning.approve(root, proposal['id'])
            learning.approve(root, proposal['id'], approved=True)
            result = json.loads(mcp_server.handle_tool_call(root, {'name': 'lesson_recall',
                                'arguments': {'query': 'restore'}})['content'][0]['text'])
            self.assertEqual('chat:example', result[0]['origin'])
            self.assertEqual('restore backups regularly', result[0]['quote'])

    def test_bad_evidence_failed_evaluation_and_changed_record_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / 'note.txt'
            f.write_text('A source with exact evidence.', encoding='utf-8')
            source = sources.ingest(root, f, 'document', 'manual')
            sources.rebuild(root)
            with self.assertRaises(ValueError):
                learning.propose(root, source['id'], 'invented quote', 'claim', 'source')
            proposal = learning.propose(root, source['id'], 'exact evidence', 'claim', 'missing query')
            self.assertFalse(learning.evaluate(root, proposal['id'])['passed'])
            with self.assertRaises(ValueError):
                learning.approve(root, proposal['id'], approved=True)
            raw = root / sources.DATA / 'sources' / source['id'] / 'raw.txt'
            raw.write_text('tampered', encoding='utf-8')
            with self.assertRaises(ValueError):
                learning.evaluate(root, proposal['id'])

    def test_retrieval_metrics_use_expected_ids_and_include_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / 'note.txt'
            f.write_text('unique searchable evidence', encoding='utf-8')
            source = sources.ingest(root, f, 'research', 'manual')
            sources.rebuild(root)
            cases = [{'query': 'searchable', 'expected_ids': [source['id']]},
                     {'query': 'absent', 'expected_ids': [source['id']]}]
            report = retrieval_eval.run(root, cases)
            self.assertEqual(0.5, report['mean_recall'])
            self.assertEqual(0.5, report['mean_reciprocal_rank'])
            self.assertEqual([], report['results'][1]['retrieved_ids'])
            self.assertEqual('unchanged', retrieval_eval.compare(report, copy.deepcopy(report))['verdict'])
            different = copy.deepcopy(report)
            different['corpus_sha256'] = 'different'
            with self.assertRaises(ValueError):
                retrieval_eval.compare(report, different)
            different = copy.deepcopy(report)
            different['results'][1]['recall'] = 1.0
            with self.assertRaises(ValueError):
                retrieval_eval.compare(report, different)
            changed_cases = [{'query': 'different', 'expected_ids': [source['id']]}]
            with self.assertRaises(ValueError):
                retrieval_eval.compare(report, retrieval_eval.run(root, changed_cases))
            with patch.object(sources, 'search', return_value=[]):
                worse = retrieval_eval.run(root, cases)
            self.assertEqual('regressed', retrieval_eval.compare(report, worse)['verdict'])
            self.assertEqual('improved', retrieval_eval.compare(worse, report)['verdict'])
            baseline_path, candidate_path = root / 'baseline.json', root / 'candidate.json'
            baseline_path.write_text(json.dumps(worse), encoding='utf-8')
            candidate_path.write_text(json.dumps(report), encoding='utf-8')
            cli = ROOT / '15_SYSTEM' / 'scripts' / 'sources.py'
            result = subprocess.run([sys.executable, str(cli), '--root', str(root), 'compare-benchmarks',
                                     str(baseline_path), str(candidate_path)],
                                    capture_output=True, text=True, check=True)
            self.assertEqual('improved', json.loads(result.stdout)['verdict'])

    def test_cli_approval_and_tampered_proposal_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / 'source.txt'
            f.write_text('the quoted evidence exists', encoding='utf-8')
            source = sources.ingest(root, f, 'document', 'manual')
            sources.rebuild(root)
            proposal = learning.propose(root, source['id'], 'quoted evidence', 'verified lesson', 'quoted')
            cli = ROOT / '15_SYSTEM' / 'scripts' / 'sources.py'
            def run(*args):
                return subprocess.run([sys.executable, str(cli), '--root', str(root), *args],
                                      capture_output=True, text=True)
            self.assertNotEqual(0, run('approve', proposal['id']).returncode)
            self.assertEqual(0, run('approve', proposal['id'], '--approve').returncode)
            self.assertEqual('verified lesson', json.loads(run('recall', 'verified').stdout)[0]['lesson'])
            path = learning._proposal_path(root, proposal['id'])
            row = json.loads(path.read_text(encoding='utf-8'))
            row['lesson'] = 'altered after approval'
            path.write_text(json.dumps(row), encoding='utf-8')
            self.assertNotEqual(0, run('recall', 'altered').returncode)
