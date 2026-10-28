"""Phase 29 -- the embedding seam: off by default, and unable to open itself.

Charter §2 allows a semantic layer only behind a flag, only after a golden-set eval beats
BM25, and only with the owner's approval. What ships here is the seam: one `Embedder`
interface, one deterministic test double made of hashlib, and a gate that refuses every
activation it cannot justify. What does not ship is a model, a dependency, or a network
call -- and these tests hold all three.

The one asymmetry that matters: a perfect evidence file still cannot activate the seam
while the registry holds only the test double. Installing a real embedder is a tool
installation; the owner does that, not a session.
"""
import ast
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BACKEND = ROOT / "15_SYSTEM" / "scripts"
sys.path.insert(0, str(BACKEND))
from backend import vector  # noqa: E402

GOOD = {
    "verdict": "beats_bm25",
    "bm25": 0.60,
    "candidate": 0.80,
    "margin": 0.20,
    "cases": 12,
    "cases_sha256": "a" * 64,
    "approved_by": "owner",
    "approved_at": "2026-10-28",
}


def fixture(flag=False, evidence=None, raw_config=None):
    root = Path(tempfile.mkdtemp())
    config = root / vector.CONFIG
    config.parent.mkdir(parents=True, exist_ok=True)
    if raw_config is not None:
        config.write_text(raw_config, encoding="utf-8")
    else:
        config.write_text(json.dumps({"feature_flags": {"vector_search": flag}}),
                          encoding="utf-8")
    if evidence is not None:
        path = root / vector.EVIDENCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence), encoding="utf-8")
    return root


def run(args, cwd=None):
    return subprocess.run([sys.executable] + [str(arg) for arg in args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(cwd or ROOT))


class TheDoubleIsATestDouble(unittest.TestCase):
    def test_the_shipped_flag_is_false_and_the_registry_is_a_double(self):
        flags = json.loads((ROOT / vector.CONFIG).read_text(encoding="utf-8"))["feature_flags"]
        self.assertFalse(flags["vector_search"])
        self.assertEqual([], vector.production_embedders())
        self.assertFalse(vector.EMBEDDERS[0].production)

    def test_vectors_have_the_requested_dims_and_unit_norm(self):
        embedder = vector.HashingEmbedder(64)
        vec = embedder.embed("bm25 ranking schedule")
        self.assertEqual(64, len(vec))
        self.assertAlmostEqual(1.0, sum(value * value for value in vec), places=9)

    def test_empty_text_is_a_zero_vector_not_an_error(self):
        vec = vector.HashingEmbedder(16).embed("the and")
        self.assertEqual([0.0] * 16, vec)

    def test_dims_outside_the_supported_range_are_refused(self):
        for dims in (0, 7, 4097, True, "64"):
            with self.assertRaises(ValueError):
                vector.HashingEmbedder(dims)

    def test_two_instances_and_two_processes_agree(self):
        embedder = vector.HashingEmbedder(32)
        first = embedder.embed("bm25 ranking")
        self.assertEqual(first, vector.HashingEmbedder(32).embed("bm25 ranking"))
        code = ("import sys;sys.path.insert(0, " + repr(str(BACKEND)) + ");"
                "from backend import vector;print(','.join(format(v, '.12f') for v in "
                "vector.HashingEmbedder(32).embed('bm25 ranking')[:4]))")
        outputs = []
        for seed in ("1", "2"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                    text=True, encoding="utf-8", env=env, cwd=str(ROOT))
            self.assertEqual(0, result.returncode, result.stderr)
            outputs.append(result.stdout.strip())
        expected = ",".join("%.12f" % value for value in first[:4])
        self.assertEqual([expected, expected], outputs)

    def test_the_seam_imports_only_the_standard_library_and_its_sibling(self):
        tree = ast.parse((BACKEND / "backend" / "vector.py").read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])
        self.assertLessEqual(imports, {"hashlib", "json", "math", "re", "datetime", "pathlib"})

    def test_embedding_and_ranking_never_open_a_socket(self):
        def refuse(*_args, **_kwargs):
            raise AssertionError("the seam opened a socket")
        with patch.object(socket, "socket", refuse), \
                patch.object(socket, "create_connection", refuse):
            embedder = vector.HashingEmbedder(32)
            hits = vector.rank([("a.md", "bm25 ranking"), ("b.md", "schedule due")],
                               "bm25", embedder)
            state = vector.gate(ROOT)
        self.assertTrue(hits)
        self.assertFalse(state["active"])


class CosineAndRankArePlainMath(unittest.TestCase):
    def test_cosine_is_symmetric_and_bounded(self):
        embedder = vector.HashingEmbedder(32)
        left, right = embedder.embed("bm25 ranking"), embedder.embed("schedule due")
        self.assertAlmostEqual(1.0, vector.cosine(left, left), places=9)
        self.assertAlmostEqual(vector.cosine(left, right), vector.cosine(right, left), places=12)
        self.assertLessEqual(abs(vector.cosine(left, right)), 1.0)

    def test_orthogonal_and_zero_vectors_score_zero(self):
        self.assertEqual(0.0, vector.cosine([0.0, 0.0], [1.0, 1.0]))
        self.assertEqual(0.0, vector.cosine([1.0, 0.0], [0.0, 1.0]))

    def test_mismatched_lengths_are_refused(self):
        with self.assertRaises(ValueError):
            vector.cosine([1.0], [1.0, 0.0])

    def test_rank_orders_by_score_and_keeps_only_positive_matches(self):
        docs = [("schedule.md", "a schedule record governs when the loop is due"),
                ("ranking.md", "bm25 ranking of documents"),
                ("lesson.md", "a lesson needs an exact quote")]
        hits = vector.rank(docs, "bm25 ranking", vector.HashingEmbedder(64))
        self.assertEqual("ranking.md", hits[0][1])
        self.assertTrue(all(score > 0 for score, _name in hits))
        self.assertNotIn("lesson.md", [name for _score, name in hits])
        self.assertEqual(1, len(vector.rank(docs, "bm25 ranking", vector.HashingEmbedder(64),
                                           limit=1)))

    def test_an_embedder_that_breaks_its_own_dims_is_refused(self):
        class Broken(vector.Embedder):
            dims = 4

            def embed(self, _text):
                return [1.0]
        with self.assertRaises(ValueError):
            vector.rank([("a.md", "text")], "query", Broken())


class TheGateRefusesByName(unittest.TestCase):
    def test_off_means_off_and_the_flag_is_named(self):
        state = vector.gate(fixture(flag=False))
        self.assertFalse(state["active"])
        self.assertIn("feature_flags.vector_search is false", state["problems"])

    def test_an_on_flag_without_evidence_is_refused(self):
        state = vector.gate(fixture(flag=True))
        self.assertFalse(state["active"])
        self.assertTrue(any(vector.EVIDENCE.as_posix() in problem
                            for problem in state["problems"]))

    def test_each_evidence_defect_is_refused_by_its_own_name(self):
        defects = [
            (dict(GOOD, verdict="looks_good"), "verdict"),
            (dict(GOOD, margin=0), "margin"),
            (dict(GOOD, candidate=0.70), "does not equal"),
            (dict(GOOD, cases=3), "cases"),
            (dict(GOOD, cases_sha256="deadbeef"), "cases_sha256"),
            (dict(GOOD, approved_by=""), "approved_by"),
            (dict(GOOD, approved_at="yesterday"), "approved_at"),
        ]
        for evidence, needle in defects:
            state = vector.gate(fixture(flag=True, evidence=evidence))
            self.assertFalse(state["active"], evidence)
            self.assertTrue(any(needle in problem for problem in state["problems"]),
                            "%r not named in %s" % (needle, state["problems"]))

    def test_a_missing_key_is_named_not_defaulted(self):
        evidence = dict(GOOD)
        del evidence["cases"]
        state = vector.gate(fixture(flag=True, evidence=evidence))
        self.assertIn("missing cases", " ".join(state["problems"]))

    def test_perfect_evidence_still_cannot_activate_a_test_double(self):
        state = vector.gate(fixture(flag=True, evidence=GOOD))
        self.assertFalse(state["active"])
        self.assertTrue(any("no production embedder" in problem for problem in state["problems"]))

    def test_unreadable_config_is_a_refusal_not_a_traceback(self):
        state = vector.gate(fixture(raw_config="{not json"))
        self.assertFalse(state["active"])
        self.assertIsNone(state["flag"])
        self.assertIn("cannot read", " ".join(state["problems"]))


class TheCommandsSayTheSameThing(unittest.TestCase):
    def test_status_is_off_on_this_repo(self):
        result = run([SCRIPTS / "vector.py", "status"])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("OFF — vector_search is false", result.stdout)

    def test_status_refuses_a_flipped_flag(self):
        root = fixture(flag=True)
        result = run([SCRIPTS / "vector.py", "status", "--root", root])
        self.assertEqual(1, result.returncode)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("no production embedder", result.stdout)

    def test_probe_shows_determinism_offline(self):
        result = run([SCRIPTS / "vector.py", "probe"])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("repeat: identical", result.stdout)
        self.assertIn("no socket is opened", result.stdout)
        self.assertIn("ranking.md", result.stdout)

    def test_the_health_gate_is_green_while_off_and_red_when_flipped(self):
        result = run([SCRIPTS / "vector_check.py"])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("vector_search is off", result.stdout)
        flipped = fixture(flag=True, evidence=GOOD)
        result = run([SCRIPTS / "vector_check.py", "--root", flipped])
        self.assertEqual(1, result.returncode)
        self.assertIn("INVALID", result.stdout)


if __name__ == "__main__":
    unittest.main()
