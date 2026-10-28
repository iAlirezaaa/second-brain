import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '15_SYSTEM' / 'scripts'))
from backend import capabilities
import mcp_server


class CapabilityTests(unittest.TestCase):
    def test_inventory_reflects_registry_and_builtin_tools(self):
        items = capabilities.inventory(ROOT, 'HAR-UNKNOWN')
        skill = next(x for x in items if x['name'] == 'kb-search')
        self.assertEqual('draft', skill['status'])
        self.assertEqual('unknown', skill['harness_compatibility'])
        self.assertEqual('unknown', skill['installed'])
        self.assertIn('Search-first', skill['description'])
        writer = next(x for x in items if x['id'] == 'core.ltm_store')
        self.assertEqual('write_requires_approval_and_allowlist', writer['permissions'])

    def test_suggestions_and_cli_and_mcp(self):
        items = capabilities.suggest(ROOT, 'Search KB', limit=10)
        self.assertTrue(any(x['name'] == 'kb-search' for x in items))
        self.assertEqual([], capabilities.suggest(ROOT, 'unfindablexyz'))
        cli = ROOT / '15_SYSTEM' / 'scripts' / 'capabilities.py'
        proc = subprocess.run([sys.executable, str(cli), '--root', str(ROOT), '--task', 'search'],
                              capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(proc.stdout))
        response = mcp_server.handle_tool_call(ROOT, {'name': 'capabilities', 'arguments': {'task': 'search'}})
        self.assertTrue(json.loads(response['content'][0]['text']))

    def test_invalid_query_and_limit_are_refused(self):
        with self.assertRaises(ValueError):
            capabilities.suggest(ROOT, '', limit=10)
        with self.assertRaises(ValueError):
            capabilities.suggest(ROOT, 'search', limit=0)

    def test_retired_and_harness_status_from_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [
                (root / '11_CONTROL' / 'skills' / 'active.json', {'id': 'SKL-A', 'kind': 'skill',
                 'name': 'active', 'status': 'approved', 'approved_for_harness_ids': ['HAR-A']}),
                (root / '11_CONTROL' / 'skills' / 'retired.json', {'id': 'SKL-B', 'kind': 'skill',
                 'name': 'retired', 'status': 'approved'}),
            ]
            class FakeRegistry:
                def config(self): return {}
                def iter_records(self, config): return iter(records)
                def superseded_by(self, all_records): return {'SKL-B': 'SKL-A'}
            with patch.object(capabilities, 'bind_hades', return_value=FakeRegistry()):
                items = capabilities.inventory(root, 'HAR-A')
                self.assertFalse(any(x['id'] == 'SKL-B' for x in items))
                self.assertEqual('approved', next(x for x in items if x['id'] == 'SKL-A')['harness_compatibility'])
                items = capabilities.inventory(root, 'HAR-B')
                self.assertEqual('not_approved', next(x for x in items if x['id'] == 'SKL-A')['harness_compatibility'])
