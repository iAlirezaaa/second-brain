"""Phase 51 -- the encryption primitive: an AEAD built from nothing but the standard library.

Charter section 8 demands "encrypted backup with a regular restore test" and section 2 forbids
handing the vault to an external binary, so the cipher has to be built here. That trade is only
defensible if the code is pinned to a known answer, so this file is written first and red first:
four RFC 8439 vectors, then every way a byte can be wrong.

The negatives are the product. A seal that works and a tag that nobody checks is a backup that
silently restores garbage, so each test below asserts refusal *by named rule* -- the same
`rule`-naming contract `backend/access.py` gives the read door. Nothing here may fall back:
a weaker KDF, a skipped tag, or a negotiated version is a downgrade the attacker chooses.

Test vectors are copied from RFC 8439 sections 2.4.2, 2.5.2 and 2.8.2. They are the oracle:
this machine has no `cryptography` module and stdlib ships no AEAD, so agreement with the RFC
is the only independent evidence that the implementation is not merely self-consistent.
"""
import ast
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "15_SYSTEM" / "scripts"
sys.path.insert(0, str(BACKEND))
from backend import crypto  # noqa: E402

CRYPTO = BACKEND / "backend" / "crypto.py"

# RFC 8439 section 2.4.2
KEY_242 = bytes(range(32))
NONCE_242 = bytes([0, 0, 0, 0, 0, 0, 0, 0x4A, 0, 0, 0, 0])
PT_242 = (b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for "
          b"the future, sunscreen would be it.")
CT_242 = bytes.fromhex(
    "6e2e359a2568f98041ba0728dd0d6981e97e7aec1d4360c20a27afccfd9fae0b"
    "f91b65c5524733ab8f593dabcd62b3571639d624e65152ab8f530c359f0861d8"
    "07ca0dbf500d6a6156a38e088a22b65e52bc514d16ccf806818ce91ab7793736"
    "5af90bbf74a35be6b40b8eedf2785e42874d")
# the first 64 bytes of the 114-byte keystream the same section prints
KEYSTREAM_242 = bytes.fromhex(
    "224f51f3401bd9e12fde276fb8631ded8c131f823d2c06e27e4fcaec9ef3cf78"
    "8a3b0aa372600a92b57974cded2b9334794cba40c63e34cdea212c4cf07d41b7")

# RFC 8439 section 2.5.2
OTK_252 = bytes.fromhex("85d6be7857556d337f4452fe42d506a80103808afb0db2fd4abff6af4149f51b")
MSG_252 = b"Cryptographic Forum Research Group"
TAG_252 = bytes.fromhex("a8061dc1305136c6c22b8baf0c0127a9")

# RFC 8439 section 2.8.2
KEY_282 = bytes(range(0x80, 0xA0))
NONCE_282 = bytes([0x07, 0, 0, 0]) + bytes(range(0x40, 0x48))
AAD_282 = bytes([0x50, 0x51, 0x52, 0x53, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7])
CT_282 = bytes.fromhex(
    "d31a8d34648e60db7b86afbc53ef7ec2a4aded51296e08fea9e2b5a736ee62d6"
    "3dbea45e8ca9671282fafb69da92728b1a71de0a9e060b2905d6a5b67ecd3b36"
    "92ddbd7f2d778b8c9803aee328091b58fab324e4fad675945585808b4831d7bc"
    "3ff4def08e4b7a9de576d26586cec64b6116")
TAG_282 = bytes.fromhex("1ae10b594f09e26a7e902ecbd0600691")

STDLIB_ONLY = {"hashlib", "hmac", "json", "secrets", "struct", "sys", "time", "os", "datetime"}
PASSPHRASE = "correct horse battery staple"


def hx(data):
    return data.hex()


def files_two():
    return [("notes/a.md", b"# alpha\n"), ("notes/b.md", b"beta" * 900), ("empty.md", b"")]


class TestKnownAnswerVectors(unittest.TestCase):
    """If these four fail, nothing else in this file means anything."""

    def test_rfc_8439_2_4_2_chacha20_ciphertext(self):
        self.assertEqual(hx(crypto.chacha20_xor(KEY_242, NONCE_242, PT_242)), hx(CT_242))

    def test_rfc_8439_2_4_2_keystream_is_ciphertext_xor_plaintext(self):
        """The RFC prints the block and the ciphertext separately; the two must agree."""
        block = crypto.chacha20_block(KEY_242, 1, NONCE_242)
        self.assertEqual(hx(block[:64]), hx(KEYSTREAM_242))
        ct = crypto.chacha20_xor(KEY_242, NONCE_242, PT_242)
        self.assertEqual(bytes(a ^ b for a, b in zip(ct, KEYSTREAM_242)), PT_242[:64])

    def test_rfc_8439_2_5_2_poly1305_tag(self):
        self.assertEqual(hx(crypto.poly1305(OTK_252, MSG_252)), hx(TAG_252))

    def test_rfc_8439_2_8_2_aead_seal(self):
        ct, tag = crypto.aead_seal(KEY_282, NONCE_282, PT_242, AAD_282)
        self.assertEqual(hx(ct), hx(CT_282))
        self.assertEqual(hx(tag), hx(TAG_282))

    def test_rfc_8439_2_8_2_aead_open(self):
        out = crypto.aead_open(KEY_282, NONCE_282, CT_282 + TAG_282, AAD_282)
        self.assertEqual(out, PT_242)


class TestKdf(unittest.TestCase):
    def test_two_kdfs_both_produce_a_32_byte_key(self):
        salt = os.urandom(16)
        for kdf in (crypto.KDF_SCRYPT, crypto.KDF_PBKDF2):
            key = crypto.kdf_derive(PASSPHRASE.encode("utf-8"), salt, kdf)
            self.assertEqual(len(key), 32, kdf)

    def test_salt_changes_the_key(self):
        a = crypto.kdf_derive(b"pw", b"\x00" * 16, crypto.KDF_SCRYPT)
        b = crypto.kdf_derive(b"pw", b"\x01" * 16, crypto.KDF_SCRYPT)
        self.assertNotEqual(a, b)

    def test_an_unknown_kdf_name_is_refused_not_guessed(self):
        with self.assertRaises(crypto.UnsupportedKDF) as caught:
            crypto.kdf_derive(b"pw", b"\x00" * 16, "aes-256-gcm-argon2")
        self.assertIn("argon2", str(caught.exception))

    def test_a_kdf_this_platform_cannot_run_refuses_without_falling_back(self):
        """The dangerous failure is silence: scrypt unavailable must not mean 'use pbkdf2'."""
        def explode(*args, **kwargs):
            raise ValueError("scrypt is not available in this build")
        original = crypto._scrypt
        try:
            crypto._scrypt = explode
            with self.assertRaises(crypto.UnsupportedKDF) as caught:
                crypto.kdf_derive(b"pw", b"\x00" * 16, crypto.KDF_SCRYPT)
        finally:
            crypto._scrypt = original
        message = str(caught.exception)
        self.assertIn("scrypt", message)
        self.assertNotIn("pbkdf2", message)

    def test_seal_refuses_an_unsupported_kdf_before_writing_anything(self):
        with self.assertRaises(crypto.UnsupportedKDF):
            crypto.seal_container(files_two(), b"pw", kdf="argon2id")


class TestRoundTrip(unittest.TestCase):
    def test_seal_then_open_returns_the_same_bytes(self):
        blob = crypto.seal_container(files_two(), PASSPHRASE.encode("utf-8"))
        self.assertEqual(crypto.open_container(blob, PASSPHRASE.encode("utf-8")), files_two())

    def test_a_sealed_container_holds_no_plaintext_of_any_file(self):
        blob = crypto.seal_container(files_two(), PASSPHRASE.encode("utf-8"))
        self.assertNotIn(b"beta" * 4, blob)
        self.assertNotIn(b"# alpha", blob)
        # the manifest, and with it every path, lives inside the encrypted frames
        self.assertNotIn(b"notes/a.md", blob)

    def test_the_container_digest_is_over_the_bytes_that_ship(self):
        blob = crypto.seal_container(files_two(), PASSPHRASE.encode("utf-8"))
        self.assertEqual(crypto.container_digest(blob), hashlib.sha256(blob).hexdigest())

    def test_two_seals_of_one_plaintext_are_not_one_container(self):
        pw = PASSPHRASE.encode("utf-8")
        first = crypto.seal_container(files_two(), pw)
        second = crypto.seal_container(files_two(), pw)
        self.assertNotEqual(first, second)
        self.assertEqual(crypto.open_container(second, pw), files_two())

    def test_the_wrong_passphrase_refuses_without_producing_a_file(self):
        blob = crypto.seal_container(files_two(), PASSPHRASE.encode("utf-8"))
        with self.assertRaises(crypto.OpenError) as caught:
            crypto.open_container(blob, b"the wrong one")
        self.assertEqual(caught.exception.rule, "tag")

    def test_an_empty_file_list_is_refused_not_sealed_empty(self):
        with self.assertRaises(crypto.SealError):
            crypto.seal_container([], b"pw")

    def test_paths_that_escape_are_refused_at_the_seal(self):
        for bad in ("/abs/a.md", "../a.md", "a/../../b.md", "C:/x/a.md", "", "a\\b.md"):
            with self.assertRaises(crypto.SealError, msg=bad):
                crypto.seal_container([(bad, b"x")], b"pw")


class TestTamperIsRefusedByName(unittest.TestCase):
    """Every attack below must raise OpenError and name the rule that stopped it."""

    @classmethod
    def setUpClass(cls):
        cls.pw = PASSPHRASE.encode("utf-8")
        cls.blob = crypto.seal_container(files_two(), cls.pw)

    def flip(self, offset):
        mutated = bytearray(self.blob)
        mutated[offset] ^= 0x01
        return bytes(mutated)

    def assert_refused(self, blob, rule):
        with self.assertRaises(crypto.OpenError) as caught:
            crypto.open_container(blob, self.pw)
        self.assertEqual(caught.exception.rule, rule)

    def test_a_single_flipped_ciphertext_byte(self):
        frames = crypto.parse_container(self.blob)["frames"]
        target = frames[2]["ct_start"] + 3
        self.assert_refused(self.flip(target), "tag")

    def test_a_single_flipped_byte_in_the_authenticated_header(self):
        parsed = crypto.parse_container(self.blob)
        self.assert_refused(self.flip(parsed["header_start"] + 5), "kdf params")

    def test_a_flipped_byte_in_the_tag(self):
        frames = crypto.parse_container(self.blob)["frames"]
        self.assert_refused(self.flip(frames[1]["tag_start"]), "tag")

    def test_a_truncated_container(self):
        self.assert_refused(self.blob[:-20], "truncated")

    def test_a_container_cut_in_the_middle_of_a_frame(self):
        frames = crypto.parse_container(self.blob)["frames"]
        self.assert_refused(self.blob[: frames[2]["ct_start"] + 8], "truncated")

    def test_two_frames_swapped(self):
        parsed = crypto.parse_container(self.blob)
        first, second = parsed["frames"][1], parsed["frames"][2]
        head = self.blob[: first["start"]]
        frame_a = self.blob[first["start"]: second["start"]]
        frame_b = self.blob[second["start"]: parsed["frames_start"] + parsed["body_end"]]
        swapped = head + frame_b + frame_a
        self.assert_refused(swapped, "tag")

    def test_a_frame_replayed_inside_the_same_container(self):
        parsed = crypto.parse_container(self.blob)
        first, second = parsed["frames"][1], parsed["frames"][2]
        replayed = (self.blob[: second["start"]]
                    + self.blob[first["start"]: second["start"]]
                    + self.blob[second["end"]:])
        with self.assertRaises(crypto.OpenError) as caught:
            crypto.open_container(replayed, self.pw)
        self.assertIn(caught.exception.rule, ("nonce reuse", "trailing bytes"))

    def test_a_frame_spliced_from_a_container_with_the_same_key(self):
        """Same plaintext, same key, different context: the AAD must be what stops it."""
        other = crypto.seal_container(files_two(), self.pw)
        source = crypto.parse_container(other)["frames"][1]
        frame = other[source["start"]: source["end"]]
        target = crypto.parse_container(self.blob)["frames"][1]
        spliced = (self.blob[: target["start"]] + frame
                   + self.blob[target["nonce_start"] + 12 + 4 + target["length"]:])
        with self.assertRaises(crypto.OpenError) as caught:
            crypto.open_container(spliced, self.pw)
        self.assertIn(caught.exception.rule, ("nonce reuse", "tag"))

    def test_a_version_byte_of_two_is_refused_rather_than_attempted(self):
        mutated = bytearray(self.blob)
        mutated[4] = 2
        self.assert_refused(bytes(mutated), "version")

    def test_an_unknown_kdf_id_byte_is_refused(self):
        mutated = bytearray(self.blob)
        mutated[5] = 9
        self.assert_refused(bytes(mutated), "kdf id")

    def test_a_container_from_another_magic_is_refused(self):
        mutated = bytearray(self.blob)
        mutated[0] = ord("X")
        self.assert_refused(bytes(mutated), "magic")

    def test_a_stripped_footer_is_refused(self):
        self.assert_refused(self.blob[: -(4 + 32)], "truncated")

    def test_the_rule_a_refusal_names_is_a_rule_this_build_declares(self):
        """Anti-forgery: a refusal may not invent a law to sound authoritative."""
        parsed = crypto.parse_container(self.blob)
        with self.assertRaises(crypto.OpenError) as caught:
            crypto.open_container(self.flip(parsed["frames"][1]["ct_start"]), self.pw)
        self.assertIn(caught.exception.rule, crypto.OPEN_RULES)


class TestFrameBinding(unittest.TestCase):
    """The frame AAD binds context, index, path and length -- each one, measurably."""

    def test_every_aad_input_changes_the_aad(self):
        base = crypto.frame_aad(b"\x01" * 32, 1, b"\x02" * 32, 7)
        variants = [
            crypto.frame_aad(b"\x09" * 32, 1, b"\x02" * 32, 7),
            crypto.frame_aad(b"\x01" * 32, 2, b"\x02" * 32, 7),
            crypto.frame_aad(b"\x01" * 32, 1, b"\x09" * 32, 7),
            crypto.frame_aad(b"\x01" * 32, 1, b"\x02" * 32, 8),
        ]
        self.assertEqual(len(set([base] + variants)), 5)

    def test_a_frame_opened_with_another_files_aad_refuses(self):
        key = bytes(32)
        nonce = bytes(12)
        aad = crypto.frame_aad(b"\x01" * 32, 1, hashlib.sha256(b"notes/a.md").digest(), 4)
        sealed = crypto.aead_seal(key, nonce, b"data", aad)
        wrong = crypto.frame_aad(b"\x01" * 32, 1, hashlib.sha256(b"notes/b.md").digest(), 4)
        with self.assertRaises(crypto.OpenError) as caught:
            crypto.aead_open(key, nonce, sealed[0] + sealed[1], wrong)
        self.assertEqual(caught.exception.rule, "tag")


class TestNoNegotiation(unittest.TestCase):
    """A format that accepts a weaker parameter is a format that will be downgraded."""

    def test_a_header_that_declares_weaker_scrypt_params_is_refused(self):
        pw = PASSPHRASE.encode("utf-8")
        blob = crypto.seal_container(files_two(), pw)
        parsed = crypto.parse_container(blob)
        header = dict(parsed["header"])
        header["scrypt_n"] = 1024
        raw = json_bytes(header)
        rebuilt = (blob[: parsed["header_start"]]
                   + len(raw).to_bytes(4, "big") + raw
                   + blob[parsed["header_start"] + parsed["header_len"]:])
        with self.assertRaises(crypto.OpenError) as caught:
            crypto.open_container(rebuilt, pw)
        self.assertIn(caught.exception.rule, ("kdf params", "tag", "header"))


class TestSelfTestCli(unittest.TestCase):
    """The KAT gate has to run as a command, not only as a test, so health can call it."""

    def run_cli(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, str(CRYPTO)] + list(args),
                              capture_output=True, text=True, cwd=str(ROOT), env=env)

    def test_selftest_passes_and_names_the_vectors(self):
        done = self.run_cli("--selftest")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("KAT", done.stdout)
        self.assertIn("chacha20", done.stdout)
        self.assertIn("poly1305", done.stdout)

    def test_bench_reports_measured_throughput(self):
        done = self.run_cli("--bench", "--bytes", "65536")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("MB/s", done.stdout)

    def test_the_primitive_imports_only_the_standard_library(self):
        tree = ast.parse(CRYPTO.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(sorted(imported - STDLIB_ONLY), [])


def json_bytes(header):
    import json
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
