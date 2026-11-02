"""Phase 37 (second half) — the python floor stops being a claim CI cannot install.

Measured, not imagined: on 2026-11-01 `ubuntu-latest` became Ubuntu 26.04, `actions/python-versions`
has no CPython 3.9 x64 build for it, and the `ci` and `loop` workflows died inside `setup-python`
on every push — 24 seconds, red — while `python scripts/health.py` on the owner's machine stayed
green and the README went on claiming "Python 3.9+". A promise and the harness that proves it were
allowed to live in different files with nothing comparing them.

`scripts/ci_floor.py` compares them; each class below is red on the state of the repo before it.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_floor  # noqa: E402

CI_GOOD = """name: ci
on: [push]
jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-24.04, windows-latest]
        python-version: ["3.9", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/setup-python@v7
        with:
          python-version: ${{ matrix.python-version }}
"""

LOOP_GOOD = """name: loop
on:
  schedule:
    - cron: "30 3 * * *"
jobs:
  nightly:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
"""

README_GOOD = "# Second Brain\n\n| python floor | 3.9 (standard library only) |\n"
START_GOOD = "# Start\n\n| python floor | 3.9 (standard library only) |\n"


def fixture(root, ci=CI_GOOD, loop=LOOP_GOOD, readme=README_GOOD, start=START_GOOD,
            pyproject='[project]\nname = "x"\nrequires-python = ">=3.9"\n'):
    root = Path(root)
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    if ci is not None:
        (workflows / "ci.yml").write_text(ci, encoding="utf-8")
    if loop is not None:
        (workflows / "loop.yml").write_text(loop, encoding="utf-8")
    (root / "README.md").write_text(readme, encoding="utf-8")
    here = root / "00_START_HERE"
    here.mkdir(parents=True, exist_ok=True)
    (here / "START.md").write_text(start, encoding="utf-8")
    return root


class TestParsing(unittest.TestCase):
    def test_matrix_versions_and_images_are_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp)
            versions, runs = ci_floor.workflow_matrix(root, "ci.yml")
            self.assertEqual(sorted(versions), ["3.12", "3.9"])
            self.assertIn("ubuntu-24.04", runs)
            self.assertIn("windows-latest", runs)

    def test_a_single_valued_python_field_is_not_invisible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp)
            versions, runs = ci_floor.workflow_matrix(root, "loop.yml")
            self.assertEqual(versions, ["3.12"])
            self.assertIn("ubuntu-24.04", runs)

    def test_the_floor_comes_from_pyproject(self):
        self.assertEqual(ci_floor.requires_python_floor(ROOT), "3.9")


class TestRefusals(unittest.TestCase):
    def test_a_workspace_where_everything_agrees_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems, floor = ci_floor.check(fixture(tmp))
            self.assertEqual(problems, [])
            self.assertEqual(floor, "3.9")

    def test_a_floor_ci_never_installs_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            ci = CI_GOOD.replace('["3.9", "3.12"]', '["3.11", "3.12"]')
            problems, _ = ci_floor.check(fixture(tmp, ci=ci))
            self.assertIn("the floor is 3.9 but the ci matrix installs 3.11, 3.12",
                          "\n".join(problems))

    def test_a_job_below_the_floor_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            ci = CI_GOOD.replace('["3.9", "3.12"]', '["3.8", "3.12"]')
            problems, _ = ci_floor.check(fixture(tmp, ci=ci))
            self.assertIn("below the declared floor", "\n".join(problems))

    def test_a_floating_image_is_named_with_the_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            ci = CI_GOOD.replace("[ubuntu-24.04, windows-latest]", "[ubuntu-latest, windows-latest]")
            problems, _ = ci_floor.check(fixture(tmp, ci=ci))
            joined = "\n".join(problems)
            self.assertIn("floating image `ubuntu-latest`", joined)
            self.assertIn("2026-11-01", joined)

    def test_a_nightly_loop_on_a_floating_image_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems, _ = ci_floor.check(fixture(tmp, loop=LOOP_GOOD.replace("ubuntu-24.04",
                                                                             "ubuntu-latest")))
            self.assertIn("nightly loop", "\n".join(problems))

    def test_a_missing_loop_workflow_is_a_problem_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems, _ = ci_floor.check(fixture(tmp, loop=None))
            self.assertIn("the nightly loop has no door", "\n".join(problems))

    def test_a_missing_ci_workflow_is_a_problem_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems, _ = ci_floor.check(fixture(tmp, ci=None))
            self.assertIn("CI cannot prove any floor", "\n".join(problems))

    def test_docs_that_quote_a_different_number_are_named_per_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, readme=README_GOOD.replace("3.9", "3.10"),
                          start=START_GOOD.replace("3.9", "3.8"))
            joined = "\n".join(ci_floor.check(root)[0])
            self.assertIn("README.md tells the reader 3.10", joined)
            self.assertIn("START.md tells the reader 3.8", joined)

    def test_a_doc_row_that_cannot_be_read_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, readme="# x\n\n| python floor | the standard library only |\n")
            self.assertIn("cannot read", "\n".join(ci_floor.check(root)[0]))

    def test_a_pyproject_without_a_floor_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems, floor = ci_floor.check(fixture(tmp, pyproject='[project]\nname = "x"\n'))
            self.assertIn("requires-python", "\n".join(problems))
            self.assertIsNone(floor)


class TestShippedRepo(unittest.TestCase):
    def test_ci_installs_the_floor_this_repo_advertises(self):
        problems, floor = ci_floor.check(ROOT)
        self.assertEqual(problems, [], "the workflows and the docs disagree about the floor")
        self.assertEqual(floor, "3.9")

    def test_the_floor_is_measured_on_two_operating_systems(self):
        _, runs = ci_floor.workflow_matrix(ROOT, "ci.yml")
        self.assertTrue(any(run.startswith("ubuntu") for run in runs), runs)
        self.assertTrue(any("windows" in run for run in runs), runs)


if __name__ == "__main__":
    unittest.main()
