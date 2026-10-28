import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '15_SYSTEM' / 'scripts'))
from backend.search import vault_search
from backend.tools_kit import Context, ToolError, default_registry
import mcp_server


class AccessBoundary(unittest.TestCase):
    def test_search_and_file_read_refuse_protected_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ['02_WIKI/public.md', '14_CANDIDATES/private.md',
                     '09_OPERATIONS/clients_metadata_only/private.md',
                     '15_SYSTEM/generated/private.md', '12_RUNTIME/private.md']
            for name in paths:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('uniqueneedle', encoding='utf-8')
            hits = [doc['path'] for _, doc in vault_search(root, 'uniqueneedle')]
            self.assertEqual(['02_WIKI/public.md'], hits)
            registry = default_registry()
            self.assertEqual('uniqueneedle', registry.execute(Context(root), 'core.fs_read', {'path': paths[0]}))
            for name in paths[1:]:
                with self.subTest(name=name), self.assertRaises(ToolError):
                    registry.execute(Context(root), 'core.fs_read', {'path': name})

    def test_resources_read_only_published_safe_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'AGENTS.md').write_text('public', encoding='utf-8')
            secret = root / '14_CANDIDATES' / 'secret.md'
            secret.parent.mkdir()
            secret.write_text('private', encoding='utf-8')
            self.assertEqual('public', mcp_server.read_resource(root, 'file://AGENTS.md')['text'])
            with self.assertRaises(mcp_server.ToolRefused):
                mcp_server.read_resource(root, 'file://14_CANDIDATES/secret.md')

    def test_tool_read_and_search_reject_credential_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ['.env', '02_WIKI/.env.production', '02_WIKI/private.key',
                     '02_WIKI/my-credentials.json', '02_WIKI/secrets/private.md',
                     '02_WIKI/.secrets/private.md', '.git/config']
            registry = default_registry()
            for name in paths:
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('uniquesecretmarker', encoding='utf-8')
                with self.subTest(name=name), self.assertRaises(ToolError):
                    registry.execute(Context(root), 'core.fs_read', {'path': name})
            self.assertEqual([], vault_search(root, 'uniquesecretmarker'))

    def test_symlink_cannot_alias_a_denied_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'secrets').mkdir()
            secret = root / 'secrets' / 'private.md'
            secret.write_text('hidden', encoding='utf-8')
            alias = root / 'public.md'
            try:
                alias.symlink_to(secret)
            except OSError:
                self.skipTest('file symlinks unavailable on this platform')
            with self.assertRaises(ToolError):
                default_registry().execute(Context(root), 'core.fs_read', {'path': 'public.md'})
            self.assertEqual([], vault_search(root, 'hidden'))


if __name__ == '__main__':
    unittest.main()
