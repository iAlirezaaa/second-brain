import json
import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '15_SYSTEM' / 'scripts'))
from backend import sources
import mcp_server
import common


class SourcesTest(unittest.TestCase):
    def test_indexed_and_legacy_rankings_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            texts = ['backup restore backup', 'restore backups and garden', 'يادگيري ماشين',
                     'a source about SOURCE citation', 'unrelated', 'در این متن فارسی']
            for number, text in enumerate(texts):
                file = root / (str(number) + '.txt')
                file.write_text(text, encoding='utf-8')
                sources.ingest(root, file, 'document', 'test:' + str(number))
            sources.rebuild(root)
            queries = ['restore backup', 'backup', 'ستو', 'یادگیری ماشین', 'SOURCE',
                       'unknown', '!', 'فارسی', 'back', 'a source']
            expected = {q: sources.search_scan(root, q) for q in queries}
            for q in queries:
                self.assertEqual(expected[q], sources.search(root, q), q)
            with closing(sqlite3.connect(str(root / sources.DATA / 'index.sqlite'))) as db:
                db.execute('DROP TABLE term_counts')
                db.execute('DROP TABLE document_lengths')
                db.commit()
            for q in queries:
                self.assertEqual(expected[q], sources.search(root, q), q)

    def test_word_order_unicode_and_relevance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relevant = root / 'relevant.txt'
            other = root / 'other.txt'
            relevant.write_text('A backup must be restored and checked. backup restore backup restore', encoding='utf-8')
            other.write_text('Restore backups and talk about gardens.', encoding='utf-8')
            expected = sources.ingest(root, relevant, 'document', 'test:relevant')
            sources.ingest(root, other, 'document', 'test:other')
            persian = root / 'persian.txt'
            persian.write_text('مدیریت اطلاعات و يادگيري ماشين', encoding='utf-8')
            p = sources.ingest(root, persian, 'document', 'test:persian')
            sources.rebuild(root)
            self.assertEqual(expected['id'], sources.search(root, 'restore backup', 1)[0]['id'])
            self.assertEqual(p['id'], sources.search(root, 'یادگیری ماشین', 1)[0]['id'])

    def test_import_rebuild_search_and_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'chat.txt'
            file.write_text('A unique conversation about retrieval', encoding='utf-8')
            first = sources.ingest(root, file, 'conversation', 'codex:session-1')
            self.assertFalse(common.clone_readable('.brain-data/sources/example/raw.txt'))
            self.assertNotIn('.brain-data', str(common.tree_inventory(root)))
            self.assertEqual(first, sources.ingest(root, file, 'conversation', 'codex:session-1'))
            self.assertEqual(1, sources.rebuild(root))
            hit = sources.search(root, 'retrieval')[0]
            self.assertEqual(first['id'], hit['id'])
            self.assertEqual('codex:session-1', hit['origin'])
            self.assertEqual('conversation', hit['kind'])
            result = mcp_server.handle_tool_call(root, {'name': 'source_search',
                                                       'arguments': {'query': 'retrieval'}})
            self.assertEqual('codex:session-1', json.loads(result['content'][0]['text'])[0]['origin'])
            self.assertEqual(1, sources.rebuild(root))
            self.assertEqual(1, len(sources.search(root, 'retrieval')))

    def test_bad_import_and_failed_rebuild_preserve_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'note.txt'
            file.write_text('original', encoding='utf-8')
            source = sources.ingest(root, file, 'research', 'https://example.org')
            sources.rebuild(root)
            metadata = root / sources.DATA / 'sources' / source['id'] / 'metadata.json'
            metadata.write_text('{invalid', encoding='utf-8')
            with self.assertRaises(ValueError):
                sources.rebuild(root)
            self.assertEqual(1, len(sources.search(root, 'original')))
            with self.assertRaises(ValueError):
                sources.ingest(root, file, 'invalid', 'origin')

    def test_incomplete_record_refuses_rebuild_and_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'note.txt'
            file.write_text('original text', encoding='utf-8')
            source = sources.ingest(root, file, 'document', 'manual')
            sources.rebuild(root)
            folder = root / sources.DATA / 'sources' / source['id']
            (folder / 'metadata.json').unlink()
            with self.assertRaises((ValueError, OSError)):
                sources.rebuild(root)
            self.assertEqual(1, len(sources.search(root, 'original')))
            (folder / 'raw.txt').write_text('unexpected data', encoding='utf-8')
            with self.assertRaises((ValueError, OSError)):
                sources.ingest(root, file, 'document', 'manual')
            self.assertEqual('unexpected data', (folder / 'raw.txt').read_text(encoding='utf-8'))

    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'source.txt'
            file.write_text('cli unique text', encoding='utf-8')
            cli = ROOT / '15_SYSTEM' / 'scripts' / 'sources.py'
            def run(*args):
                return subprocess.run([sys.executable, str(cli), '--root', str(root), *args],
                                      capture_output=True, text=True, check=True)
            run('import', str(file), '--kind', 'document', '--origin', 'manual')
            run('rebuild')
            self.assertEqual('manual', json.loads(run('search', 'unique').stdout)[0]['origin'])

    def test_raw_bytes_preserve_bom_and_windows_newlines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'windows.txt'
            raw = b'\xef\xbb\xbffirst\r\nsecond\r\n'
            file.write_bytes(raw)
            meta = sources.ingest(root, file, 'document', 'local:test')
            self.assertEqual(raw, (root / sources.DATA / 'sources' / meta['id'] / 'raw.txt').read_bytes())
            self.assertEqual(meta, sources.ingest(root, file, 'document', 'local:test'))
            self.assertEqual(1, sources.rebuild(root))
            self.assertEqual(1, len(sources.search(root, 'second')))

    def test_codex_projection_keeps_only_user_and_assistant_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / 'rollout.jsonl'
            rows = [
                {'type': 'session_meta', 'payload': {'base_instructions': 'privateinstructions'}},
                {'type': 'response_item', 'payload': {'type': 'function_call_output', 'output': 'privateoutput'}},
                {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'unique user question'}]}},
                {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'unique assistant answer'}]}},
            ]
            raw = ('\n'.join(json.dumps(row) for row in rows) + '\n').encode('utf-8')
            file.write_bytes(raw)
            meta = sources.ingest(root, file, 'conversation', 'codex:example', 'codex-jsonl')
            self.assertEqual(raw, (root / sources.DATA / 'sources' / meta['id'] / 'raw.txt').read_bytes())
            sources.rebuild(root)
            self.assertEqual(1, len(sources.search(root, 'assistant answer')))
            self.assertEqual([], sources.search(root, 'privateoutput'))
            self.assertEqual([], sources.search(root, 'privateinstructions'))
            file.write_text('{invalid', encoding='utf-8')
            with self.assertRaises(ValueError):
                sources.ingest(root, file, 'conversation', 'codex:bad', 'codex-jsonl')

    def test_claude_and_cursor_streams_skip_tool_results(self):
        for source_format in ('claude-stream-json', 'cursor-stream-json'):
            with self.subTest(source_format=source_format), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                file = root / 'stream.jsonl'
                rows = [
                    {'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'text', 'text': 'user question'}]}},
                    {'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'answer '}]}},
                    {'type': 'tool_call', 'result': 'private tool output'},
                    {'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'private tool result'}]}},
                    {'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'complete'}]}},
                    {'type': 'result', 'result': 'duplicate final output'},
                ]
                file.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
                sources.ingest(root, file, 'conversation', source_format + ':1', source_format)
                sources.rebuild(root)
                result = sources.search(root, 'answer')[0]['text']
                self.assertIn('user question', result)
                self.assertIn('complete', result)
                self.assertNotIn('private tool', result)
                self.assertNotIn('duplicate final', result)
                if source_format == 'cursor-stream-json':
                    self.assertIn('answer complete', result)
                with self.assertRaises(ValueError):
                    sources.ingest(root, file, 'document', 'wrong-kind', source_format)
                rows[0]['session_id'] = 'one'
                rows[1]['session_id'] = 'two'
                file.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')
                with self.assertRaises(ValueError):
                    sources.ingest(root, file, 'conversation', 'mixed', source_format)
