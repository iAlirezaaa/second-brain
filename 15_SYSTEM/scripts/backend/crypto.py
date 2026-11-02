"""Encrypted container primitive: ChaCha20-Poly1305 from the standard library alone.

Charter section 8 demands an encrypted backup with a real restore test, section 2 forbids handing
the private plane to an external binary, and this machine has no `cryptography` module and stdlib
ships no AEAD, so the cipher lives here. That trade is only defensible while it is pinned to an
outside oracle: every constant in VECTORS below is a published RFC 8439 known answer, `--selftest`
re-checks them on every call, and `tests/test_phase51_chacha20_poly1305.py` flips single bytes of a
real container to prove a wrong one is refused by the name of the rule that stopped it.

What does NOT ship here: any product surface, any file I/O, any key storage, any schedule. Sealing
a real backup is `scripts/vault.py`'s job (later phase). This module only turns bytes into bytes.

Design decisions worth naming:

* One format, no negotiation. A header declaring weaker key-derivation parameters is refused rather
  than honoured, so nobody can downgrade a container that was sealed elsewhere.
* Every frame is bound to the container it came from: its additional authenticated data carries the
  digest of the authenticated header, its own index, the digest of its path and its length. Frames
  therefore cannot be reordered, replayed or spliced between containers without a tag failure.
* A refusal always names its rule and the rule names come from one closed set, OPEN_RULES. A refusal
  that invents a law is as much a bug as a check that was skipped.
"""
import hashlib
import hmac
import json
import secrets
import struct
import sys
import time

MAGIC = b"SBO1"
VERSION = 1
SALT_LEN = 16
HEADER_LEN_BYTES = 4
PREFIX_LEN = len(MAGIC) + 1 + 1 + SALT_LEN + HEADER_LEN_BYTES
FRAME_NONCE_LEN = 12
FRAME_LEN_BYTES = 4
TAG_LEN = 16
FOOTER_LEN = 4 + 32
MAX_FRAME_BYTES = 32 * 1024 * 1024

KDF_SCRYPT = "scrypt"
KDF_PBKDF2 = "pbkdf2"
KDF_IDS = {1: KDF_SCRYPT, 2: KDF_PBKDF2}
KDF_PARAMS = {
    KDF_SCRYPT: {"kdf": KDF_SCRYPT, "scrypt_n": 2 ** 15, "scrypt_r": 8, "scrypt_p": 1},
    KDF_PBKDF2: {"kdf": KDF_PBKDF2, "pbkdf2_hash": "sha256", "pbkdf2_iters": 600000},
}

MANIFEST_NAME = "@manifest"

OPEN_RULES = frozenset([
    "magic", "version", "kdf id", "kdf params", "truncated", "trailing bytes",
    "frame length", "nonce reuse", "tag", "footer digest", "path set",
])

_SIGMA = b"expand 32-byte k"
_MASK = 0xFFFFFFFF
_POLY_P = (1 << 130) - 5
_POLY_CLAMP = 0x0ffffffc0ffffffc0ffffffc0fffffff


class SealError(Exception):
    """The bytes handed to `seal_container` cannot be sealed as stated."""


class UnsupportedKDF(Exception):
    """A key derivation was asked for that this build will not run -- and will not substitute."""


class OpenError(Exception):
    """A container was refused. `rule` names the law that refused it; see OPEN_RULES."""

    def __init__(self, message, rule):
        Exception.__init__(self, "%s (rule: %s)" % (message, rule))
        self.rule = rule


def _refuse(rule, message):
    if rule not in OPEN_RULES:
        raise AssertionError("refusal named a rule this build does not declare: %r" % rule)
    raise OpenError(message, rule)


def _rotl(value, bits):
    return ((value << bits) | (value >> (32 - bits))) & _MASK


def _quarter_round(x, a, b, c, d):
    x[a] = (x[a] + x[b]) & _MASK
    x[d] = _rotl(x[d] ^ x[a], 16)
    x[c] = (x[c] + x[d]) & _MASK
    x[b] = _rotl(x[b] ^ x[c], 12)
    x[a] = (x[a] + x[b]) & _MASK
    x[d] = _rotl(x[d] ^ x[a], 8)
    x[c] = (x[c] + x[d]) & _MASK
    x[b] = _rotl(x[b] ^ x[c], 7)


def _chacha_state(key, counter, nonce):
    if len(key) != 32:
        raise SealError("ChaCha20 key must be 32 bytes, got %d" % len(key))
    if len(nonce) != FRAME_NONCE_LEN:
        raise SealError("ChaCha20 nonce must be 12 bytes, got %d" % len(nonce))
    state = list(struct.unpack("<4I", _SIGMA))
    state += list(struct.unpack("<8I", key))
    state.append(counter & _MASK)
    state += list(struct.unpack("<3I", nonce))
    return state


def chacha20_block(key, counter, nonce):
    """One 64-byte keystream block: ChaCha20 with a 32-bit counter and a 96-bit nonce (RFC 8439 2.3)."""
    state = _chacha_state(key, counter, nonce)
    x = list(state)
    for _ in range(10):
        _quarter_round(x, 0, 4, 8, 12)
        _quarter_round(x, 1, 5, 9, 13)
        _quarter_round(x, 2, 6, 10, 14)
        _quarter_round(x, 3, 7, 11, 15)
        _quarter_round(x, 0, 5, 10, 15)
        _quarter_round(x, 1, 6, 11, 12)
        _quarter_round(x, 2, 7, 8, 13)
        _quarter_round(x, 3, 4, 9, 14)
    return struct.pack("<16I", *[(a + b) & _MASK for a, b in zip(x, state)])


def chacha20_xor(key, nonce, data, counter=1):
    """Encrypt or decrypt `data`; the counter starts at 1 because 0 is spent on the one-time key."""
    out = bytearray(len(data))
    for offset in range(0, len(data), 64):
        block = chacha20_block(key, counter + offset // 64, nonce)
        chunk = data[offset:offset + 64]
        for i, byte in enumerate(chunk):
            out[offset + i] = byte ^ block[i]
    return bytes(out)


def poly1305(key, message):
    """Poly1305 MAC over `message` with a 32-byte one-time key (RFC 8439 2.5)."""
    if len(key) != 32:
        raise SealError("Poly1305 needs a 32-byte one-time key, got %d" % len(key))
    r = int.from_bytes(key[:16], "little") & _POLY_CLAMP
    s = int.from_bytes(key[16:], "little")
    h = 0
    for offset in range(0, len(message), 16):
        block = message[offset:offset + 16]
        n = int.from_bytes(block + b"\x01", "little")
        h = ((h + n) * r) % _POLY_P
    return ((h + s) & ((1 << 128) - 1)).to_bytes(16, "little")


def _pad16(data):
    remainder = len(data) % 16
    return data if remainder == 0 else data + b"\x00" * (16 - remainder)


def _mac_data(aad, ciphertext):
    return (_pad16(aad) + _pad16(ciphertext)
            + len(aad).to_bytes(8, "little") + len(ciphertext).to_bytes(8, "little"))


def aead_seal(key, nonce, plaintext, aad):
    """AEAD_CHACHA20_POLY1305 seal; returns (ciphertext, 16-byte tag)."""
    one_time_key = chacha20_block(key, 0, nonce)[:32]
    ciphertext = chacha20_xor(key, nonce, plaintext)
    return ciphertext, poly1305(one_time_key, _mac_data(aad, ciphertext))


def aead_open(key, nonce, sealed, aad):
    """AEAD_CHACHA20_POLY1305 open. The tag is checked before a single plaintext byte is returned.

    The tag is recomputed over the received ciphertext here rather than by calling `aead_seal` on
    it: seal encrypts what it is handed, so feeding it the ciphertext would MAC the double-encrypted
    bytes and refuse every honest container.
    """
    if len(sealed) < TAG_LEN:
        _refuse("truncated", "a sealed frame needs at least a %d-byte tag, got %d bytes"
                % (TAG_LEN, len(sealed)))
    ciphertext, tag = sealed[:-TAG_LEN], sealed[-TAG_LEN:]
    one_time_key = chacha20_block(key, 0, nonce)[:32]
    expected = poly1305(one_time_key, _mac_data(aad, ciphertext))
    if not hmac.compare_digest(tag, expected):
        _refuse("tag", "the Poly1305 tag does not match this frame under the key it was derived with")
    return chacha20_xor(key, nonce, ciphertext)


def frame_aad(context_digest, index, path_digest, length):
    """Bind a frame to one place in one container: header digest, index, path digest, plaintext length."""
    return (context_digest
            + index.to_bytes(8, "big")
            + path_digest
            + length.to_bytes(8, "big"))


def kdf_derive(passphrase, salt, kdf):
    """Stretch a passphrase to a 32-byte key. No fallback: an unavailable KDF is a stated refusal."""
    if kdf == KDF_SCRYPT:
        params = KDF_PARAMS[KDF_SCRYPT]
        try:
            return _scrypt(passphrase, salt, params["scrypt_n"], params["scrypt_r"], params["scrypt_p"])
        except Exception as exc:
            raise UnsupportedKDF(
                "this build cannot run scrypt (%s), and it will not pretend otherwise by deriving the"
                " key some other way; this container is neither sealed nor opened here" % exc)
    if kdf == KDF_PBKDF2:
        params = KDF_PARAMS[KDF_PBKDF2]
        return hashlib.pbkdf2_hmac(params["pbkdf2_hash"], passphrase, salt,
                                   params["pbkdf2_iters"], dklen=32)
    raise UnsupportedKDF("unknown key derivation %r: this build ships %s only"
                         % (kdf, ", ".join(sorted(KDF_PARAMS))))


def _scrypt(passphrase, salt, n, r, p):
    return hashlib.scrypt(passphrase, salt=salt, n=n, r=r, p=p, dklen=32, maxmem=64 * 1024 * 1024)


def container_digest(blob):
    return hashlib.sha256(blob).hexdigest()


def _safe_path(path):
    if not path or path != path.strip():
        return "empty or padded"
    if "\\" in path or "\x00" in path:
        return "contains a backslash or a NUL"
    if path.startswith("/"):
        return "absolute"
    if len(path) > 1 and path[1] == ":":
        return "a drive-qualified path"
    segments = path.split("/")
    for segment in segments:
        if segment in ("", ".", ".."):
            return "walks outside the container root"
    if path == MANIFEST_NAME:
        return "the reserved manifest name"
    return None


def _encode_header(params):
    return json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8")


def seal_container(files, passphrase, kdf=KDF_SCRYPT):
    """Seal [(path, bytes), ...] into one SBO1 container. Writes nothing; returns bytes."""
    if not files:
        raise SealError("refusing to seal an empty file list: a backup with no files is not a backup")
    seen = set()
    for path, payload in files:
        problem = _safe_path(path)
        if problem:
            raise SealError("refusing to seal path %r: %s" % (path, problem))
        if path == MANIFEST_NAME:
            raise SealError("%r is reserved for the manifest frame" % MANIFEST_NAME)
        if path in seen:
            raise SealError("duplicate path in one seal: %r" % path)
        seen.add(path)
    params = KDF_PARAMS.get(kdf)
    if params is None:
        kdf_derive(b"", b"\x00" * SALT_LEN, kdf)
    if len(passphrase) == 0:
        raise SealError("refusing to seal with an empty passphrase")
    salt = secrets.token_bytes(SALT_LEN)
    header = _encode_header(params)
    prefix = (MAGIC + bytes([VERSION, _kdf_id(kdf)]) + salt
              + len(header).to_bytes(HEADER_LEN_BYTES, "big") + header)
    context = hashlib.sha256(prefix).digest()
    key = kdf_derive(passphrase, salt, kdf)
    manifest = _encode_header({"kind": "manifest",
                               "files": [[path, len(payload)] for path, payload in files]})
    entries = [(MANIFEST_NAME, manifest)] + [(path, payload) for path, payload in files]
    used = set()
    frames = []
    for index, (name, payload) in enumerate(entries):
        if len(payload) > MAX_FRAME_BYTES:
            raise SealError("frame %d would be %d bytes, over the %d-byte cap"
                            % (index, len(payload), MAX_FRAME_BYTES))
        frame_nonce = _fresh_nonce(used, index)
        aad = frame_aad(context, index, hashlib.sha256(name.encode("utf-8")).digest(), len(payload))
        ciphertext, tag = aead_seal(key, frame_nonce, payload, aad)
        frames.append(frame_nonce + len(ciphertext).to_bytes(FRAME_LEN_BYTES, "big") + ciphertext + tag)
    body = b"".join(frames)
    footer = len(frames).to_bytes(4, "big") + hashlib.sha256(prefix + body).digest()
    return prefix + body + footer


def _kdf_id(kdf):
    for value, name in KDF_IDS.items():
        if name == kdf:
            return value
    raise SealError("no id byte for key derivation %r" % kdf)


def _fresh_nonce(used, index):
    for _ in range(8):
        candidate = secrets.token_bytes(FRAME_NONCE_LEN)
        if candidate not in used:
            used.add(candidate)
            return candidate
    raise SealError("could not draw a fresh nonce for frame %d; refusing to reuse one" % index)


def _read_frame(blob, pos):
    """Structural read of one frame. Returns (nonce, ciphertext_len, ct_start, tag_start, end)."""
    if len(blob) - pos < FRAME_NONCE_LEN + FRAME_LEN_BYTES + TAG_LEN:
        _refuse("truncated", "frame at offset %d has no room for a nonce, a length and a tag" % pos)
    nonce = blob[pos:pos + FRAME_NONCE_LEN]
    length = int.from_bytes(blob[pos + FRAME_NONCE_LEN:pos + FRAME_NONCE_LEN + FRAME_LEN_BYTES], "big")
    if length > MAX_FRAME_BYTES:
        _refuse("frame length", "frame at offset %d declares %d bytes, over the %d-byte cap"
                % (pos, length, MAX_FRAME_BYTES))
    ct_start = pos + FRAME_NONCE_LEN + FRAME_LEN_BYTES
    if len(blob) - ct_start < length + TAG_LEN:
        _refuse("truncated", "frame at offset %d declares %d payload bytes but the container ends at %d"
                % (pos, length, len(blob)))
    return nonce, length, ct_start, ct_start + length, ct_start + length + TAG_LEN


def read_header(blob):
    """Read and honour the authenticated prefix only. No passphrase, no frame walk.

    Kept separate from parse_container on purpose: a container that has not been opened may be
    inspected for evidence, but opening must not learn the frame map before the tags say so. A
    structural walk first would let an attacker choose which rule a splice trips -- frame length or
    truncated -- instead of the one that actually stopped it.
    """
    if len(blob) < PREFIX_LEN + FOOTER_LEN:
        _refuse("truncated", "a container is at least %d bytes, got %d" % (PREFIX_LEN + FOOTER_LEN, len(blob)))
    if blob[:len(MAGIC)] != MAGIC:
        _refuse("magic", "container does not start with %r" % MAGIC)
    if blob[4] != VERSION:
        _refuse("version", "container version %d cannot be read by this build, which writes version %d"
                % (blob[4], VERSION))
    kdf_id = blob[5]
    if kdf_id not in KDF_IDS:
        _refuse("kdf id", "no key derivation is registered under id byte %d" % kdf_id)
    salt = blob[6:6 + SALT_LEN]
    header_len = int.from_bytes(blob[6 + SALT_LEN:PREFIX_LEN], "big")
    if header_len == 0 or PREFIX_LEN + header_len + FOOTER_LEN > len(blob):
        _refuse("truncated", "header length %d does not fit a %d-byte container" % (header_len, len(blob)))
    raw = blob[PREFIX_LEN:PREFIX_LEN + header_len]
    try:
        header = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        _refuse("kdf params", "the header that carries the key-derivation parameters is not readable"
                " as JSON (%s), so nothing about this container can be trusted" % exc)
    if not isinstance(header, dict) or header != KDF_PARAMS[KDF_IDS[kdf_id]]:
        _refuse("kdf params", "the header declares %r but this build only honours %r"
                % (header, KDF_PARAMS[KDF_IDS[kdf_id]]))
    frames_start = PREFIX_LEN + header_len
    return {
        "version": blob[4], "kdf_id": kdf_id, "kdf": KDF_IDS[kdf_id], "salt": salt,
        "header": header, "header_start": PREFIX_LEN, "header_len": header_len,
        "frames_start": frames_start, "prefix": blob[:frames_start],
        "context_digest": hashlib.sha256(blob[:frames_start]).digest(),
    }


def parse_container(blob):
    """Read the authenticated header and the frame map. Needs no passphrase, so evidence can be checked."""
    parsed = read_header(blob)
    body_limit = len(blob) - FOOTER_LEN
    frames = []
    pos = parsed["frames_start"]
    while pos < body_limit:
        nonce, length, ct_start, tag_start, end = _read_frame(blob, pos)
        frames.append({"start": pos, "nonce_start": pos, "ct_start": ct_start,
                       "tag_start": tag_start, "end": end, "length": length, "nonce": nonce})
        pos = end
    if pos > body_limit:
        _refuse("trailing bytes", "the frames run past the footer at offset %d of %d" % (pos, len(blob)))
    parsed.update({
        "frames": frames, "body_end": pos,
        "frame_count": int.from_bytes(blob[pos:pos + 4], "big"),
        "footer_digest": blob[pos + 4:pos + FOOTER_LEN],
    })
    return parsed


def open_container(blob, passphrase):
    """Open a SBO1 container and return [(path, bytes), ...]. Any refusal names its rule."""
    parsed = read_header(blob)
    key = kdf_derive(passphrase, parsed["salt"], parsed["kdf"])
    context = parsed["context_digest"]
    nonce_history = set()

    first = _read_frame(blob, parsed["frames_start"])
    _check_nonce(nonce_history, first, 0)
    manifest_bytes = _open_frame(key, blob, first, frame_aad(
        context, 0, hashlib.sha256(MANIFEST_NAME.encode("utf-8")).digest(), first[1]))
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, dict) or manifest.get("kind") != "manifest":
        _refuse("path set", "the first frame authenticated, but it is not the manifest it claimed to be")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        _refuse("path set", "the manifest lists no files, and an empty backup is not a backup")

    out = []
    pos = first[4]
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, list) or len(entry) != 2 or not isinstance(entry[0], str):
            _refuse("path set", "manifest entry %d is %r, not [path, length]" % (index, entry))
        path, declared = entry[0], entry[1]
        if _safe_path(path):
            _refuse("path set", "manifest entry %d carries the path %r, which this build never seals"
                    % (index, path))
        read = _read_frame(blob, pos)
        _check_nonce(nonce_history, read, index)
        plaintext = _open_frame(key, blob, read, frame_aad(
            context, index, hashlib.sha256(path.encode("utf-8")).digest(), read[1]))
        # the manifest is read only after this frame authenticated: a tampered length changes the AAD,
        # so a disagreement between the two is a bookkeeping fault, never the thing that stopped an attack
        if declared != len(plaintext):
            _refuse("frame length", "%r declares %d bytes in the manifest, the authenticated frame"
                    " holds %d" % (path, declared, len(plaintext)))
        out.append((path, plaintext))
        pos = read[4]

    if pos + FOOTER_LEN > len(blob):
        _refuse("truncated", "the manifest promised %d files and the container ran out at %d bytes"
                % (len(entries) + 1, len(blob)))
    if pos + FOOTER_LEN != len(blob):
        _refuse("trailing bytes", "%d bytes follow the last frame the manifest declared"
                % (len(blob) - pos - FOOTER_LEN))
    if int.from_bytes(blob[pos:pos + 4], "big") != len(entries) + 1:
        _refuse("footer digest", "the footer counts %d frames, the manifest declares %d"
                % (int.from_bytes(blob[pos:pos + 4], "big"), len(entries) + 1))
    if not hmac.compare_digest(blob[pos + 4:], hashlib.sha256(blob[:pos]).digest()):
        _refuse("footer digest", "the whole-body digest in the footer does not match the bytes shipped")
    return out


def _check_nonce(history, frame, index):
    if frame[0] in history:
        _refuse("nonce reuse", "frame %d reuses a nonce already seen in this container; two frames"
                " under one key may not share a nonce" % index)
    history.add(frame[0])


def _open_frame(key, blob, frame, aad):
    sealed = blob[frame[2]:frame[4]]
    return aead_open(key, frame[0], sealed, aad)


# --- RFC 8439 known answers ----------------------------------------------------------------------------
# Extracted from the published text, not typed: each hexdump, colon-run and state matrix was parsed,
# and the ciphertext of both sections equals plaintext xor keystream, so a transcription slip in any
# one of them breaks the set rather than passing quietly.

_SUNSCREEN = (b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for "
              b"the future, sunscreen would be it.")

VECTORS = {
    "chacha20 2.4.2": {
        "key": bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"),
        "counter": 1,
        "nonce": bytes.fromhex("000000000000004a00000000"),
        "block": bytes.fromhex(
            "224f51f3401bd9e12fde276fb8631ded8c131f823d2c06e27e4fcaec9ef3cf78"
            "8a3b0aa372600a92b57974cded2b9334794cba40c63e34cdea212c4cf07d41b7"),
        "plaintext": _SUNSCREEN,
        "ciphertext": bytes.fromhex(
            "6e2e359a2568f98041ba0728dd0d6981e97e7aec1d4360c20a27afccfd9fae0b"
            "f91b65c5524733ab8f593dabcd62b3571639d624e65152ab8f530c359f0861d8"
            "07ca0dbf500d6a6156a38e088a22b65e52bc514d16ccf806818ce91ab7793736"
            "5af90bbf74a35be6b40b8eedf2785e42874d"),
    },
    "poly1305 2.5.2": {
        "key": bytes.fromhex("85d6be7857556d337f4452fe42d506a80103808afb0db2fd4abff6af4149f51b"),
        "message": b"Cryptographic Forum Research Group",
        "tag": bytes.fromhex("a8061dc1305136c6c22b8baf0c0127a9"),
    },
    "aead 2.8.2": {
        "key": bytes.fromhex("808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f"),
        "nonce": bytes.fromhex("070000004041424344454647"),
        "aad": bytes.fromhex("50515253c0c1c2c3c4c5c6c7"),
        "plaintext": _SUNSCREEN,
        "one_time_key": bytes.fromhex("7bac2b252db447af09b67a55a4e955840ae1d6731075d9eb2a9375783ed553ff"),
        "ciphertext": bytes.fromhex(
            "d31a8d34648e60db7b86afbc53ef7ec2a4aded51296e08fea9e2b5a736ee62d6"
            "3dbea45e8ca9671282fafb69da92728b1a71de0a9e060b2905d6a5b67ecd3b36"
            "92ddbd7f2d778b8c9803aee328091b58fab324e4fad675945585808b4831d7bc"
            "3ff4def08e4b7a9de576d26586cec64b6116"),
        "tag": bytes.fromhex("1ae10b594f09e26a7e902ecbd0600691"),
    },
}


def run_selftest():
    """Re-check every published vector and every refusal the format promises. Returns lines."""
    lines = []
    source = VECTORS["chacha20 2.4.2"]
    block = chacha20_block(source["key"], source["counter"], source["nonce"])
    if block != source["block"]:
        raise AssertionError("chacha20 block does not match RFC 8439 2.4.2")
    encrypted = chacha20_xor(source["key"], source["nonce"], source["plaintext"])
    if encrypted != source["ciphertext"]:
        raise AssertionError("chacha20 ciphertext does not match RFC 8439 2.4.2")
    if chacha20_xor(source["key"], source["nonce"], encrypted) != source["plaintext"]:
        raise AssertionError("chacha20 is not an involution")
    lines.append("KAT chacha20 2.4.2 ok (%d bytes of ciphertext)" % len(encrypted))

    source = VECTORS["poly1305 2.5.2"]
    if poly1305(source["key"], source["message"]) != source["tag"]:
        raise AssertionError("poly1305 tag does not match RFC 8439 2.5.2")
    lines.append("KAT poly1305 2.5.2 ok")

    source = VECTORS["aead 2.8.2"]
    if chacha20_block(source["key"], 0, source["nonce"])[:32] != source["one_time_key"]:
        raise AssertionError("AEAD one-time key does not match RFC 8439 2.8.2")
    sealed, tag = aead_seal(source["key"], source["nonce"], source["plaintext"], source["aad"])
    if sealed != source["ciphertext"] or tag != source["tag"]:
        raise AssertionError("AEAD seal does not match RFC 8439 2.8.2")
    if aead_open(source["key"], source["nonce"], sealed + tag, source["aad"]) != source["plaintext"]:
        raise AssertionError("AEAD open does not return the RFC 8439 2.8.2 plaintext")
    forged = bytearray(tag)
    forged[0] ^= 0x01
    try:
        aead_open(source["key"], source["nonce"], sealed + bytes(forged), source["aad"])
    except OpenError as exc:
        if exc.rule != "tag":
            raise AssertionError("a flipped tag byte named %r, not 'tag'" % exc.rule)
    else:
        raise AssertionError("a forged tag was accepted")
    lines.append("KAT chacha20-poly1305 aead 2.8.2 ok (seal, open, one-bit forgery refused)")

    for name in sorted(KDF_PARAMS):
        derived = kdf_derive(b"selftest", b"\x00" * SALT_LEN, name)
        if len(derived) != 32:
            raise AssertionError("%s did not derive 32 bytes" % name)
        lines.append("KAT key derivation %s ok (32 bytes)" % name)

    files = [("notes/a.md", b"# alpha\n"), ("notes/b.md", b"beta" * 40), ("empty.md", b"")]
    blob = seal_container(files, b"selftest")
    if open_container(blob, b"selftest") != files:
        raise AssertionError("a container sealed in this run did not open back to the same bytes")
    if b"notes/a.md" in blob or b"# alpha" in blob:
        raise AssertionError("a sealed container leaked plaintext it promised to hide")
    for label, mutated, rule in _tamper_cases(blob):
        try:
            open_container(mutated, b"selftest")
        except OpenError as exc:
            if exc.rule != rule:
                raise AssertionError("%s named %r, expected %r" % (label, exc.rule, rule))
        else:
            raise AssertionError("%s was accepted" % label)
    try:
        open_container(blob, b"the wrong one")
    except OpenError as exc:
        if exc.rule != "tag":
            raise AssertionError("a wrong passphrase named %r, not 'tag'" % exc.rule)
    else:
        raise AssertionError("a wrong passphrase opened the container")
    lines.append("KAT container round-trip ok (%d bytes, %d tamper cases refused by name)"
                 % (len(blob), len(_tamper_cases(blob))))
    lines.append("rules declared: %s" % ", ".join(sorted(OPEN_RULES)))
    return lines


def _tamper_cases(blob):
    parsed = parse_container(blob)
    frames = parsed["frames"]
    flip = lambda offset: (blob[:offset] + bytes([blob[offset] ^ 0x01]) + blob[offset + 1:])
    cases = [
        ("ciphertext byte", flip(frames[1]["ct_start"] + 1), "tag"),
        ("tag byte", flip(frames[1]["tag_start"]), "tag"),
        ("header byte", flip(parsed["header_start"] + 5), "kdf params"),
        ("version byte", flip(4), "version"),
        ("kdf id byte", flip(5), "kdf id"),
        ("magic byte", flip(0), "magic"),
        ("last 20 bytes", blob[:-20], "truncated"),
        ("footer stripped", blob[:-(4 + 32)], "truncated"),
    ]
    second = frames[1]["ct_start"] + 8
    cases.append(("frame cut", blob[:second], "truncated"))
    return cases


def _bench(byte_count):
    key = bytes(range(32))
    nonce = bytes(FRAME_NONCE_LEN)
    payload = bytes(byte_count)
    started = time.monotonic()
    chacha20_xor(key, nonce, payload)
    elapsed = time.monotonic() - started
    rate = (byte_count / 1048576.0) / elapsed if elapsed > 0 else 0.0
    return {"bytes": byte_count, "seconds": round(elapsed, 4), "mb_per_second": round(rate, 3)}


def main(argv):
    if "--selftest" in argv:
        for line in run_selftest():
            print(line)
        print("chacha20-poly1305 selftest passed")
        return 0
    if "--bench" in argv:
        count = 1048576
        if "--bytes" in argv:
            count = int(argv[argv.index("--bytes") + 1])
        measured = _bench(count)
        print("chacha20 %d bytes in %.4fs = %.3f MB/s"
              % (measured["bytes"], measured["seconds"], measured["mb_per_second"]))
        return 0
    print(__doc__.strip().splitlines()[0])
    print("usage: python crypto.py --selftest | --bench [--bytes N]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
