import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '15_SYSTEM' / 'scripts'))
from backend import install_skill


class SkillInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.skill = self.root / 'skills' / 'demo'
        self.skill.mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text('# demo', encoding='utf-8')
        (self.skill / 'scripts').mkdir()
        (self.skill / 'scripts' / 'demo.py').write_text('print(1)', encoding='utf-8')
        self.target = Path(self.temp.name) / 'host'
        self.target.mkdir()
        self.record = {'id': 'SKL-TEST', 'kind': 'skill', 'name': 'demo', 'status': 'approved',
                       'entrypoint': 'skills/demo/SKILL.md', 'origin': '11_CONTROL/skills/demo.json',
                       'harness_compatibility': 'approved', 'permissions': 'unspecified'}
        self.mock = patch.object(install_skill.capabilities, 'inventory', return_value=[self.record])
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_plan_requires_review_and_apply_does_not_replace(self):
        plan = install_skill.plan(self.root, 'SKL-TEST', 'HAR-X', self.target)
        self.assertFalse((self.target / 'demo').exists())
        self.assertEqual({'SKILL.md', 'scripts/demo.py'}, set(plan['files']))
        with self.assertRaises(ValueError):
            install_skill.apply(self.root, plan)
        result = install_skill.apply(self.root, plan, approved=True)
        self.assertEqual(2, result['files'])
        self.assertEqual('# demo', (self.target / 'demo' / 'SKILL.md').read_text(encoding='utf-8'))
        self.assertFalse((self.target / 'demo' / '.install-incomplete').exists())
        with self.assertRaises(ValueError):
            install_skill.apply(self.root, plan, approved=True)

    def test_stale_source_and_unapproved_record_are_refused(self):
        plan = install_skill.plan(self.root, 'SKL-TEST', 'HAR-X', self.target)
        (self.skill / 'SKILL.md').write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError):
            install_skill.apply(self.root, plan, approved=True)
        self.assertFalse((self.target / 'demo').exists())
        self.record['status'] = 'draft'
        with self.assertRaises(ValueError):
            install_skill.plan(self.root, 'SKL-TEST', 'HAR-X', self.target)
        self.record['status'] = 'approved'
        self.record['harness_compatibility'] = 'unknown'
        with self.assertRaises(ValueError):
            install_skill.plan(self.root, 'SKL-TEST', 'HAR-X', self.target)

    def test_incomplete_install_is_left_visible_on_write_failure(self):
        plan = install_skill.plan(self.root, 'SKL-TEST', 'HAR-X', self.target)
        real_open = Path.open
        def fail(path, *args, **kwargs):
            if path.name == 'demo.py' and args and args[0] == 'xb':
                raise OSError('simulated disk failure')
            return real_open(path, *args, **kwargs)
        with patch.object(Path, 'open', fail), self.assertRaises(OSError):
            install_skill.apply(self.root, plan, approved=True)
        self.assertTrue((self.target / 'demo' / '.install-incomplete').is_file())
