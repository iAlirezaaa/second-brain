"""Phase 52 -- the vault seals the private planes, and the gate only opens on a witness.

Charter section 8 asks for two things in one breath: encrypted backup and a regular restore
test. `crypto.py` (phase 51) is the codec; `backend/vault.py` is the seam between that codec and
the real files; `scripts/vault.py` is the only CLI over it; `scripts/vault_check.py` is the door
that refuses to let the repo *say* the private planes are backed up until a second machine has
proven it can read them. The flag `encrypted_private_backup` ships false, so nothing here touches
the owner's vault until the owner asks.

What these tests hold, in order of the harm each prevents:

* A seal that silently drops a file is worse than no backup, because it is trusted. So a symlink,
  an over-large file, a plane that would swallow the shelf, or an empty scope is a *named* refusal.
* A restore that half-writes leaves a vault of mixed generations -- invisible to its owner. So a
  failed open writes nothing at all.
* A key in a command line is a key in a process list and a CI log. So the only key sources are a
  terminal and a file outside the repository, and there is no option to take a third.
* The gate is satisfied by shape, never by a name, and never touches a key -- a gate that needed
  a passphrase would be skipped, and a skipped gate says "fine" about a disaster.
"""
import ast
import hashlib
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
sys.path.insert(0, str(SCRIPTS))
from backend import crypto, vault  # noqa: E402
import common  # noqa: E402

PLANES = [".brain-data", ".kb"]
FILES = {
    ".brain-data/index.json": '{"notes": 3, "synced": false}\n',
    ".brain-data/notes/note-one.md": "# note one\n\nthe thing I did not want to forget\n",
    ".brain-data/sub/deep/two.md": "# note two\n",
    ".kb/documents/doc-a.md": "# doc a\n",
}
KEY = b"four-word-phrase-that-nobody-typed-into-argv\n"
ABSENT = object()

GOOD_EVIDENCE = {
    "verdict": "roundtrip_verified",
    "cipher": vault.CIPHER_CLAIM,
    "kdf": crypto.KDF_PBKDF2,
    "container_sha256": "a" * 64,
    "files": 4,
    "bytes": 3540,
    "sealed_on": "machine-sequoia",
    "restored_on": "machine-ietl",
    "python_sealed": "3.9.13",
    "python_restored": "3.12.7",
    "ci_run": "12345678",
    "approved_by": "owner",
    "approved_at": "2026-11-02",
}


def fixture(planes=ABSENT, flag=False, evidence=None, files=ABSENT):
    """A repo-shaped sandbox: config, private planes, and nothing else."""
    root = Path(tempfile.mkdtemp(prefix="vault-fixture-"))
    config = root / vault.CONFIG
    config.parent.mkdir(parents=True, exist_ok=True)
    data = {"feature_flags": {"encrypted_private_backup": flag}}
    if planes is not ABSENT or True:
        data["private_planes"] = PLANES if planes is ABSENT else planes
    if planes is None:
        del data["private_planes"]
    config.write_text(json.dumps(data), encoding="utf-8")
    for rel, text in (FILES if files is ABSENT else files).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    if evidence is not None:
        path = root / vault.EVIDENCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence), encoding="utf-8")
    return root


def keyfile():
    """A key kept where the repository cannot see it -- which is the whole rule."""
    directory = Path(tempfile.mkdtemp(prefix="vault-key-"))
    path = directory / "passphrase"
    path.write_bytes(KEY)
    return path


def digests(root):
    measured = {}
    for rel in FILES:
        path = Path(root) / rel
        if path.is_file():
            measured[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return measured


def sealed_name(line):
    """`sealed 20261102T201530Z: 4 files ...` -- the stamp is the second word, colon and all."""
    return line.split()[1].rstrip(":")


def shelf_copy(root, name, source):
    """The way bytes arrive on a machine that has never sealed: copied in, shelf and all.

    A fresh fixture has no shelf directory, so writing straight to `container_path` would raise
    `FileNotFoundError` and the test would measure the harness instead of the vault.
    """
    path = vault.container_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source)
    return path


def cli(args):
    """The real command, with stdin closed: a test must never hang waiting for a passphrase."""
    argv = [sys.executable, str(SCRIPTS / "vault.py")] + [str(a) for a in args]
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", stdin=subprocess.DEVNULL, cwd=str(ROOT))


def gate(args):
    argv = [sys.executable, str(SCRIPTS / "vault_check.py")] + [str(a) for a in args]
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT))


class TheRoundTrip(unittest.TestCase):
    def test_seal_verify_restore_returns_the_same_bytes(self):
        root = fixture()
        row = vault.seal(root, KEY, crypto.KDF_PBKDF2)
        self.assertEqual(len(FILES), row["files"])
        self.assertEqual(sum(len(t) for t in FILES.values()), row["plain_bytes"])
        report = vault.verify(root, row["name"], KEY)
        self.assertEqual(row["container_sha256"], report["container_sha256"])
        self.assertEqual(sorted(FILES), sorted(rel for rel, _size in report["entries"]))
        into = Path(tempfile.mkdtemp(prefix="vault-into-"))
        restored = vault.restore(root, row["name"], into, KEY)
        self.assertEqual(digests(root), digests(into))
        self.assertEqual(restored["container_sha256"], row["container_sha256"])

    def test_a_container_moved_to_another_root_reopens_there(self):
        """The claim this feature exists for: bytes that another machine has never seen."""
        first = fixture()
        row = vault.seal(first, KEY, crypto.KDF_PBKDF2)
        source = vault.container_path(first, row["name"]).read_bytes()
        second = fixture()
        self.assertEqual(0, len(vault.rows(second)))
        shelf_copy(second, row["name"], source)
        into = Path(tempfile.mkdtemp(prefix="vault-elsewhere-"))
        report = vault.restore(second, row["name"], into, KEY)
        self.assertEqual(row["container_sha256"], report["container_sha256"])
        self.assertEqual(digests(first), digests(into))

    def test_sealing_writes_only_to_the_shelf_and_never_into_a_plane(self):
        root = fixture()
        before = sorted(p.as_posix() for p in (root / PLANES[0]).rglob("*") if p.is_file())
        vault.seal(root, KEY, crypto.KDF_PBKDF2)
        after = sorted(p.as_posix() for p in (root / PLANES[0]).rglob("*") if p.is_file())
        self.assertEqual(before, after)
        self.assertEqual(1, len(list((root / vault.SHELF).glob("priv-*" + vault.SUFFIX))))

    def test_the_journal_keeps_every_seal_while_the_shelf_rotates_bytes(self):
        root = fixture()
        for index in range(7):
            with patch.object(vault, "stamp", return_value="20261102T2015%02dZ" % index):
                vault.seal(root, KEY, crypto.KDF_PBKDF2)
        self.assertEqual(7, len(vault.rows(root)))
        self.assertEqual(vault.KEEP, len(list((root / vault.SHELF).glob("priv-*" + vault.SUFFIX))))

    def test_the_cli_body_and_the_api_agree(self):
        root = fixture()
        key = keyfile()
        lines = vault.run(["--seal", "--root", str(root), "--passphrase-file", str(key),
                           "--kdf", crypto.KDF_PBKDF2], str(root))
        self.assertTrue(any(line.startswith("sealed ") for line in lines), lines)
        name = sealed_name(lines[0])
        listed = vault.run(["--list", "--root", str(root)], str(root))
        self.assertTrue(any(name in line and "frames" in line for line in listed), listed)
        status = vault.run(["--status", "--root", str(root)], str(root))
        self.assertEqual("encrypted_private_backup: inert", status[0])
        into = Path(tempfile.mkdtemp(prefix="vault-cli-into-"))
        unsealed = vault.run(["--unseal", name, "--into", str(into), "--root", str(root),
                              "--passphrase-file", str(key)], str(root))
        self.assertTrue(unsealed[0].startswith("restored "), unsealed)
        self.assertEqual(digests(root), digests(into))


class RefusalsNameTheirRule(unittest.TestCase):
    def assert_refused(self, call, rule):
        with self.assertRaises(vault.VaultError) as caught:
            call()
        self.assertEqual(rule, caught.exception.rule)
        self.assertIn("rule: %s" % rule, str(caught.exception))

    def test_a_private_planes_list_that_is_not_a_path_set_is_refused(self):
        for planes in ([], None, ".brain-data", [".."], ["/etc"], ["a/../b"], [""]):
            root = fixture(planes=planes)
            self.assert_refused(lambda: vault.collect(root), "plane scope")

    def test_a_scope_that_seals_nothing_is_refused_rather_than_reported_as_success(self):
        root = fixture(files={})
        for plane in PLANES:
            (root / plane).mkdir(parents=True, exist_ok=True)
        self.assert_refused(lambda: vault.collect(root), "empty scope")

    def test_a_plane_that_would_contain_the_shelf_is_refused(self):
        for plane in ("15_SYSTEM/backups", "15_SYSTEM"):
            root = fixture(planes=[plane])
            self.assert_refused(lambda: vault.collect(root), "shelf in scope")

    def test_a_file_beyond_the_frame_cap_is_refused_not_left_out(self):
        root = fixture()
        with patch.object(crypto, "MAX_FRAME_BYTES", 16):
            self.assert_refused(lambda: vault.collect(root), "frame cap")

    def test_a_symlink_in_scope_is_refused_not_followed(self):
        root = fixture()
        link = root / PLANES[0] / "pointer.md"
        try:
            os.symlink(str(root / PLANES[0] / "index.json"), str(link))
        except (OSError, NotImplementedError):
            self.skipTest("this platform will not let a test create a symlink")
        self.assert_refused(lambda: vault.collect(root), "symlink in scope")

    def test_a_container_name_that_is_not_a_stamp_is_refused(self):
        root = fixture()
        for name in ("../../evil", "priv-1.sbo1", "", "2026-11-02", "123456789012345"):
            self.assert_refused(lambda: vault.container_path(root, name), "container name")

    def test_a_container_that_is_not_on_the_shelf_names_what_the_shelf_holds(self):
        root = fixture()
        row = vault.seal(root, KEY, crypto.KDF_PBKDF2)
        with self.assertRaises(vault.VaultError) as caught:
            vault.verify(root, "20200101T000000Z", KEY)
        self.assertEqual("container missing", caught.exception.rule)
        self.assertIn(row["name"], str(caught.exception))

    def test_two_seals_in_one_second_refuse_to_overwrite_each_other(self):
        root = fixture()
        with patch.object(vault, "stamp", return_value="20261102T201530Z"):
            vault.seal(root, KEY, crypto.KDF_PBKDF2)
            self.assert_refused(lambda: vault.seal(root, KEY, crypto.KDF_PBKDF2),
                                "refuse to overwrite")
        self.assertEqual(1, len(list((root / vault.SHELF).glob("priv-*" + vault.SUFFIX))))

    def test_an_empty_passphrase_is_refused(self):
        root = fixture()
        self.assert_refused(lambda: vault.seal(root, b""), "passphrase source")

    def test_a_key_file_inside_the_repository_is_refused(self):
        root = fixture()
        inside = root / "my-key.txt"
        inside.write_bytes(KEY)
        self.assert_refused(lambda: vault.passphrase_from_file(str(inside), str(root)),
                            "passphrase source")
        self.assert_refused(lambda: vault.passphrase_from_file(str(root / "absent.txt"),
                                                               str(root)), "passphrase source")

    def test_unseal_without_a_destination_is_refused(self):
        root = fixture()
        key = keyfile()
        vault.run(["--seal", "--root", str(root), "--passphrase-file", str(key),
                   "--kdf", crypto.KDF_PBKDF2], str(root))
        name = vault.rows(root)[-1]["name"]
        with self.assertRaises(vault.VaultError) as caught:
            vault.run(["--unseal", name, "--root", str(root),
                       "--passphrase-file", str(key)], str(root))
        self.assertEqual("refuse to overwrite", caught.exception.rule)

    def test_restore_refuses_to_overwrite_the_live_plane(self):
        root = fixture()
        row = vault.seal(root, KEY, crypto.KDF_PBKDF2)
        self.assert_refused(lambda: vault.restore(root, row["name"], root, KEY),
                            "refuse to overwrite")

    def test_a_refusal_can_only_name_a_declared_rule(self):
        with self.assertRaises(AssertionError):
            vault.VaultError("invented", "some rule nobody declared")
        source = (BACKEND / "backend" / "vault.py").read_text(encoding="utf-8")
        used = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "VaultError":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    used.add(node.args[1].value)
        self.assertEqual(set(vault.RULES), used,
                         "a rule declared and never used, or used and never declared")


class ADamagedContainerIsStillOnTheShelf(unittest.TestCase):
    def test_verify_refuses_a_truncated_container_by_rule(self):
        root = fixture()
        row = vault.seal(root, KEY, crypto.KDF_PBKDF2)
        path = vault.container_path(root, row["name"])
        path.write_bytes(path.read_bytes()[:-8])
        with self.assertRaises(crypto.OpenError) as caught:
            vault.verify(root, row["name"], KEY)
        self.assertEqual("truncated", caught.exception.rule)

    def test_list_names_the_unreadable_container_and_keeps_listing(self):
        root = fixture()
        good = vault.seal(root, KEY, crypto.KDF_PBKDF2)
        with patch.object(vault, "stamp", return_value="20261102T201630Z"):
            bad = vault.seal(root, KEY, crypto.KDF_PBKDF2)
        path = vault.container_path(root, bad["name"])
        path.write_bytes(path.read_bytes()[:200])
        text = "\n".join(vault.run(["--list", "--root", str(root)], str(root)))
        self.assertIn("%s  UNREADABLE" % bad["name"], text)
        self.assertIn(good["name"], text)

    def test_a_wrong_passphrase_writes_nothing_at_the_destination(self):
        root = fixture()
        row = vault.seal(root, KEY, crypto.KDF_PBKDF2)
        into = Path(tempfile.mkdtemp(prefix="vault-empty-"))
        with self.assertRaises(crypto.OpenError) as caught:
            vault.restore(root, row["name"], into, b"not-the-phrase")
        self.assertEqual("tag", caught.exception.rule)
        leftovers = [p for p in into.rglob("*") if p.name.endswith(".tmp") or p.is_file()]
        self.assertEqual([], leftovers)

    def test_a_spliced_container_opens_as_nothing(self):
        root = fixture()
        row = vault.seal(root, KEY, crypto.KDF_PBKDF2)
        path = vault.container_path(root, row["name"])
        blob = bytearray(path.read_bytes())
        blob[len(blob) // 2] ^= 0x01
        path.write_bytes(bytes(blob))
        with self.assertRaises(crypto.OpenError):
            vault.verify(root, row["name"], KEY)

    def test_a_container_the_journal_never_recorded_is_still_openable(self):
        """`verify` compares against the journal row; a container copied in from another
        machine has no row here, and that must not read as forgery."""
        first = fixture()
        row = vault.seal(first, KEY, crypto.KDF_PBKDF2)
        second = fixture()
        shelf_copy(second, row["name"], vault.container_path(first, row["name"]).read_bytes())
        report = vault.verify(second, row["name"], KEY)
        self.assertEqual(row["container_sha256"], report["container_sha256"])


class TheGateJudgesShape(unittest.TestCase):
    def test_off_is_honest_and_names_the_flag(self):
        state = vault.gate(fixture())
        self.assertFalse(state["active"])
        self.assertIs(False, state["flag"])
        self.assertIn("feature_flags.encrypted_private_backup is false", state["problems"])

    def test_on_without_a_witness_is_refused_by_name(self):
        state = vault.gate(fixture(flag=True))
        self.assertFalse(state["active"])
        self.assertTrue(any(vault.EVIDENCE.as_posix() in problem for problem in state["problems"]),
                        state["problems"])

    def test_a_witness_from_one_machine_is_not_a_round_trip(self):
        same = dict(GOOD_EVIDENCE, sealed_on="Machine-IETL", restored_on="machine-ietl")
        state = vault.gate(fixture(flag=True, evidence=same))
        self.assertFalse(state["active"])
        self.assertTrue(any("sealed_on == restored_on" in problem
                            for problem in state["problems"]), state["problems"])

    def test_each_witness_defect_is_refused_by_its_own_name(self):
        defects = [
            (dict(GOOD_EVIDENCE, verdict="i_trust_it"), "verdict"),
            (dict(GOOD_EVIDENCE, cipher="SBO2 ChaCha20-Poly1305"), "cipher"),
            (dict(GOOD_EVIDENCE, kdf="aes-256-cbc"), "kdf"),
            (dict(GOOD_EVIDENCE, container_sha256="deadbeef"), "container_sha256"),
            (dict(GOOD_EVIDENCE, files=0), "files"),
            (dict(GOOD_EVIDENCE, bytes=True), "bytes"),
            (dict(GOOD_EVIDENCE, python_restored="soon"), "python_restored"),
            (dict(GOOD_EVIDENCE, ci_run="trust me"), "ci_run"),
            (dict(GOOD_EVIDENCE, approved_by=""), "approved_by"),
            (dict(GOOD_EVIDENCE, approved_at="last tuesday"), "approved_at"),
            (dict(GOOD_EVIDENCE, restored_on=""), "must both name a machine"),
        ]
        for evidence, needle in defects:
            state = vault.gate(fixture(flag=True, evidence=evidence))
            self.assertFalse(state["active"], evidence)
            self.assertTrue(any(needle in problem for problem in state["problems"]),
                            "%r not named in %s" % (needle, state["problems"]))

    def test_a_missing_key_is_named_not_defaulted(self):
        evidence = dict(GOOD_EVIDENCE)
        del evidence["container_sha256"]
        del evidence["approved_by"]
        state = vault.gate(fixture(flag=True, evidence=evidence))
        joined = " ".join(state["problems"])
        self.assertIn("evidence is missing", joined)
        self.assertIn("container_sha256", joined)
        self.assertIn("approved_by", joined)
        self.assertEqual(1, len(state["problems"]))

    def test_an_unreadable_witness_is_a_refusal_not_a_traceback(self):
        root = fixture(flag=True)
        path = root / vault.EVIDENCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        state = vault.gate(root)
        self.assertFalse(state["active"])
        self.assertIn("evidence is unreadable", " ".join(state["problems"]))

    def test_a_config_without_planes_names_the_plane_law(self):
        state = vault.gate(fixture(planes=None, flag=True, evidence=GOOD_EVIDENCE))
        self.assertFalse(state["active"])
        self.assertIn("plane scope", " ".join(state["problems"]))

    def test_a_complete_witness_from_two_machines_opens_the_door(self):
        state = vault.gate(fixture(flag=True, evidence=GOOD_EVIDENCE))
        self.assertTrue(state["active"], state["problems"])
        self.assertEqual(PLANES, state["private_planes"])
        self.assertEqual(vault.EVIDENCE.as_posix(), state["evidence"])

    def test_the_gate_never_derives_a_key_or_opens_a_container(self):
        def refuse(*_args, **_kwargs):
            raise AssertionError("the gate touched a key")
        root = fixture(flag=True, evidence=GOOD_EVIDENCE)
        with patch.object(crypto, "kdf_derive", refuse), \
                patch.object(crypto, "open_container", refuse), \
                patch.object(socket, "socket", refuse):
            state = vault.gate(root)
            status = vault.status(root)
        self.assertTrue(state["active"])
        self.assertTrue(status["active"])

    def test_the_vault_imports_only_the_standard_library_and_its_sibling(self):
        tree = ast.parse((BACKEND / "backend" / "vault.py").read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])
        self.assertLessEqual(imports, {"hashlib", "json", "os", "platform", "re", "sys", "time",
                                       "datetime", "pathlib", "argparse", "getpass", "common",
                                       "crypto"})
        self.assertNotIn("socket", imports)

    def test_the_backend_module_has_no_dispatch_of_its_own(self):
        """One CLI, one usage text, one rule list: `scripts/vault.py` owns the surface."""
        source = (BACKEND / "backend" / "vault.py").read_text(encoding="utf-8")
        self.assertNotIn("def main(", source)
        self.assertNotIn("__main__", source)
        cli_source = (SCRIPTS / "vault.py").read_text(encoding="utf-8")
        self.assertIn("vault.RULES", cli_source)
        self.assertIn("crypto.run_selftest", cli_source)


class TheCommandsSayTheSameThing(unittest.TestCase):
    def test_no_arguments_prints_the_usage_and_the_rules(self):
        result = cli([])
        self.assertEqual(2, result.returncode)
        self.assertIn("usage: python scripts/vault.py", result.stdout)
        for rule in vault.RULES:
            self.assertIn(rule, result.stdout)

    def test_the_selftest_of_the_primitive_is_reachable_through_the_cli(self):
        result = cli(["--selftest"])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("selftest passed", result.stdout)

    def test_a_seal_whose_key_never_reached_argv_and_a_restore_of_it(self):
        root = fixture()
        key = keyfile()
        sealed = cli(["--seal", "--root", root, "--passphrase-file", key,
                      "--kdf", crypto.KDF_PBKDF2])
        self.assertEqual(0, sealed.returncode, sealed.stdout + sealed.stderr)
        self.assertIn("sha256 (of the ciphertext):", sealed.stdout)
        first = [line for line in sealed.stdout.splitlines() if line.startswith("sealed ")][0]
        name = sealed_name(first)
        verified = cli(["--verify", name, "--root", root, "--passphrase-file", key])
        self.assertEqual(0, verified.returncode, verified.stdout)
        self.assertIn("every frame authenticated", verified.stdout)
        into = Path(tempfile.mkdtemp(prefix="vault-sub-into-"))
        unsealed = cli(["--unseal", name, "--into", into, "--root", root,
                        "--passphrase-file", key])
        self.assertEqual(0, unsealed.returncode, unsealed.stdout)
        self.assertEqual(digests(root), digests(into))

    def test_a_key_file_inside_the_repo_is_refused_by_the_command(self):
        root = fixture()
        inside = root / "key.txt"
        inside.write_bytes(KEY)
        result = cli(["--seal", "--root", root, "--passphrase-file", inside])
        self.assertEqual(1, result.returncode)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("rule: passphrase source", result.stdout)

    def test_a_terminal_less_seal_refuses_instead_of_reading_a_closed_stdin(self):
        result = cli(["--seal", "--root", fixture()])
        self.assertEqual(1, result.returncode)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("rule: passphrase source", result.stdout)

    def test_the_cli_has_no_option_that_takes_a_key_as_a_value(self):
        source = (BACKEND / "backend" / "vault.py").read_text(encoding="utf-8")
        self.assertIn('"--passphrase-file"', source)
        for fragment in ('"--passphrase"', "'--passphrase'", '"--key"', '"--secret"'):
            self.assertNotIn(fragment, source)
        self.assertNotIn("add_argument", (SCRIPTS / "vault.py").read_text(encoding="utf-8"))

    def test_the_health_gate_is_green_while_off_and_red_when_flipped(self):
        result = gate([])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("encrypted_private_backup is off", result.stdout)
        ok_lines = [line for line in result.stdout.splitlines() if line.startswith("OK")]
        self.assertEqual(1, len(ok_lines), result.stdout)
        flipped = gate(["--root", fixture(flag=True)])
        self.assertEqual(1, flipped.returncode)
        self.assertIn("INVALID", flipped.stdout)
        self.assertIn(vault.EVIDENCE.as_posix(), flipped.stdout)
        opened = gate(["--root", fixture(flag=True, evidence=GOOD_EVIDENCE)])
        self.assertEqual(0, opened.returncode, opened.stdout)
        self.assertIn("encrypted_private_backup is active", opened.stdout)


class TheHouseWiring(unittest.TestCase):
    def test_the_gate_is_wired_into_health_exactly_once(self):
        import health
        self.assertEqual(1, health.GATES.count("vault_check.py"))
        self.assertIn("vault_check.py", health.ROOT_ONLY_GATES)
        self.assertEqual(len(health.GATES), len(set(health.GATES)))

    def test_the_shipped_flag_and_the_witness_agree(self):
        """The door opens on evidence, never on the flag alone -- so a false flag with a
        witness present is allowed (evidence first, flip second) but the reverse is not."""
        config = json.loads((ROOT / vault.CONFIG).read_text(encoding="utf-8"))
        flag = config["feature_flags"]["encrypted_private_backup"]
        witness = (ROOT / vault.EVIDENCE).is_file()
        if not witness:
            self.assertFalse(flag, "the flag is true with no cross-machine witness")
        state = vault.gate(ROOT)
        self.assertEqual(bool(flag) and not state["problems"], state["active"])

    def test_the_shipped_private_planes_are_the_two_index_planes(self):
        config = json.loads((ROOT / vault.CONFIG).read_text(encoding="utf-8"))
        self.assertEqual(PLANES, config["private_planes"])

    def test_the_private_planes_stay_out_of_the_deny_zones(self):
        """`zones` drives access.denied_prefixes() and the door tests; sealing a plane is a
        different law and must not widen the read-deny set behind the owner's back."""
        config = json.loads((ROOT / vault.CONFIG).read_text(encoding="utf-8"))
        for zone in config["zones"]:
            self.assertNotIn(zone["dir"], PLANES)

    def test_one_path_rule_for_every_writer(self):
        self.assertIn("def safe_rel", (SCRIPTS / "common.py").read_text(encoding="utf-8"))
        base = (SCRIPTS / "base.py").read_text(encoding="utf-8")
        self.assertNotIn("def safe_rel", base)
        self.assertIn("safe_rel", base)

    def test_no_sealed_container_is_ever_committed(self):
        shelf = ROOT / vault.SHELF
        if shelf.is_dir():
            self.assertEqual([], list(shelf.glob("priv-*" + vault.SUFFIX)))
        self.assertFalse(common.is_repo_checkout(fixture()),
                         "a sandbox must not read as a checkout")

    def test_the_bench_measures_a_seal_without_touching_the_vault(self):
        measured = vault.bench(4096)
        self.assertEqual(4096, measured["bytes"])
        self.assertGreater(measured["container_bytes"], 4096)
        self.assertGreater(measured["seal_mb_per_second"], 0.0)
        self.assertEqual(crypto.KDF_PBKDF2, measured["kdf"])


if __name__ == "__main__":
    unittest.main()
