"""UTC timezone-aware clock regression tests, Python 3.9+ compatible."""
import datetime
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
import base  # noqa: E402
from backend import vault  # noqa: E402

CLOCK_MODULES = (
    "scripts/handoff.py", "scripts/base.py", "scripts/promote.py",
    "scripts/probe.py", "scripts/loop.py", "scripts/memory.py",
    "scripts/candidate_check.py", "15_SYSTEM/scripts/backend/vault.py",
)


class UTCAwareClocks(unittest.TestCase):
    def test_no_deprecated_naive_utcnow_in_timestamp_modules(self):
        for rel in CLOCK_MODULES:
            with self.subTest(path=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertNotIn("utcnow" + "(", text)

    def test_public_timestamp_format_remains_utc_z(self):
        for read in (base.now, vault.now):
            value = read()
            parsed = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            self.assertLess(abs((datetime.datetime.now(datetime.timezone.utc) -
                                 parsed.replace(tzinfo=datetime.timezone.utc)).total_seconds()), 60)


if __name__ == "__main__":
    unittest.main()
