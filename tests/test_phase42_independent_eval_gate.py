"""Phase 36, the gates that were still unchecked: independent eval, repeatable claim, way back.

Nothing here claims a model got better. What is measured, and executed through the real CLI:

  * `dataset-eval-gate DATASET EVAL` refuses an eval set sharing any identifier (case id,
    expected source id, document origin) with a built dataset manifest -- and refuses a
    dataset that no longer verifies, so the gate cannot be bypassed by editing the manifest;
  * `retrieval_eval.claim` publishes IMPROVEMENT only when every repeat improved both mean
    recall and MRR past a positive margin; REGRESSION and NO_IMPROVEMENT are real verdicts
    that exit nonzero, and a claim without a saved known-good base is refused outright;
  * the claim report carries the two reports, the margin, the repeat count and the exact
    `python scripts/base.py --recover --stamp ...` line back to the recorded base.
"""
import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
from backend import dataset, retrieval_eval, sources  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "retrieval-independent-eval.json"
GOLDEN = ROOT / "tests" / "fixtures" / "retrieval-golden.json"
CLI = ROOT / "15_SYSTEM" / "scripts" / "sources.py"
STAMP = "20261029T000000Z"
BASE = {"stamp": STAMP, "fingerprint": "f" * 64}


def previous_search(root, query, limit=10):
    """The search from before ranked retrieval: whole-query substring, newest first."""
    with closing(sqlite3.connect(str(root / sources.DATA / "index.sqlite"))) as db:
        rows = db.execute('SELECT id, kind, origin, filename, imported_at, body FROM sources '
                          'WHERE instr(lower(body), lower(?)) > 0 ORDER BY imported_at DESC LIMIT ?',
                          (query, limit)).fetchall()
    return [dict(zip(("id", "kind", "origin", "filename", "imported_at", "text"), row))
            for row in rows]


def run_cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), "--root", str(root), *[str(a) for a in args]],
                          capture_output=True, text=True)


def ingest_fixture(root, fixture):
    ids = {}
    for doc in fixture["documents"]:
        f = root / (doc["name"] + ".txt")
        f.write_text(doc["text"], encoding="utf-8")
        ids[doc["name"]] = sources.ingest(root, f, "document",
                                          doc.get("origin") or "fixture:" + doc["name"])["id"]
    sources.rebuild(root)
    return ids


def golden_cases(ids):
    fixture = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return [{"query": item["query"], "expected_ids": [ids[item["expected"]]]}
            for item in fixture["cases"]]


class TheIndependentFixtureIsItselfMeasured(unittest.TestCase):
    """The eval set must be answerable before it can grade anything."""

    def test_every_case_is_retrievable_on_a_corpus_made_only_of_the_fixture(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ids = ingest_fixture(root, fixture)
            cases = [{"query": case["query"], "expected_ids": [ids[case["expected"]]]}
                     for case in fixture["cases"]]
            report = retrieval_eval.run(root, cases, limit=10)
            self.assertEqual(1.0, report["mean_recall"])
            self.assertEqual(1.0, report["mean_reciprocal_rank"])

    def test_case_ids_are_unique_and_the_documents_are_not_the_golden_ones(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        case_ids = [case["id"] for case in fixture["cases"]]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertTrue(all(str(case["query"]).strip() for case in fixture["cases"]))
        golden_texts = {doc["text"] for doc in golden["documents"]}
        for doc in fixture["documents"]:
            self.assertNotIn(doc["text"], golden_texts)
            self.assertTrue(doc["origin"].startswith("fixture-independent:"))


class EvalGateRefusesAnySharedIdentifier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.first = self.import_text("chat.txt", "the first conversation about retrieval",
                                      "conversation", "codex:session-1")
        self.second = self.import_text("memo.txt", "a private client memo", "document",
                                       "local:memo")
        for meta in (self.first, self.second):
            dataset.mark_shareable(self.root, meta["id"], approved=True)
        self.out = self.root / "out"
        dataset.build(self.root, self.out, limit=40)

    def tearDown(self):
        self._tmp.cleanup()

    def import_text(self, name, text, kind, origin):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return sources.ingest(self.root, path, kind, origin)

    def write_eval(self, payload):
        path = self.root / "eval.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_a_clean_disjoint_eval_is_accepted(self):
        result = dataset.leak_check(self.out, FIXTURE)
        self.assertTrue(result["ok"], result["leaks"])
        self.assertEqual([], result["leaks"])

    def test_the_clean_pair_passes_through_the_command(self):
        answer = run_cli(self.root, "dataset-eval-gate", self.out, FIXTURE)
        self.assertEqual(0, answer.returncode, answer.stdout + answer.stderr)
        self.assertTrue(json.loads(answer.stdout)["ok"])

    def test_a_case_id_that_is_a_training_source_id_is_refused_by_name(self):
        source_id = self.second["id"]
        cases = self.write_eval({"cases": [{"id": source_id, "query": "anything",
                                            "expected_ids": ["a" * 64]}]})
        answer = run_cli(self.root, "dataset-eval-gate", self.out, cases)
        self.assertNotEqual(0, answer.returncode)
        self.assertIn(source_id, answer.stdout)
        leak = json.loads(answer.stdout)["leaks"][0]
        self.assertEqual(source_id, leak["identifier"])

    def test_a_case_id_equal_to_an_example_id_is_refused(self):
        first_example = json.loads((self.out / "examples.jsonl").read_text(
            encoding="utf-8").splitlines()[0])
        cases = self.write_eval({"cases": [{"id": first_example["id"], "query": "anything",
                                            "expected_ids": ["b" * 64]}]})
        answer = run_cli(self.root, "dataset-eval-gate", self.out, cases)
        self.assertNotEqual(0, answer.returncode)
        self.assertIn(first_example["id"], answer.stdout)

    def test_an_eval_document_pointing_at_a_trained_origin_is_refused(self):
        cases = self.write_eval({
            "documents": [{"name": "memo", "origin": "local:memo", "text": "whatever"}],
            "cases": [{"id": "leaky-1", "query": "memo", "expected": "memo"}]})
        answer = run_cli(self.root, "dataset-eval-gate", self.out, cases)
        self.assertNotEqual(0, answer.returncode)
        leaks = json.loads(answer.stdout)["leaks"]
        self.assertIn("local:memo", [leak["identifier"] for leak in leaks])
        self.assertIn("leaky-1", [leak["case"] for leak in leaks])

    def test_an_expected_id_equal_to_a_training_source_id_is_refused(self):
        cases = self.write_eval({"cases": [{"id": "leaky-2", "query": "anything",
                                            "expected_ids": [self.first["id"]]}]})
        result = dataset.leak_check(self.out, cases)
        self.assertFalse(result["ok"])
        self.assertIn(self.first["id"], str(result["leaks"]))

    def test_a_tampered_dataset_cannot_pass_the_gate(self):
        path = self.out / "examples.jsonl"
        path.write_text(path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            dataset.leak_check(self.out, FIXTURE)
        self.assertIn("does not verify", str(caught.exception))
        answer = run_cli(self.root, "dataset-eval-gate", self.out, FIXTURE)
        self.assertEqual(2, answer.returncode)
        self.assertIn("does not verify", answer.stderr)


class TheClaimGate(unittest.TestCase):
    """retrieval_eval.claim: repeats, a positive margin, and a way back -- or no verdict."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        fixture = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.ids = ingest_fixture(self.root, fixture)
        self.cases = golden_cases(self.ids)
        with patch.object(sources, "search", side_effect=previous_search):
            self.baseline = retrieval_eval.run(self.root, self.cases, limit=1)
        self.candidate = retrieval_eval.run(self.root, self.cases, limit=1)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_measured_before_after_clears_a_positive_margin_on_every_repeat(self):
        result = retrieval_eval.claim([self.baseline, copy.deepcopy(self.baseline)],
                                      [self.candidate, copy.deepcopy(self.candidate)],
                                      0.4, BASE)
        self.assertEqual("IMPROVEMENT", result["verdict"])
        self.assertEqual(2, result["repeats"])
        self.assertEqual(0.4, result["margin"])
        self.assertEqual(0.5, result["min_delta_mean_recall"])
        self.assertEqual(0.5, result["min_delta_mean_reciprocal_rank"])
        self.assertIn("baseline", result["reports"])
        self.assertIn("candidate", result["reports"])
        self.assertEqual(BASE, result["base"])
        self.assertIn("--recover --stamp " + STAMP, result["recover"])

    def test_a_margin_the_gain_does_not_clear_is_no_improvement_not_a_bare_better(self):
        result = retrieval_eval.claim([self.baseline], [self.candidate], 0.6, BASE)
        self.assertEqual("NO_IMPROVEMENT", result["verdict"])

    def test_a_regression_is_a_regression(self):
        result = retrieval_eval.claim([self.candidate], [self.baseline], 0.1, BASE)
        self.assertEqual("REGRESSION", result["verdict"])

    def test_one_flat_repeat_among_two_is_not_a_repeatable_gain(self):
        result = retrieval_eval.claim([self.baseline, copy.deepcopy(self.baseline)],
                                      [self.candidate, copy.deepcopy(self.baseline)],
                                      0.1, BASE)
        self.assertEqual("NO_IMPROVEMENT", result["verdict"])

    def test_a_bare_better_needs_a_margin_and_a_positive_one(self):
        for margin in (0, -0.5, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                retrieval_eval.claim([self.baseline], [self.candidate], margin, BASE)

    def test_a_claim_without_a_saved_base_is_refused_before_any_verdict(self):
        for base in (None, {}, {"stamp": STAMP}, {"fingerprint": "x" * 64}):
            with self.assertRaises(ValueError) as caught:
                retrieval_eval.claim([self.baseline], [self.candidate], 0.1, base)
            self.assertIn("base.py --save", str(caught.exception))

    def test_repeats_must_measure_the_same_world(self):
        other_cases = [{"query": "gardens", "expected_ids": [self.ids["garden"]]}]
        other = retrieval_eval.run(self.root, other_cases, limit=1)
        with patch.object(sources, "search", side_effect=previous_search):
            other_baseline = retrieval_eval.run(self.root, other_cases, limit=1)
        with self.assertRaises(ValueError) as caught:
            retrieval_eval.claim([self.baseline, other_baseline], [self.candidate, other],
                                 0.1, BASE)
        self.assertIn("one case set", str(caught.exception))

    def test_known_good_base_reads_the_journal_and_survives_garbage(self):
        journal = self.root / "14_CANDIDATES" / "loop" / "bases.jsonl"
        self.assertIsNone(retrieval_eval.known_good_base(self.root))
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text("not json at all\n" + json.dumps({"event": "recovery"}) + "\n"
                           + json.dumps({"stamp": "20260101T000000Z", "fingerprint": "a" * 64})
                           + "\n" + json.dumps({"stamp": STAMP, "fingerprint": "b" * 64}) + "\n",
                           encoding="utf-8")
        self.assertEqual({"stamp": STAMP, "fingerprint": "b" * 64},
                         retrieval_eval.known_good_base(self.root))


class TheComparisonCommandCarriesTheWayBack(unittest.TestCase):
    """compare-benchmarks: measurement unchanged, publication gated, regression loud."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        fixture = json.loads(GOLDEN.read_text(encoding="utf-8"))
        ids = ingest_fixture(self.root, fixture)
        cases = golden_cases(ids)
        with patch.object(sources, "search", side_effect=previous_search):
            baseline = retrieval_eval.run(self.root, cases, limit=1)
        candidate = retrieval_eval.run(self.root, cases, limit=1)
        self.baseline_path = self.root / "baseline.json"
        self.candidate_path = self.root / "candidate.json"
        self.baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
        self.candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        self.worse_path = self.root / "worse.json"
        self.worse_path.write_text(json.dumps(baseline), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def save_base(self):
        journal = self.root / "14_CANDIDATES" / "loop" / "bases.jsonl"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(json.dumps({"event": "base", "stamp": STAMP,
                                       "fingerprint": "f" * 64, "gates": "green"}) + "\n",
                           encoding="utf-8")

    def test_a_claim_is_refused_when_no_base_was_ever_saved(self):
        answer = run_cli(self.root, "compare-benchmarks", self.baseline_path,
                         self.candidate_path, "--claim", "--margin", "0.4")
        self.assertEqual(2, answer.returncode)
        self.assertIn("no known-good base is recorded", answer.stderr)
        self.assertIn("base.py --save", answer.stderr)
        self.assertNotIn("verdict", answer.stdout)

    def test_a_published_claim_carries_reports_margin_repeats_and_the_recover_line(self):
        self.save_base()
        answer = run_cli(self.root, "compare-benchmarks", self.baseline_path,
                         self.candidate_path, "--claim", "--margin", "0.4")
        self.assertEqual(0, answer.returncode, answer.stdout + answer.stderr)
        result = json.loads(answer.stdout)
        self.assertEqual("IMPROVEMENT", result["verdict"])
        self.assertEqual(1, result["repeats"])
        self.assertEqual(0.4, result["margin"])
        self.assertIn("python scripts/base.py --recover --stamp " + STAMP, result["recover"])
        self.assertEqual(1, len(result["reports"]["baseline"]))
        self.assertEqual(1, len(result["reports"]["candidate"]))

    def test_no_improvement_and_regression_claims_exit_nonzero(self):
        self.save_base()
        answer = run_cli(self.root, "compare-benchmarks", self.baseline_path,
                         self.candidate_path, "--claim", "--margin", "0.9")
        self.assertEqual(1, answer.returncode)
        self.assertEqual("NO_IMPROVEMENT", json.loads(answer.stdout)["verdict"])
        answer = run_cli(self.root, "compare-benchmarks", self.candidate_path,
                         self.worse_path, "--claim", "--margin", "0.1")
        self.assertEqual(1, answer.returncode)
        self.assertEqual("REGRESSION", json.loads(answer.stdout)["verdict"])

    def test_a_claim_without_a_margin_is_refused(self):
        self.save_base()
        answer = run_cli(self.root, "compare-benchmarks", self.baseline_path,
                         self.candidate_path, "--claim")
        self.assertEqual(2, answer.returncode)
        self.assertIn("positive margin", answer.stderr)

    def test_a_plain_comparison_still_measures_but_a_regression_now_exits_nonzero(self):
        answer = run_cli(self.root, "compare-benchmarks", self.baseline_path, self.candidate_path)
        self.assertEqual(0, answer.returncode)
        result = json.loads(answer.stdout)
        self.assertEqual("improved", result["verdict"])
        self.assertFalse(result["base_saved"])
        self.assertIsNone(result["recover"])
        answer = run_cli(self.root, "compare-benchmarks", self.candidate_path, self.worse_path)
        self.assertEqual(1, answer.returncode)
        self.assertEqual("regressed", json.loads(answer.stdout)["verdict"])

    def test_a_plain_comparison_names_the_way_back_when_a_base_exists(self):
        self.save_base()
        answer = run_cli(self.root, "compare-benchmarks", self.baseline_path, self.candidate_path)
        self.assertEqual(0, answer.returncode)
        result = json.loads(answer.stdout)
        self.assertTrue(result["base_saved"])
        self.assertIn("--recover --stamp " + STAMP, result["recover"])


if __name__ == "__main__":
    unittest.main()
