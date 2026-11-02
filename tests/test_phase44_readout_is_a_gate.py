"""Phase 44 — the link-graph readout is wired into the gate family, and it bites.

The readout agent delivered the measurement (`graph_readout`, `--readout`, edge labels) and
deliberately left `health.py` alone. That is the half where a capability goes quiet: an
un-wired gate is a script nobody runs, and `doc_report.py` counts `len(health.GATES)` as the
number the README prints, so a gate outside the list is a gate that cannot make the repo red
and cannot be seen.

Wiring it raised the question the old link gate dodged. Its verdict line said (and still says)
"0 broken links", which is true of a vault holding an ambiguous edge — the resolver bound a
link to one of two colliding files, so nothing is *missing*. The readout mode names that edge
and calls it "never a healthy edge". Two modes, one vault, opposite opinions, only one of them
judged by CI: that is the silent gate this repo was built to refuse.

The contract these tests hold:

  1. `--readout` is a verdict, not a printout — while an ambiguous edge is escalated it exits 1;
  2. the default link gate prints the graph shape it measured next to its own verdict, so a
     green link gate can never again be mistaken for a statement about reachability;
  3. `health.py` runs the readout as a gate, so `doc_report.py` counts it and CI sees it;
  4. the numbers the two modes print come from the same pass over the same vault — a mode that
     disagrees with the other is a bug, not a second opinion.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import health  # noqa: E402
from link_check import graph_readout  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LINK = str(ROOT / "scripts" / "link_check.py")
NOTE = "---\nid: {stem}\ntype: note\ntitle: \"{stem}\"\nstatus: raw\nowner: agent\n" \
       "topics: [fixture]\ncreated: 2026-11-02\nupdated: 2026-11-02\n---\n\n# {stem}\n\n"


def vault_with(files):
    home = Path(tempfile.mkdtemp(prefix="readout-vault-"))
    for relpath, body in files.items():
        p = home / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return home


def run(vault, *flags):
    return subprocess.run([sys.executable, LINK, "--vault", str(vault)] + list(flags),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


CLEAN = {"a/widget.md": NOTE.format(stem="widget"),
         "b/gadget.md": NOTE.format(stem="gadget") + "see [[a/widget]]\n"}
# the collision is deliberate: `[[a/widget]]` names one file literally, while `[[widget]]`
# now names two, so exactly one edge escalates and the counts stay checkable by hand
ESCALATED = dict(CLEAN)
ESCALATED.update({
    "c/widget.md": NOTE.format(stem="widget"),          # a second file shares the stem
    "d/hub.md": NOTE.format(stem="hub") + "points at [[widget]]\n"})


class TestTheReadoutIsAVerdict(unittest.TestCase):
    def setUp(self):
        self.vault = vault_with(CLEAN)

    def tearDown(self):
        shutil.rmtree(self.vault, ignore_errors=True)

    def test_a_settled_graph_passes_and_says_what_it_measured(self):
        code = run(self.vault, "--readout")
        self.assertEqual(code.returncode, 0, code.stdout + code.stderr)
        self.assertIn("link graph measured", code.stdout, code.stdout)
        ok = [line for line in code.stdout.splitlines() if line.startswith("OK")]
        self.assertEqual(len(ok), 1, "health counts one OK line per gate: %r" % code.stdout)
        self.assertIn("notes scanned: 2", code.stdout,
                      "the denominator has to be the notes it scanned")

    def test_an_escalated_edge_refuses_the_readout(self):
        """A colliding stem binds a link by accident; the graph gate must not call that healthy."""
        vault = vault_with(ESCALATED)
        try:
            code = run(vault, "--readout")
            self.assertEqual(code.returncode, 1, code.stdout + code.stderr)
            self.assertIn("REFUSED", code.stdout, code.stdout)
            self.assertIn("widget", code.stdout, code.stdout)
            self.assertNotIn("link graph measured", code.stdout,
                             "a refused graph cannot also certify itself")
        finally:
            shutil.rmtree(vault, ignore_errors=True)

    def test_a_broken_link_still_refuses_the_default_gate(self):
        vault = vault_with(dict(CLEAN, **{"e/orphan.md": NOTE.format(stem="orphan")
                                          + "[[nowhere]]\n"}))
        try:
            code = run(vault)
            self.assertEqual(code.returncode, 1, code.stdout + code.stderr)
            self.assertIn("BROKEN", code.stdout, code.stdout)
        finally:
            shutil.rmtree(vault, ignore_errors=True)


class TestTheLinkGateShowsItsOwnShape(unittest.TestCase):
    def tearDown(self):
        if getattr(self, "vault", None):
            shutil.rmtree(self.vault, ignore_errors=True)

    def test_the_default_verdict_line_is_unchanged_and_the_shape_rides_with_it(self):
        self.vault = vault_with(CLEAN)
        code = run(self.vault)
        self.assertEqual(code.returncode, 0, code.stdout + code.stderr)
        self.assertRegex(code.stdout, r"^OK — 0 broken links in ", code.stdout)
        self.assertIn("graph: 2 note(s)", code.stdout, code.stdout)
        for token in ("extracted", "component(s)", "degree-0", "bridge note(s)", "ambiguous"):
            self.assertIn(token, code.stdout, "the shape line must carry the whole readout: %s"
                          % token)

    def test_an_ambiguous_graph_is_visible_in_the_default_run_before_it_is_refused_anywhere(self):
        vault = vault_with(ESCALATED)
        try:
            code = run(vault)
            self.assertIn("1 ambiguous", code.stdout,
                          "the link gate prints the edge it will not resolve: %s" % code.stdout)
        finally:
            shutil.rmtree(vault, ignore_errors=True)

    def test_both_modes_agree_because_they_are_one_pass(self):
        self.vault = vault_with(ESCALATED)
        data = graph_readout(self.vault)
        shape = run(self.vault).stdout
        readout = run(self.vault, "--readout").stdout
        self.assertIn("%d note(s)" % len(data["notes_scanned"]), shape, shape)
        self.assertIn("notes scanned: %d" % len(data["notes_scanned"]), readout, readout)
        self.assertEqual(len(data["ambiguous"]), 1, data["ambiguous"])


class TestTheGateFamilyRunsIt(unittest.TestCase):
    def test_health_runs_the_readout_as_a_gate(self):
        entry = [g for g in health.GATES if g.split()[0] == "link_check.py"]
        self.assertIn("--readout", " ".join(entry),
                      "the readout is not a capability until health runs it: %r" % entry)

    def test_the_flag_survives_into_the_argv(self):
        """A gate entry that loses its flag in argv would silently re-run the other mode."""
        for entry in health.GATES:
            argv = health.gate_argv(entry, ["--vault", "."])
            self.assertTrue(Path(argv[1]).is_file(), "gate %s points at no script: %s" % (entry, argv))
            if "--readout" in entry:
                self.assertIn("--readout", argv, argv)
                self.assertIn("--vault", argv, argv)

    def test_the_gate_count_the_documents_print_is_the_list_health_walks(self):
        import doc_report
        self.assertEqual(doc_report.gates(ROOT), len(health.GATES))

    def test_the_readout_line_appears_in_a_real_health_run(self):
        """End-to-end: the composite command actually prints the graph verdict for this repo."""
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "health.py")],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", cwd=str(ROOT), timeout=900)
        self.assertEqual(result.returncode, 0,
                         "a gate wired into health is judged by health: %s"
                         % result.stdout[-4000:])
        self.assertIn("\nOK", "\n" + result.stdout)
        self.assertNotIn("\ufffd", result.stdout,
                         "a gate that writes cp1252 bytes is a gate whose verdict arrives as mojibake")
        self.assertIn("link graph measured", result.stdout, result.stdout[-4000:])
        ok_lines = [line for line in result.stdout.splitlines() if line.startswith("OK")]
        self.assertEqual(len(ok_lines), len(health.GATES),
                         "health printed %d OK lines for %d gates:\n%s"
                         % (len(ok_lines), len(health.GATES), result.stdout))


class TestTheLawSaysWhereTheReadoutLives(unittest.TestCase):
    def test_the_module_docstring_owns_the_verdict_it_implements(self):
        text = (ROOT / "scripts" / "link_check.py").read_text(encoding="utf-8")
        self.assertIn("--readout", text)
        self.assertIn("refuses", text.lower(),
                      "a flag whose contract lives only in the code is a flag nobody can review")

    def test_the_changelog_records_the_wiring(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?i)readout")


if __name__ == "__main__":
    unittest.main()
