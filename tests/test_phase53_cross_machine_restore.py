"""Phase 53 -- a second machine reads the bytes back, and no run of this proof is self-evidence.

`scripts/backup_proof.py` exists for one question that `scripts/vault.py` cannot answer on its own:
section 8 of the charter asks for an encrypted backup *and a restore test actually run*. A seal
proves the writer wrote. It never exercises the reader on a machine that has not seen those bytes,
and the failures that live there -- a path rule, an end-of-line, a filesystem detail, a bug in the
open path -- are exactly the ones that make a trusted backup useless.

The laws these tests hold:

* A proof may only seal bytes it wrote itself. `--fixture` refuses a plane that already holds
  files, so this script can never be the thing that read -- or destroyed -- the owner's vault.
* A run on the machine that just sealed is a byte check, not a recovery test, and says so.
* Nothing a repository can author may count as evidence for itself: no passphrase, envelope or
  witness crosses the repository boundary, and no command writes inside it or flips a flag.
* Every refusal names the law it refused under, and a failed restore leaves nothing behind.
"""
import contextlib
import hashlib
import io
import json
import platform
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BACKEND = ROOT / "15_SYSTEM" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(BACKEND))
import backup_proof  # noqa: E402
import common  # noqa: E402
from backend import crypto, vault  # noqa: E402

PLANES = (".brain-data", ".kb")
PREFIXES = tuple("%s/" % plane for plane in PLANES)
KEY = b"four-word-phrase-that-nobody-typed-into-argv\n"


def sandbox(planes=PLANES, hold=()):
    """A repo-shaped sandbox: a config, and the private planes only if someone held them."""
    root = Path(tempfile.mkdtemp(prefix="proof-sandbox-"))
    config = root / vault.CONFIG
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"private_planes": list(planes),
                                  "feature_flags": {"encrypted_private_backup": False}}),
                      encoding="utf-8")
    for rel in hold:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"a note that was here before this proof ran\n")
    return root


def outside():
    """Where a passphrase, an envelope or a destination may live: never inside the repo."""
    return Path(tempfile.mkdtemp(prefix="proof-outside-"))


def run(argv, root=None):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = backup_proof.main([str(arg) for arg in argv], root=root)
    return code, buffer.getvalue()


def keyfile():
    path = outside() / "passphrase"
    path.write_bytes(KEY)
    return path


def sealed(kdf=crypto.KDF_PBKDF2, ci_run=None, planes=PLANES, hold=()):
    """The whole A-side: fixture then seal. Returns (root, key, envelope path, seal output)."""
    root = sandbox(planes, hold=hold)
    key = keyfile()
    envelope = outside() / "envelope.json"
    code, out = run(["--fixture", "--root", root])
    assert code == backup_proof.EXIT_OK, out
    argv = ["--seal", "--root", root, "--passphrase-file", key, "--envelope", envelope,
            "--kdf", kdf]
    if ci_run:
        argv += ["--ci-run", ci_run]
    code, out = run(argv)
    assert code == backup_proof.EXIT_OK, out
    return root, key, envelope, out


def envelope_of(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def files_under(directory):
    base = Path(directory)
    if not base.is_dir():
        return []
    return sorted(path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file())


def plane_files(directory):
    return [rel for rel in files_under(directory) if rel.startswith(PREFIXES)]


class TheFixtureIsSynthetic(unittest.TestCase):
    def test_the_fixture_writes_only_its_own_generated_bytes(self):
        root, _key, _envelope, _out = sealed()
        written = plane_files(root)
        self.assertEqual(2 * len(backup_proof.FIXTURE_LEAVES), len(written))
        for rel in written:
            body = (root / rel).read_bytes()
            self.assertIn(b"Synthetic content", body)
            self.assertIn(b"Not personal data", body)
            self.assertIn(rel.encode("utf-8"), body)

    def test_the_fixture_refuses_a_plane_that_already_holds_files(self):
        root = sandbox(hold=(".kb/documents/real-note.md",))
        code, out = run(["--fixture", "--root", root])
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("REFUSED: private plane .kb already holds files", out)
        self.assertEqual(["documents/real-note.md"], files_under(root / ".kb"))
        self.assertFalse((root / ".brain-data").exists())

    def test_an_explicit_root_wins_over_the_checkout_the_script_lives_in(self):
        """Regression: the sandbox is what gets touched, never the repository running the test."""
        root = sandbox()
        code, out = run(["--fixture", "--root", root])
        self.assertEqual(backup_proof.EXIT_OK, code)
        self.assertEqual(6, len(plane_files(root)))
        self.assertNotIn(str(ROOT), out)


class TheSealSideRefuses(unittest.TestCase):
    def test_sealing_an_absent_plane_is_refused_rather_than_skipped(self):
        root = sandbox()
        code, out = run(["--seal", "--root", root, "--passphrase-file", keyfile(),
                         "--envelope", outside() / "envelope.json"])
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("declared private plane(s) absent", out)
        self.assertIn(".brain-data", out)

    def test_a_plane_that_holds_no_bytes_is_refused_not_reported_as_backed_up(self):
        root, key, envelope, _out = sealed()
        data = envelope_of(envelope)
        for path in (root / PLANES[1]).rglob("*"):
            if path.is_file():
                path.unlink()
        code, out = run(["--seal", "--root", root, "--passphrase-file", key,
                         "--envelope", outside() / "envelope.json"])
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("hold no bytes", out)
        self.assertIn(PLANES[1], out)
        self.assertEqual(1, len(list((root / vault.SHELF).glob("priv-*" + vault.SUFFIX))))
        self.assertEqual(data["files"], envelope_of(envelope)["files"])

    def test_a_passphrase_inside_the_repository_is_refused(self):
        root = sandbox()
        code, out = run(["--fixture", "--root", root])
        self.assertEqual(backup_proof.EXIT_OK, code)
        inside = root / "passphrase"
        inside.write_bytes(KEY)
        code, out = run(["--seal", "--root", root, "--passphrase-file", inside,
                         "--envelope", outside() / "envelope.json"])
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("passphrase source", out)

    def test_an_envelope_inside_the_repository_is_refused_on_both_sides(self):
        """Self-issued evidence is the failure this whole script is built against."""
        root = sandbox()
        code, out = run(["--fixture", "--root", root])
        self.assertEqual(backup_proof.EXIT_OK, code)
        inside = root / "envelope.json"
        code, out = run(["--seal", "--root", root, "--passphrase-file", keyfile(),
                         "--envelope", inside])
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("resolves inside the repository", out)
        self.assertFalse(inside.exists())
        code, out = run(["--restore", "--root", root, "--envelope", inside,
                         "--passphrase-file", keyfile(), "--into", outside() / "back"])
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("resolves inside the repository", out)

    def test_a_seal_does_not_overwrite_the_envelope_it_is_about_to_claim(self):
        root, key, envelope, _out = sealed()
        code, out = run(["--seal", "--root", root, "--passphrase-file", key,
                         "--envelope", envelope])
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("does not overwrite the numbers", out)

    def test_the_seal_reports_honestly_and_writes_no_witness(self):
        root, _key, envelope, out = sealed(ci_run="87654321")
        self.assertIn("CIPHER %s" % vault.CIPHER_CLAIM, out)
        self.assertIn("NOT EVIDENCE YET", out)
        self.assertIn("encrypted_private_backup is", out)
        self.assertEqual([], files_under(root / "11_CONTROL"))
        self.assertEqual("87654321", envelope_of(envelope)["ci_run"])

    def test_a_local_run_names_itself_as_not_a_ci_run(self):
        _root, _key, envelope, _out = sealed()
        self.assertEqual(backup_proof.NOT_A_CI_RUN, envelope_of(envelope)["ci_run"])


class TheEnvelopeAnswersEveryQuestion(unittest.TestCase):
    def test_it_carries_every_key_the_restore_side_reads(self):
        root, _key, envelope, out = sealed()
        data = envelope_of(envelope)
        self.assertEqual([], [key for key in backup_proof.ENVELOPE_KEYS if key not in data])
        self.assertNotIn("id", data)
        self.assertNotIn("kind", data)
        self.assertEqual(list(PLANES), data["planes"])
        self.assertEqual(len(backup_proof.FIXTURE_LEAVES) * 2, data["files"])
        self.assertIn("ON host=%s" % data["sealed_on"], out)
        self.assertIn("PLANES .brain-data, .kb plane_digest=%s" % data["plane_digest"], out)

    def test_the_container_digest_is_measured_on_the_shelf_not_trusted_from_the_row(self):
        root, _key, envelope, _out = sealed()
        data = envelope_of(envelope)
        blob = vault.container_path(root, data["name"]).read_bytes()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), data["container_sha256"])
        self.assertEqual(crypto.container_digest(blob), data["container_sha256"])

    def test_the_plane_digest_is_the_rule_the_base_ledger_already_uses(self):
        """One digest rule for the whole proof: the fingerprint `scripts/base.py` compares."""
        root, _key, envelope, _out = sealed()
        data = envelope_of(envelope)
        inventory = {}
        for rel in plane_files(root):
            inventory[rel] = hashlib.sha1((root / rel).read_bytes()).hexdigest()
        self.assertEqual(len(plane_files(root)), data["files"])
        self.assertEqual(common.fingerprint_of_inventory(inventory), data["plane_digest"])


class TheRestoreSideRefuses(unittest.TestCase):
    def restore(self, root, key, envelope, into=None, extra=()):
        argv = ["--restore", "--root", root, "--envelope", envelope,
                "--passphrase-file", key, "--into", into if into is not None else outside() / "b"]
        return run(argv + list(extra))

    def test_a_run_on_the_sealing_machine_is_refused_without_the_flag(self):
        root, key, envelope, _out = sealed()
        into = outside() / "back"
        code, out = self.restore(root, key, envelope, into)
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("which is also where the container was sealed", out)
        self.assertEqual([], files_under(into))

    def test_the_same_machine_with_the_flag_reports_itself_as_not_evidence(self):
        root, key, envelope, _out = sealed()
        into = outside() / "back"
        code, out = self.restore(root, key, envelope, into, ("--allow-same-machine",))
        self.assertEqual(backup_proof.EXIT_OK, code)
        self.assertIn("CROSS_MACHINE false", out)
        self.assertIn("NOT EVIDENCE", out)
        self.assertEqual(plane_files(root), plane_files(into))

    def test_a_different_host_makes_the_same_run_a_cross_machine_proof(self):
        """Patching the host name exercises the branch; it does not manufacture evidence.

        The witness that opens the door is the CI pair on two OS images and its run id, not a test
        that can rename its own machine.
        """
        root, key, envelope, _out = sealed()
        into = outside() / "back"
        with patch.object(backup_proof.platform, "node", return_value="machine-ietl"):
            code, out = self.restore(root, key, envelope, into)
        self.assertEqual(backup_proof.EXIT_OK, code)
        self.assertIn("CROSS_MACHINE true", out)
        self.assertIn("PROOF bytes written on", out)
        self.assertNotIn("NOT EVIDENCE", out)
        self.assertIn("machine-ietl", out)
        self.assertNotEqual(envelope_of(envelope)["sealed_on"], "machine-ietl")

    def test_the_witness_draft_keeps_the_human_in_the_loop(self):
        root, key, envelope, _out = sealed()
        into = outside() / "back"
        code, out = self.restore(root, key, envelope, into, ("--allow-same-machine", "--witness"))
        self.assertEqual(backup_proof.EXIT_OK, code)
        self.assertIn("WITNESS DRAFT", out)
        draft = json.loads(out.split("WITNESS DRAFT", 1)[1].split("\n", 1)[1])
        self.assertEqual("roundtrip_pending", draft["verdict"])
        self.assertIsNone(draft["approved_by"])
        self.assertEqual(envelope_of(envelope)["container_sha256"], draft["container_sha256"])
        self.assertEqual([], files_under(root / "11_CONTROL"))

    def test_a_container_copied_to_a_root_that_never_sealed_reopens_there(self):
        first, key, envelope, _out = sealed()
        data = envelope_of(envelope)
        blob = vault.container_path(first, data["name"]).read_bytes()
        second = sandbox()
        code, out = run(["--fixture", "--root", second])
        self.assertEqual(backup_proof.EXIT_OK, code)
        shelf = vault.container_path(second, data["name"])
        shelf.parent.mkdir(parents=True, exist_ok=True)
        shelf.write_bytes(blob)
        into = outside() / "elsewhere"
        with patch.object(backup_proof.platform, "node", return_value="machine-ietl"):
            code, out = self.restore(second, key, envelope, into)
        self.assertEqual(backup_proof.EXIT_OK, code, out)
        self.assertEqual(plane_files(second), plane_files(into))
        for rel in plane_files(second):
            self.assertEqual((second / rel).read_bytes(), (into / rel).read_bytes())

    def test_a_wrong_passphrase_moves_nothing_and_names_the_failure(self):
        root, _key, envelope, _out = sealed()
        wrong = outside() / "pass"
        wrong.write_bytes(b"the-phrase-i-guessed\n")
        into = outside() / "back"
        code, out = self.restore(root, wrong, envelope, into, ("--allow-same-machine",))
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("REFUSED: the container did not come back", out)
        self.assertIn("NOTHING MOVED a failed restore placed 0 file(s)", out)
        self.assertEqual([], files_under(into))

    def test_a_tampered_container_is_refused_and_leaves_no_mixed_generation(self):
        root, key, envelope, _out = sealed()
        data = envelope_of(envelope)
        path = vault.container_path(root, data["name"])
        blob = bytearray(path.read_bytes())
        blob[len(blob) // 2] ^= 0x01
        path.write_bytes(bytes(blob))
        into = outside() / "back"
        code, out = self.restore(root, key, envelope, into, ("--allow-same-machine",))
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("NOTHING MOVED a failed restore placed 0 file(s)", out)
        self.assertEqual([], files_under(into))

    def test_an_envelope_missing_a_key_is_refused_by_name(self):
        root, key, envelope, _out = sealed()
        data = envelope_of(envelope)
        del data["plane_digest"]
        envelope.write_text(json.dumps(data), encoding="utf-8")
        code, out = self.restore(root, key, envelope, extra=("--allow-same-machine",))
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("carries no plane_digest", out)

    def test_an_envelope_from_another_format_version_is_refused(self):
        root, key, envelope, _out = sealed()
        data = envelope_of(envelope)
        data["cipher"] = "SBO2-1 ChaCha20-Poly1305"
        envelope.write_text(json.dumps(data), encoding="utf-8")
        code, out = self.restore(root, key, envelope, extra=("--allow-same-machine",))
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("another format version is not evidence for this one", out)

    def test_a_destination_that_already_holds_files_is_refused(self):
        root, key, envelope, _out = sealed()
        into = outside() / "already-there"
        into.mkdir()
        (into / "x").write_bytes(b"mine\n")
        code, out = self.restore(root, key, envelope, into, ("--allow-same-machine",))
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("already holds files", out)
        self.assertEqual(["x"], files_under(into))

    def test_a_missing_envelope_is_refused_rather_than_guessed(self):
        root, key, _envelope, _out = sealed()
        code, out = self.restore(root, key, outside() / "ghost.json",
                                 extra=("--allow-same-machine",))
        self.assertEqual(backup_proof.EXIT_REFUSED, code)
        self.assertIn("is not a file", out)


class TheParserRefusesBeforeAnythingRuns(unittest.TestCase):
    def test_no_command_and_two_commands_are_both_usage_errors(self):
        self.assertEqual(backup_proof.EXIT_USAGE, run([])[0])
        code, out = run(["--seal", "--restore"])
        self.assertEqual(backup_proof.EXIT_USAGE, code)
        self.assertIn("exactly one of", out)

    def test_unknown_and_value_less_flags_are_usage_errors(self):
        for argv in (["--seal", "--passphrase"], ["--seal", "--passphrase-file"],
                     ["--fixture", "--nope"]):
            code, out = run(argv)
            self.assertEqual(backup_proof.EXIT_USAGE, code, argv)
            self.assertIn("USAGE:", out)

    def test_the_passphrase_is_never_a_value_the_command_line_can_carry(self):
        source = (SCRIPTS / "backup_proof.py").read_text(encoding="utf-8")
        self.assertNotIn("--passphrase ", source)
        self.assertIn('"--passphrase-file"', source)


class TheCiPairIsDeclaredOnTwoMachines(unittest.TestCase):
    """The job pair is the only independent witness of *where* a seal happened.

    A host name is self-reported, so the door needs two OS images and a run id. These assertions
    read the workflow instead of running it; `scripts/ci_floor.py` keeps the images honest.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    def test_the_seal_job_uploads_and_the_restore_job_downloads(self):
        self.assertIn("backup-seal:", self.text)
        self.assertIn("backup-restore:", self.text)
        self.assertIn("actions/upload-artifact@", self.text)
        self.assertIn("actions/download-artifact@", self.text)
        self.assertLess(self.text.index("backup-seal:"), self.text.index("backup-restore:"))
        self.assertIn("needs: [test, backup-seal]", self.text)

    def test_the_proof_runs_the_real_commands_on_both_sides(self):
        self.assertIn("backup_proof.py --fixture", self.text)
        self.assertIn("backup_proof.py --seal", self.text)
        self.assertIn("backup_proof.py --restore", self.text)
        self.assertIn("github.run_id", self.text)

    def test_the_passphrase_reaches_the_proof_from_a_file_and_never_argv(self):
        self.assertIn("--passphrase-file", self.text)
        self.assertNotIn("--passphrase ", self.text)

    def test_the_restore_job_may_not_certify_its_own_machine(self):
        self.assertNotIn("--allow-same-machine", self.text)
        self.assertIn("backup_proof.py --restore", self.text)

    def test_no_artifact_and_no_witness_is_committed(self):
        self.assertNotIn("11_CONTROL", self.text)
        self.assertIn("retention-days: 1", self.text)
        self.assertNotIn(vault.SUFFIX + "\n      - name", self.text)
        self.assertFalse((ROOT / vault.EVIDENCE).exists())
        self.assertFalse(list((ROOT / vault.SHELF).glob("*" + vault.SUFFIX)))


class TheRepositoryBoundaryHolds(unittest.TestCase):
    def test_no_run_of_the_proof_writes_inside_the_repo_or_opens_the_door(self):
        root, key, envelope, _out = sealed()
        into = outside() / "back"
        run(["--restore", "--root", root, "--envelope", envelope, "--passphrase-file", key,
             "--into", into, "--allow-same-machine", "--witness"])
        self.assertEqual([], files_under(root / "11_CONTROL"))
        cfg = json.loads((root / vault.CONFIG).read_text(encoding="utf-8"))
        self.assertFalse(cfg["feature_flags"]["encrypted_private_backup"])
        shelf = sorted(path.name for path in (root / vault.SHELF).iterdir())
        self.assertTrue(all(name.endswith(vault.SUFFIX) or name == "index.jsonl"
                            for name in shelf), shelf)

    def test_the_real_checkout_keeps_the_door_closed_while_this_ships(self):
        cfg = json.loads((ROOT / "15_SYSTEM" / "config" / "system.json").read_text(
            encoding="utf-8"))
        self.assertFalse(cfg["feature_flags"]["encrypted_private_backup"])

    def test_the_host_law_reads_the_platform_and_not_an_option(self):
        _root, _key, envelope, _out = sealed()
        self.assertEqual(platform.node(), envelope_of(envelope)["sealed_on"])
        self.assertNotIn("host", backup_proof.VALUE_FLAGS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
