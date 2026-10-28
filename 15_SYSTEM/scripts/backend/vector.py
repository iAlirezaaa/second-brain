"""An embedding seam that is off by default and has nothing to download.

Charter §2 is the law this file answers to: no embedder dependency, no network call, no
activation without a golden-set eval that beats BM25 *and* the owner's explicit approval.
So this module ships the shape of the seam -- `Embedder.embed`, `cosine`, `rank` -- plus one
deterministic test double built from `hashlib`, and ships no model. `gate()` reads the flag
and the evidence and refuses, by name, every activation it cannot justify.

The double is not semantics: it is a stable bag-of-words hash, useful for pinning the
interface and for tests. `production = False` on it is load-bearing -- while the registry
holds no production embedder, activation is refused even with a perfect evidence file.
"""
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

from . import search

CONFIG = Path("15_SYSTEM") / "config" / "system.json"
EVIDENCE = Path("11_CONTROL") / "vector" / "activation.json"
ACTIVATION_KEYS = ("verdict", "bm25", "candidate", "margin", "cases", "cases_sha256",
                   "approved_by", "approved_at")


class Embedder:
    """The one interface a future model must satisfy. `production` is a claim about the
    embedder, and only a real, reviewed model may set it -- the test double may not."""
    name = "abstract"
    dims = 0
    production = False

    def embed(self, text):
        raise NotImplementedError


class HashingEmbedder(Embedder):
    """sha256 bag-of-words, sign-hashed and L2-normalised.

    Deterministic across processes (unlike Python's salted `hash`), offline, dependency
    free. It measures lexical overlap that BM25 already measures -- which is exactly why it
    cannot be evidence *for* vectors. It exists so the seam has a body to test.
    """
    name = "hashing-sha256"
    production = False

    def __init__(self, dims=256):
        if isinstance(dims, bool) or not isinstance(dims, int):
            raise ValueError("dims must be an int")
        if not 8 <= dims <= 4096:
            raise ValueError("dims must be between 8 and 4096")
        self.dims = dims

    def embed(self, text):
        vector = [0.0] * self.dims
        for term in search.tokenize(text):
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % self.dims
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[slot] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector


EMBEDDERS = (HashingEmbedder(),)


def production_embedders():
    return [embedder for embedder in EMBEDDERS if embedder.production]


def _check_vector(vector, dims):
    if len(vector) != dims:
        raise ValueError("vector has %d dims, expected %d" % (len(vector), dims))
    if any(not math.isfinite(value) for value in vector):
        raise ValueError("vector carries a non-finite value")


def cosine(left, right):
    """Cosine of two equal-length vectors. Zero vectors score 0, not an error."""
    if len(left) != len(right):
        raise ValueError("cosine needs equal lengths, got %d and %d" % (len(left), len(right)))
    _check_vector(left, len(left))
    _check_vector(right, len(right))
    dot = sum(a * b for a, b in zip(left, right))
    lnorm = math.sqrt(sum(a * a for a in left))
    rnorm = math.sqrt(sum(b * b for b in right))
    if not lnorm or not rnorm:
        return 0.0
    return dot / (lnorm * rnorm)


def rank(docs, query, embedder, limit=5):
    """Docs as (name, text) pairs -> [(score, name)] with positive scores, best first.

    A pure function: no index on disk, no cache, nothing to invalidate. It is not wired
    into `kb.py` while the flag is false, and `gate()` is what keeps it that way.
    """
    query_vector = embedder.embed(query)
    _check_vector(query_vector, embedder.dims)
    scored = []
    for name, text in docs:
        vector = embedder.embed(text)
        _check_vector(vector, embedder.dims)
        score = cosine(query_vector, vector)
        if score > 0:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[:max(1, min(50, limit))]


def _read_flags(root):
    path = Path(root) / CONFIG
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read %s: %s" % (CONFIG.as_posix(), exc))
    flags = data.get("feature_flags") if isinstance(data, dict) else None
    if not isinstance(flags, dict):
        raise ValueError("%s has no feature_flags object" % CONFIG.as_posix())
    return flags


def _evidence_problems(data):
    """The evidence is judged by shape, not trusted by vibe. A file that cannot answer
    every question below is not evidence, whatever it is named."""
    if not isinstance(data, dict):
        return ["evidence is not a JSON object"]
    missing = [key for key in ACTIVATION_KEYS if key not in data]
    if missing:
        return ["evidence is missing %s" % ", ".join(missing)]
    problems = []
    if data.get("verdict") != "beats_bm25":
        problems.append("verdict is %r, not 'beats_bm25'" % (data.get("verdict"),))
    numbers = {}
    for key in ("bm25", "candidate", "margin"):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(value):
            problems.append("%s is not a finite number" % key)
        else:
            numbers[key] = float(value)
    if len(numbers) == 3:
        if not (0.0 <= numbers["bm25"] <= 1.0 and 0.0 <= numbers["candidate"] <= 1.0):
            problems.append("bm25/candidate must be rates between 0 and 1")
        if numbers["margin"] <= 0:
            problems.append("margin is %r, not a win" % numbers["margin"])
        elif abs((numbers["candidate"] - numbers["bm25"]) - numbers["margin"]) > 1e-9:
            problems.append("margin %r does not equal candidate-bm25 %r"
                            % (numbers["margin"], numbers["candidate"] - numbers["bm25"]))
    cases = data.get("cases")
    if isinstance(cases, bool) or not isinstance(cases, int) or cases < 5:
        problems.append("cases must be an int >= 5 (a golden set, not a demo)")
    if not re.fullmatch(r"[0-9a-f]{64}", str(data.get("cases_sha256") or "")):
        problems.append("cases_sha256 must be the 64-hex digest of the case set that was run")
    if not str(data.get("approved_by") or "").strip():
        problems.append("approved_by is empty -- an agent cannot approve this")
    try:
        date.fromisoformat(str(data.get("approved_at") or ""))
    except ValueError:
        problems.append("approved_at must be an ISO date")
    return problems


def gate(root):
    """Every door, named. Active only when the flag is true, the evidence survives shape
    checks, and a production embedder is registered. Today the last door is always shut,
    on purpose: activation is a tool installation, and tools need the owner's approval."""
    root = Path(root)
    try:
        flags = _read_flags(root)
    except ValueError as exc:
        return {"active": False, "flag": None, "problems": [str(exc)],
                "evidence": EVIDENCE.as_posix()}
    flag = bool(flags.get("vector_search"))
    problems = []
    if not flag:
        problems.append("feature_flags.vector_search is false")
    evidence_path = root / EVIDENCE
    if not evidence_path.is_file():
        problems.append("no activation evidence at %s" % EVIDENCE.as_posix())
    else:
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append("evidence is unreadable: %s" % exc)
        else:
            problems.extend(_evidence_problems(evidence))
    if not production_embedders():
        problems.append("no production embedder is installed; the only one registered is %r, "
                        "a deterministic test double" % EMBEDDERS[0].name)
    return {"active": not problems, "flag": flag, "problems": problems,
            "evidence": EVIDENCE.as_posix(),
            "registered": [embedder.name for embedder in EMBEDDERS]}
