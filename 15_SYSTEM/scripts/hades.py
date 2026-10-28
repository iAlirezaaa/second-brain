"""HADES OS v3 core CLI -- registry, gates and verification.

stdlib only. Run with:  py -3.10 15_SYSTEM/scripts/hades.py <command>

Design commitments (each one exists because v2 broke on it):
  * stdout is forced to UTF-8, so Persian never dies on a Windows console
  * a plan is stamped 'applied' BEFORE any printing, so a print failure
    cannot leave an orphan record behind
  * 15_SYSTEM/schemas/manifest.schema.json is loaded from disk and enforced
    at creation and re-checked by doctor -- it is not decoration
  * .gitignore is cross-checked against config, so the documented boundary and
    the real boundary cannot drift apart
  * a record is amendable, not just creatable: `set` plans an amendment, `apply --approve`
    performs it, the plan is bound to the bytes it was written against, and the record keeps
    its own audit trail -- identity and provenance stay immutable
  * every count printed comes from a live scan of this disk, never from a doc
"""
import sys
import os
import re
import json
import uuid
import shutil
import hashlib
import argparse
import subprocess
from datetime import datetime, date, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "15_SYSTEM/config/system.json"
SCHEMA_PATH = ROOT / "15_SYSTEM/schemas/manifest.schema.json"
GEN = ROOT / "15_SYSTEM/generated"
PLANS = GEN / "plans"

HUMAN_MAX = 10                     # 00..10 human plane
ASCII_SEG = re.compile(r"^[\x20-\x7E]*$")
ID_RE_STRICT = re.compile(r"^[A-Z]{2,6}-[0-9A-F]{8}$")
ID_HEAD_RE = re.compile(r"^[A-Z]{2,6}-[0-9A-F]{8}(-|$)")
# Relations whose values are filesystem paths, not registry ids. Validating these
# as ids would call a correct evidence link a malformed reference.
PATH_RELATIONS = {"evidence_paths"}
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    "github-token": re.compile(r"\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]{10,}\b"),
    "openai-anthropic": re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}\b"),
    "aws-access-id": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "slack-token": re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    "gitlab-token": re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "jwt-or-bearer": re.compile(r"\b(?:eyJ[A-Za-z0-9_-]{10,}|[Bb]earer\s+[A-Za-z0-9._-]{20,})"),
    "labelled-secret": re.compile(r"(?im)^\s*[\"']?(?:api[_-]?key|password|passwd|secret|access[_-]?token|private[_-]?key|auth)[\"']?\s*[:=]\s*[\"']?([^\s\"'#]{8,})"),
}
ENTROPY_TOKEN = re.compile(r"[A-Za-z0-9+/=_-]{24,}")
CJK_RANGES = (0x3000, 0x303F, 0x3040, 0x30FF, 0x3400, 0x4DBF, 0x4E00, 0x9FFF,
              0xAC00, 0xD7AF, 0x0E00, 0x0E7F, 0xFF00, 0xFFEF)
ARABIC_LOOKALIKE = (0x064A, 0x0643, 0x0649, 0x0629, 0x06C1)   # yeh, kaf, alef maksura, teh marbuta, heh goal
# Latin run glued straight onto a Persian/Arabic LETTER. Punctuation (، ؛ ؟), the
# Persian digits and ZWNJ are deliberately outside this class: "API،" is correct
# text, "workflowها" is a defect and "workflow‌ها" (with ZWNJ) is the fix.
# Code points are built with chr() so this file can never itself carry a defect.
GLUED_LETTER_FIRST = chr(0x0627)          # alef
GLUED_LETTER_LAST = chr(0x06CC)           # yeh
GLUED_LETTER_EXCLUDE = "".join(chr(c) for c in (0x0643, 0x0649, 0x064A))  # Arabic kaf / alef maksura / yeh
GLUED_LATIN = re.compile(r"[A-Za-z0-9_\-\.]{2,}["
                         + GLUED_LETTER_FIRST + "-" + GLUED_LETTER_LAST
                         + "^" + GLUED_LETTER_EXCLUDE + "]")


# ---------------------------------------------------------------- utilities
def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return date.today().isoformat()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp-%d" % os.getpid())
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def config():
    return load_json(CONFIG_PATH)


def schema():
    return load_json(SCHEMA_PATH)


def kind_cfg(cfg, kind):
    for k in cfg["kinds"]:
        if k["kind"] == kind:
            return k
    return None


def zone_num(d):
    m = re.match(r"^(\d\d)_", d)
    return int(m.group(1)) if m else -1


def rel(p):
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def new_id(prefix, taken=None):
    for _ in range(200):
        i = "%s-%s" % (prefix, uuid.uuid4().hex[:8].upper())
        if taken is None or i not in taken:
            return i
    raise SystemExit("ERROR: exhausted id space for %s" % prefix)


def ascii_slug(name):
    """Path-safe slug. Persian names produce NO slug: the folder stays pure ASCII
    (the ID) and the Persian name lives in the manifest. Non-ASCII paths are what
    broke Git, task scheduler and gh in v2."""
    t = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return t[:28]


# ---------------------------------------------------------------- discovery
MANIFEST_NAMES = None
REGISTRY_KINDS = None


def registry_kinds(cfg):
    """The kind names the contract declares -- a markdown file is a record only as one of these."""
    global REGISTRY_KINDS
    if REGISTRY_KINDS is None:
        REGISTRY_KINDS = {k["kind"] for k in cfg["kinds"]}
    return REGISTRY_KINDS


def manifest_names(cfg):
    global MANIFEST_NAMES
    if MANIFEST_NAMES is None:
        MANIFEST_NAMES = sorted({k["manifest"] for k in cfg["kinds"]})
    return MANIFEST_NAMES


def iter_records(cfg):
    """Yield (path, record dict) for every registry manifest on disk."""
    skip_parts = {"generated", "backups", "logs", "__pycache__", "templates", "_templates", "_site", "dashboards"}
    names = set(manifest_names(cfg))
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rp = rel(p)
        parts = rp.split("/")
        if any(seg in skip_parts for seg in parts[:-1]):
            continue
        # 12_RUNTIME is disposable harness state, not a registry: a synced skill
        # mirror must never be read back as a second copy of the same record
        if parts[0] == "12_RUNTIME":
            continue
        if parts[0] == "15_SYSTEM" and len(parts) > 1 and parts[1] in ("scripts", "schemas", "config", "migrations", "integrations"):
            continue
        if p.name in names and p.suffix == ".json":
            try:
                obj = load_json(p)
            except Exception as e:
                yield p, {"_parse_error": str(e)}
                continue
            if isinstance(obj, dict) and ("id" in obj or "kind" in obj):
                yield p, obj
        elif p.suffix == ".json" and ID_HEAD_RE.match(p.stem):
            # file-layout kinds (harness, policy, ...) name the manifest after the
            # id, so a name-only match would make them invisible to every gate
            try:
                obj = load_json(p)
            except Exception as e:
                yield p, {"_parse_error": str(e)}
                continue
            if isinstance(obj, dict) and obj.get("id"):
                yield p, obj
        elif p.suffix == ".md":
            # A markdown record is found by its content, not by one filename: file-layout
            # kinds are written as `<ID>-<slug>.md`, so a `stem == "note"` match made every
            # news and wiki_note record `apply` writes invisible to every gate (issue #13).
            # A body (OVERVIEW.md, SKILL.md) carries its record's id with `type: note` and no
            # `kind`, so requiring a declared kind keeps a body from becoming a second record.
            fm = frontmatter(p)
            if fm and ID_RE_STRICT.match(str(fm.get("id") or "")) and fm.get("kind") in registry_kinds(cfg):
                yield p, fm


def frontmatter(path):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    block = text[3:end].strip()
    out, key = {}, None
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w]*)\s*:\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            out[key] = [] if val == "" else parse_scalar(val)
        elif key and re.match(r"^\s*-\s+", line):
            v = re.sub(r"^\s*-\s+", "", line)
            if not isinstance(out[key], list):
                out[key] = [out[key]] if out[key] not in ("", None) else []
            out[key].append(parse_scalar(v))
    return out


def parse_scalar(v):
    t = v.strip()
    if t and t[0] in ("[", "{", '"'):
        # JSON first: a record's relations and amendments are JSON -- what one script
        # writes, another has to be able to read back, or the field is decoration. Dict
        # values and lists whose members carry commas or quotes must round-trip exactly,
        # not be re-split. Hand-written YAML flow lists are not valid JSON, so the
        # splitter below still gets them.
        try:
            return json.loads(t)
        except ValueError:
            pass
    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        return [parse_scalar(x.strip()) for x in inner.split(",") if x.strip()] if inner else []
    if t in ("true", "false"):
        return t == "true"
    if re.match(r"^-?\d+$", t):
        return int(t)
    if re.match(r"^-?\d+\.\d+$", t):
        return float(t)
    return t.strip("'\"")


def zone_dirs(cfg):
    return [z["dir"] for z in cfg["zones"]]


def zone_meta(cfg, name):
    """The config entry for one zone dir, or {} when the dir is not declared."""
    for z in cfg["zones"]:
        if z["dir"] == name:
            return z
    return {}


def gitignore_lines():
    path = ROOT / ".gitignore"
    if not path.is_file():
        return []
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]


def absent_by_boundary(cfg, name, gi):
    """True when a zone is missing *because the documented git boundary says so*.

    The machine plane (12_RUNTIME, 13_LAB) is disposable local state: .gitignore
    excludes it on purpose, so a fresh clone can never contain it. Reporting that
    as a defect would make doctor un-green for every user of the published repo --
    exactly the class of claim that must be measured, not remembered. A human-plane
    zone is never excusable; a machine zone is excused only when config AND
    .gitignore agree that it is out of version control.
    """
    meta = zone_meta(cfg, name)
    if meta.get("plane") != "machine":
        return False
    # 14_CANDIDATES is quarantined but its loop shelf is tracked by exception,
    # so its absence is a real defect, not the documented boundary
    if meta.get("tracked_exception"):
        return False
    return bool(meta.get("gitignore_required")) and (name + "/") in gi


def denied_prefixes(cfg):
    out = []
    for z in cfg["zones"]:
        if z.get("denied_for_default_context"):
            out.append(z["dir"])
    for z in cfg["zones"]:
        if z.get("generated_denied"):
            out.append(z["dir"] + "/generated")
    return out


def is_denied(path_rel, cfg):
    return any(path_rel.startswith(d) for d in denied_prefixes(cfg))


# ---------------------------------------------------------------- validation
def type_ok(value, t):
    return {
        "string": lambda v: isinstance(v, str),
        "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "bool": lambda v: isinstance(v, bool),
        "array": lambda v: isinstance(v, list),
        "object": lambda v: isinstance(v, dict),
    }.get(t, lambda v: True)(value)


def validate(record, cfg, sch, path=None):
    """Return list of problem strings for one record."""
    problems = []
    kind = record.get("kind")
    if "_parse_error" in record:
        return ["unreadable json: %s" % record["_parse_error"]]
    kc = kind_cfg(cfg, kind) if kind else None
    if not kind:
        return ["missing 'kind'"]
    if not kc:
        return ["kind '%s' is not declared in config" % kind]
    idr = record.get("id", "")
    if not ID_RE_STRICT.match(idr):
        problems.append("id '%s' does not match %s" % (idr, sch["id_pattern"]))
    elif not idr.startswith(kc["prefix"] + "-"):
        problems.append("id prefix '%s' wrong for kind %s (want %s)" % (idr.split('-')[0], kind, kc["prefix"]))
    for f in sch["common_required"]:
        if f not in record:
            problems.append("missing required field '%s'" % f)
    for f, t in sch["common_types"].items():
        if f in record and not type_ok(record[f], t):
            problems.append("field '%s' should be %s" % (f, t))
    ks = kc["kind"]
    spec = sch["by_kind"].get(ks) or sch["by_kind"].get(kc["kind"]) or {}
    for f in spec.get("required", []):
        if f not in record:
            problems.append("kind %s requires '%s'" % (ks, f))
        elif isinstance(record[f], str) and not record[f].strip():
            # an empty string is the field being present in name only: provenance
            # written as "" cites nothing, so it must not pass as a value
            problems.append("kind %s requires a non-empty '%s'" % (ks, f))
    for f, t in spec.get("types", {}).items():
        if f in record and not type_ok(record[f], t):
            problems.append("kind %s: field '%s' should be %s" % (ks, f, t))
    statuses = cfg["status_sets"].get(ks, cfg["status_sets"]["default"])
    st = record.get("status")
    if st and st not in statuses:
        problems.append("status '%s' not allowed for %s (allowed: %s)" % (st, ks, "|".join(statuses)))
    cl = record.get("classification")
    if cl and cl not in cfg["allowed_classifications"]:
        problems.append("classification '%s' not allowed" % cl)
    if spec.get("evidence_paths_must_exist"):
        ev = record.get("evidence_paths") or []
        if not ev:
            problems.append("evidence_paths is empty -- a claim without a witness")
        for e in ev:
            if not (ROOT / e).exists():
                problems.append("evidence path missing on disk: %s" % e)
    # folder placement
    if path is not None:
        rp = rel(path)
        if not rp.startswith(kc["zone"] + "/"):
            problems.append("record for kind %s sits outside its zone %s" % (ks, kc["zone"]))
        containers = kc["container"].split("|")
        seg = rp.split("/")
        if len(seg) > 2 and seg[1] not in containers:
            problems.append("folder '%s' is not a declared container for %s (allowed: %s)" % (seg[1], ks, "|".join(containers)))
        for segp in seg[:-1]:
            if not ASCII_SEG.match(segp):
                problems.append("non-ASCII path segment '%s' (registry paths must be ASCII)" % segp)
        # status vs folder for projects
        if ks == "project" and st in ("incubating", "active", "paused", "completed") and seg[1] != st:
            problems.append("project status '%s' disagrees with folder '%s'" % (st, seg[1]))
    return problems


def check_relations(records, cfg):
    ids = {r.get("id") for _, r in records}
    problems = []

    def ref(p, k, t):
        if k in PATH_RELATIONS:
            if not isinstance(t, str):
                problems.append((p, "evidence path is not a string: %r" % t))
            elif not (ROOT / t).exists():
                problems.append((p, "evidence file does not exist: %s" % t))
            return
        if not isinstance(t, str):
            problems.append((p, "relation %s holds a non-string target %r" % (k, t)))
            return
        # A target that is not shaped like an ID is the more dangerous case: it
        # can never resolve, and a typo reads like a valid link.
        if not ID_RE_STRICT.match(t):
            problems.append((p, "malformed id reference %s -> '%s' (must match PREFIX-8HEX)" % (k, t)))
        elif t not in ids:
            problems.append((p, "dangling relation %s -> %s" % (k, t)))

    for p, r in records:
        for k, v in (r.get("relations") or {}).items():
            if k not in cfg["relations"]:
                problems.append((p, "unknown relation '%s'" % k))
            for t in (v if isinstance(v, list) else [v]):
                ref(p, k, t)
        for k in cfg["relations"]:
            if k in r and isinstance(r[k], list):
                for t in r[k]:
                    ref(p, k, t)
    return problems


def strip_pattern_defs(text, path):
    """The scanner must not flag its own regex source. In .py files, lines that
    define patterns are blanked before matching; every other line is still scanned."""
    if path.suffix != ".py":
        return text
    return "\n".join("" if "re.compile" in ln else ln for ln in text.splitlines())


def scan_secrets(root_dirs, cfg, limit_mb=8):
    hits = []
    exts = {".md", ".json", ".txt", ".yaml", ".yml", ".ps1", ".bat", ".py"}
    for z in root_dirs:
        for p in sorted((ROOT / z).rglob("*")) if (ROOT / z).exists() else []:
            if not p.is_file() or p.suffix not in exts:
                continue
            if any(seg in ("generated", "backups", "__pycache__") for seg in p.parts):
                continue
            try:
                if p.stat().st_size > limit_mb * 1024 * 1024:
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            text = strip_pattern_defs(text, p)
            names = [n for n, pat in SECRET_PATTERNS.items() if pat.search(text)]
            if not names:
                for m in ENTROPY_TOKEN.finditer(text):
                    tok = m.group()
                    uniq = len(set(tok)) / len(tok)
                    if uniq > 0.72 and re.search(r"[A-Za-z]", tok) and re.search(r"\d", tok):
                        before = text[max(0, m.start() - 40):m.start()]
                        if re.search(r"(?i)(key|token|secret|password|auth|credential)\W{0,4}$", before.strip()):
                            names.append("high-entropy-token")
                            break
            if names:
                hits.append((rel(p), names))
    return hits


def scan_fa(files):
    """Persian hygiene gate: CJK/kana/hangul/thai, Arabic lookalikes, glued Latin."""
    bad = []
    cjk = "[" + "".join(chr(a) + "-" + chr(b) for a, b in zip(CJK_RANGES[::2], CJK_RANGES[1::2])) + "]"
    kre = re.compile(cjk)
    lookalike = [chr(c) for c in ARABIC_LOOKALIKE]
    for f in files:
        try:
            t = Path(f).read_text(encoding="utf-8")
        except Exception:
            continue
        hits = {}
        c = len(kre.findall(t))
        if c:
            hits["cjk"] = c
        la = {hex(ord(x)): t.count(x) for x in lookalike if x in t}
        if la:
            hits["arabic_lookalike"] = la
        g = set(GLUED_LATIN.findall(t))
        if g:
            hits["glued_latin"] = list(g)[:5]
        if hits:
            bad.append((rel(Path(f)), hits))
    return bad


def fa_doc_files():
    """Persian prose the owner authored. Excluded: 12_RUNTIME (disposable),
    13_LAB (unjudged), 15_SYSTEM/generated (rebuilt). 15_SYSTEM/templates and
    integrations are shipped text, so they are inspected -- a defect in a
    template is copied into every record made from it."""
    out = []
    for p in list(ROOT.rglob("*.md")) + list(ROOT.rglob("*.txt")):
        rp = rel(p)
        if rp.startswith(("00_", "01_", "02_", "03_", "04_", "05_", "06_", "07_", "08_", "09_", "10_", "11_", "14_")):
            out.append(p)
        elif rp.startswith(("15_SYSTEM/templates/", "15_SYSTEM/integrations/", "15_SYSTEM/migrations/")):
            out.append(p)
    for name in ("README.md", "AGENTS.md"):
        p = ROOT / name
        if p.exists():
            out.append(p)
    return out


def counts_by(records):
    by_kind, by_zone = {}, {}
    for p, r in records:
        by_kind[r.get("kind", "?")] = by_kind.get(r.get("kind", "?"), 0) + 1
        by_zone[rel(p).split("/")[0]] = by_zone.get(rel(p).split("/")[0], 0) + 1
    return by_kind, by_zone


# ---------------------------------------------------------------- commands
def cmd_status(cfg):
    recs = list(iter_records(cfg))
    retired = superseded_by(recs)
    bk, bz = counts_by(recs)
    print("HADES OS v3 | root %s" % ROOT)
    print("registry records: %d" % len(recs))
    if retired:
        print("superseded (retired from the active index): %d of %d -- %s"
              % (len(retired), len(recs), ", ".join(sorted(retired))))
    print("by kind: %s" % (json.dumps(bk, ensure_ascii=False, sort_keys=True) if bk else "{}"))
    print("by zone: %s" % (json.dumps(bz, ensure_ascii=False, sort_keys=True) if bz else "{}"))
    zones = zone_dirs(cfg)
    gi = gitignore_lines()
    present = [z for z in zones if (ROOT / z).exists()]
    excused = [z for z in zones if not (ROOT / z).exists() and absent_by_boundary(cfg, z, gi)]
    missing = [z for z in zones if not (ROOT / z).exists() and z not in excused]
    print("zones on disk: %d/%d" % (len(present), len(zones)))
    if excused:
        print("absent at the documented git boundary (machine plane, never versioned): %s"
              % ", ".join(excused))
    if missing:
        print("absent and NOT excused by the boundary: %s" % ", ".join(missing))
    return 0


def skill_entrypoint(name):
    """Where a skill's body actually lives, so the record cannot be born pointing at nothing.

    The definition stays in 11_CONTROL (that is the plane of laws) and the prose body stays
    in skills/<name>/SKILL.md (that is what every agent host reads). One of the two has to
    be a pointer, and a pointer that has not been checked is how a registry starts lying.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    candidate = ROOT / "skills" / slug / "SKILL.md"
    return "skills/%s/SKILL.md" % slug if candidate.is_file() else "SKILL.md"


def check_entrypoints(path, rec):
    """Every file an agent is told to open has to exist -- record-local or vault-relative."""
    entry = str(rec.get("entrypoint") or "").strip()
    if not entry:
        return []
    local, from_root = path.parent / entry, ROOT / entry
    if local.is_file() or from_root.is_file():
        return []
    return ["entrypoint '%s' does not exist (looked for %s and %s) -- a definition whose "
            "body is missing is a promise, not a capability" %
            (entry, rel(local), rel(from_root))]


def cmd_doctor(cfg, sch, as_json=False):
    errors, warnings = [], []
    zones = zone_dirs(cfg)
    gi = gitignore_lines()
    boundary_absent = []
    for z in zones:
        d = ROOT / z
        if not d.exists():
            # the published repo cannot contain the disposable machine plane;
            # that is the boundary, so say where it is instead of calling it a defect
            if absent_by_boundary(cfg, z, gi):
                boundary_absent.append(z)
            else:
                errors.append("missing zone: %s" % z)
            continue
        if absent_by_boundary(cfg, z, gi):
            # the zone exists on this machine only as disposable local state -- its
            # README could never be tracked, so the tracked-plane law stops at the
            # boundary instead of demanding an untrackable file
            continue
        if not (d / "README.md").exists():
            errors.append("zone without README: %s" % z)
    recs = list(iter_records(cfg))
    seen = {}
    for p, r in recs:
        rid = r.get("id")
        if rid in seen:
            errors.append("duplicate id %s in %s and %s" % (rid, rel(seen[rid]), rel(p)))
        seen[rid] = p
        for prob in validate(r, cfg, sch, p):
            errors.append("%s: %s" % (rel(p), prob))
    for p, prob in check_relations(recs, cfg):
        errors.append("%s: %s" % (rel(p), prob))
    # a record that points at a file which is not there is not a definition, it is a rumour
    for p, r in recs:
        for prob in check_entrypoints(p, r):
            errors.append("%s: %s" % (rel(p), prob))
    # registry manifests inside the disposable plane = knowledge stranded in machine
    # state; 12_RUNTIME is never enumerated as a registry, so scan it directly
    names = set(manifest_names(cfg))
    rt = ROOT / "12_RUNTIME"
    # a harness's declared skills_dir is a sanctioned mirror, not a stranded record
    mirrors = []
    for _, r in recs:
        if r.get("kind") == "harness" and r.get("skills_dir"):
            mirrors.append(r["skills_dir"].strip("/"))
    if rt.exists():
        for p in sorted(rt.rglob("*.json")):
            rp = rel(p)
            if any(rp.startswith(m + "/") for m in mirrors):
                continue
            if p.name in names or ID_HEAD_RE.match(p.stem):
                errors.append("%s: registry manifest inside 12_RUNTIME (promote it to the human plane instead)" % rp)
    # stale dated claims
    for p, r in recs:
        lv = r.get("last_verified") or r.get("observed_at")
        if lv:
            try:
                d = date.fromisoformat(str(lv)[:10])
                if (date.today() - d).days > cfg["stale_after_days"]:
                    warnings.append("%s: last verified %s (%d days ago) -- treat as unverified" % (rel(p), lv, (date.today() - d).days))
            except Exception:
                warnings.append("%s: unparseable date '%s'" % (rel(p), lv))
    # git boundary drift
    for need in cfg["gitignore_required_paths"]:
        if need not in gi:
            errors.append(".gitignore does not exclude %s though config requires it" % need)
    # nested repos inside the vault
    # The vault's own .git is the vault: a published repo cloned as a vault is the
    # normal case, not a stranded project repo. Only .git *below* the root counts.
    for g in ROOT.rglob(".git"):
        if g.is_dir() and g.parent != ROOT:
            errors.append("nested git repo inside the vault: %s" % rel(g.parent))
    # secrets and utf-8
    for p, names in scan_secrets(zones, cfg):
        errors.append("%s: possible secret (%s)" % (p, ",".join(names)))
    for z in zones:
        d = ROOT / z
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".json", ".txt"):
                try:
                    f.read_text(encoding="utf-8")
                except Exception:
                    errors.append("%s: not valid UTF-8" % rel(f))
    fa = scan_fa(fa_doc_files())
    for p, hits in fa:
        warnings.append("%s: persian hygiene %s" % (p, json.dumps(hits, ensure_ascii=False)))
    # retirement is a verdict about a record, and a verdict the index ignores is a second
    # definition of the same thing that nobody has to answer for
    retired = superseded_by(recs)
    for p, r in recs:
        targets = (r.get("relations") or {}).get("supersedes") or []
        if isinstance(targets, str):
            targets = [targets]
        if r.get("id") in [t for t in targets if isinstance(t, str)]:
            errors.append("%s: supersedes itself -- a record cannot retire its own identity; "
                          "file the replacement and link that one" % rel(p))
    rec_n = len([1 for _p, r in recs if r.get("id") not in retired])
    if as_json:
        print(json.dumps({"records": rec_n, "superseded": sorted(retired),
                          "errors": errors, "warnings": warnings,
                          "zones_absent_at_git_boundary": boundary_absent,
                          "flags": cfg["feature_flags"]}, ensure_ascii=False, indent=2))
    else:
        print("HADES OS v3 doctor")
        print("scanned zones: %d | registry records: %d" % (len([z for z in zones if (ROOT / z).exists()]), rec_n))
        if retired:
            print("superseded (retired from the active index): %s" % ", ".join(
                "%s by %s" % (k, retired[k]) for k in sorted(retired)))
        if boundary_absent:
            print("absent at the documented git boundary: %s" % ", ".join(boundary_absent))
        print("errors: %d | warnings: %d" % (len(errors), len(warnings)))
        for e in errors:
            print("  ERROR %s" % e)
        for w in warnings:
            print("  warn  %s" % w)
        off = [k for k, v in cfg["feature_flags"].items() if not v]
        print("not enforced by this package (documented, not silently claimed): %s" % ", ".join(off))
    return 1 if errors else 0


def superseded_by(recs):
    """{retired id: the record that retires it} -- what `supersedes` is declared to mean.

    system.json says a superseding record "replaces a record; superseded leaves the active
    index". Until the index and the gate read the relation, that sentence was a comment and
    the plane kept two definitions of one thing while printing `errors: 0` (issue #12).
    """
    out = {}
    for _p, r in recs:
        targets = (r.get("relations") or {}).get("supersedes") or []
        if isinstance(targets, str):
            targets = [targets]
        for target in targets:
            if isinstance(target, str) and target != r.get("id"):
                out.setdefault(target, r.get("id"))
    return out


def cmd_index(cfg):
    recs = list(iter_records(cfg))
    retired = superseded_by(recs)
    items, retired_items, bad = [], [], 0
    for p, r in recs:
        if "_parse_error" in r:
            bad += 1
            continue
        item = {"id": r.get("id"), "kind": r.get("kind"), "name": r.get("name"),
                "status": r.get("status"), "classification": r.get("classification"),
                "path": rel(p), "zone": rel(p).split("/")[0],
                "plane": "human" if zone_num(rel(p).split("/")[0]) <= HUMAN_MAX else "machine",
                "last_verified": r.get("last_verified") or r.get("observed_at")}
        if r.get("id") in retired:
            item["superseded_by"] = retired[r.get("id")]
            retired_items.append(item)
            continue
        items.append(item)
    GEN.mkdir(parents=True, exist_ok=True)
    PLANS.mkdir(parents=True, exist_ok=True)
    out = {"schema_version": cfg["schema_version"], "generated_at_utc": now(),
           "scope": "canonical metadata; excludes 12_RUNTIME, 13_LAB, 14_CANDIDATES and every "
                    "record another record supersedes",
           "count": len(items), "unreadable": bad,
           "superseded_count": len(retired_items),
           "superseded": sorted(retired_items, key=lambda x: str(x["id"])),
           "records": sorted(items, key=lambda x: str(x["id"]))}
    dump_json(GEN / "catalog.json", out)
    print("indexed %d records (%d unreadable) -> %s" % (len(items), bad, rel(GEN / "catalog.json")))
    if retired_items:
        print("superseded, left the active index: %s" % ", ".join(
            "%s (by %s)" % (i["id"], i["superseded_by"]) for i in sorted(
                retired_items, key=lambda x: str(x["id"]))))
    return 0


def resolve_container(cfg, kc, args):
    containers = kc["container"].split("|")
    if args.container:
        if args.container not in containers:
            raise SystemExit("ERROR: container '%s' not allowed for kind %s (allowed: %s)" % (args.container, kc["kind"], "|".join(containers)))
        return containers[containers.index(args.container)]
    if args.kind == "project":
        st = args.status or "incubating"
        return st if st in containers else "incubating"
    return containers[0]


def make_obj(cfg, kind, name, args, ident):
    kc = kind_cfg(cfg, kind)
    obj = {"kind": kc["kind"], "id": ident, "name": name, "status": args.status or
           (cfg["status_sets"].get(kind, cfg["status_sets"]["default"])[0]),
           "classification": args.classification or cfg["default_classification"],
           "created_at": today(), "tags": (args.tags.split(",") if args.tags else []),
           "relations": {}}
    if args.description:
        obj["notes"] = args.description
    defaults = {
        "project": lambda: obj.update({"type": args.type or "program",
                                       "repo": {"path": "", "remote": "", "branch": "main"}}),
        "organization": lambda: obj.update({"official_url": args.url or ""}),
        "model": lambda: obj.update({"category": args.category or "other_emerging", "organization_id": args.org or "", "versions": []}),
        "model_version": lambda: obj.update({"model_id": args.model or "", "version": args.version or "v1"}),
        "news": lambda: obj.update({"source_url": args.url or "", "observed_at": today(), "claim": args.description or ""}),
        "benchmark": lambda: obj.update({"model_version_id": args.model or "", "metric": args.metric or "score", "score": 0.0}),
        "prompt": lambda: obj.update({"body_path": "PROMPT.md"}),
        "workflow": lambda: obj.update({"engine": args.engine or "other", "body_path": "workflow.json"}),
        "asset": lambda: obj.update({"path_ref": args.path or "", "sha256": "", "size_bytes": 0}),
        "deliverable": lambda: obj.update({"project_id": args.project or "", "produced_by": args.produced_by or "", "uses_model_ids": []}),
        "channel": lambda: obj.update({"platform": args.platform or "other"}),
        "episode": lambda: obj.update({"channel_id": args.channel or ""}),
        "campaign": lambda: obj.update({"channel_ids": [], "starts": today()}),
        "app": lambda: obj.update({"app_type": args.type or "app"}),
        "tutorial": lambda: obj.update({"topic": args.category or "general"}),
        "task": lambda: obj.update({"project_id": args.project or ""}),
        "decision": lambda: obj.update({"decision": args.description or "", "decided_on": today(), "reversible": True}),
        "wiki_note": lambda: obj.update({"topic": args.category or "concept", "cites_ids": []}),
        "agent": lambda: obj.update({"capabilities": (args.capabilities.split(",") if args.capabilities else []),
                                     "read_scope": [z["dir"] for z in cfg["zones"] if z["plane"] == "human"],
                                     "write_scope": [], "tool_allowlist": [], "memory_policy": "promote-only",
                                     "approved_for_harness_ids": []}),
        "subagent": lambda: obj.update({"parent_agent_id": args.agent or "", "capabilities": [], "tool_allowlist": []}),
        "skill": lambda: obj.update({"entrypoint": skill_entrypoint(name),
                                     "description": args.description or "",
                                     "approved_for_harness_ids": []}),
        "mcp": lambda: obj.update({"transport": args.transport or "stdio", "endpoint_or_command": args.endpoint or "", "tools_exposed": []}),
        "hook": lambda: obj.update({"event": args.event or "on_save", "action": args.action or "", "enabled": False}),
        "command": lambda: obj.update({"invocation": args.invocation or "/" + (args.name_slug or name.lower()), "effect": args.description or ""}),
        "mode": lambda: obj.update({"read_scope": ["00_START_HERE"], "write_scope": [], "approval_policy": "ask"}),
        "loop": lambda: obj.update({"schedule": args.schedule or "manual", "action": args.action or "", "mode_id": args.mode or ""}),
        "harness": lambda: obj.update({"runtime_name": args.runtime or name, "memory_paths": [], "config_paths": [], "supports": []}),
        "plugin": lambda: obj.update({"provides": []}),
        "template": lambda: obj.update({"applies_to_kind": args.template_kind or "project"}),
        "policy": lambda: obj.update({"applies_to": [], "rule": args.description or ""}),
        "sandbox": lambda: obj.update({"isolation": args.isolation or "none", "credentials": "none", "network": "none"}),
        "experiment": lambda: obj.update({"goal": args.description or "", "isolation": args.isolation or "none",
                                          "evaluation": {"passed": False, "metric": "", "score": None}}),
        "candidate": lambda: obj.update({"source_experiment_id": args.experiment or "",
                                         "evaluation": {"passed": False, "metric": "", "score": None},
                                         "safety_review": {"passed": False, "note": ""},
                                         "human_approved": False, "evidence_paths": []}),
    }
    if kind in defaults:
        defaults[kind]()
    if args.parent:
        obj["relations"]["parent_ids"] = [args.parent]
    if args.depends_on:
        obj["relations"]["depends_on"] = [args.depends_on]
    if args.variant_of:
        obj["relations"]["variant_of"] = args.variant_of
    return obj


def target_path(cfg, kc, obj, container):
    slug = ascii_slug(obj["name"])
    folder_name = "%s-%s" % (obj["id"], slug) if slug else obj["id"]
    base = ROOT / kc["zone"] / container
    if kc["layout"] in ("folder", "subfolder"):
        if kc["layout"] == "subfolder":
            parent = ROOT / kc["zone"] / container / (obj.get("model_id") or "MOD-UNKNOWN")
            return parent / "versions" / folder_name / kc["manifest"]
        return base / folder_name / kc["manifest"]
    suffix = ".md" if kc["manifest"] == "note.md" else ".json"
    return base / (folder_name + suffix)


def cmd_plan(cfg, args):
    kc = kind_cfg(cfg, args.kind)
    if not kc:
        raise SystemExit("ERROR: unknown kind '%s' (see config kinds)" % args.kind)
    obj = make_obj(cfg, kc["kind"], args.name, args, new_id(kc["prefix"], taken=existing_ids(cfg)))
    container = resolve_container(cfg, kc, args)
    tp = target_path(cfg, kc, obj, container)
    plan = {"plan_id": "PLAN-" + uuid.uuid4().hex[:12].upper(), "created_utc": now(),
            "applied": False, "target_kind": kc["kind"], "container": container,
            "target_path": rel(tp), "record": obj}
    PLANS.mkdir(parents=True, exist_ok=True)
    dump_json(PLANS / (plan["plan_id"] + ".json"), plan)
    print("PLAN %s | kind %s | id %s | path %s" % (plan["plan_id"], kc["kind"], obj["id"], rel(tp)))
    print("review it, then: hades.py apply --plan %s --approve" % plan["plan_id"])
    return 0


def existing_ids(cfg):
    return {r.get("id") for _, r in iter_records(cfg)}


def find_record(cfg, ident):
    """(path, record) for one registry id, or None -- the lookup every writer shares."""
    for p, r in iter_records(cfg):
        if r.get("id") == ident:
            return (p, r)
    return None


# Identity and provenance: changing one of these is not correcting a record, it is a
# different record. Retirement is what `supersedes` is for; `set` cannot rewrite history.
IMMUTABLE_FIELDS = ("id", "kind", "created_at")
# the audit trail is written by the tool that made the change, never typed by hand
LEDGER_FIELDS = ("amendments",)


def parse_value(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def pre_image_sha(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


def cmd_set(cfg, sch, args):
    """Amend one field of an applied record -- through a plan, approved like a creation.

    The registry used to be create-only, so the only way to correct a definition was to
    file a second record for the same thing (issue #12). An amendment is not a file edit:
    it is an approved structural change, validated against the same contract before a
    single byte moves, bound to the bytes it was written against, and stamped into the
    record's own history.
    """
    hit = find_record(cfg, args.id)
    if not hit:
        raise SystemExit("ERROR: no record %s" % args.id)
    path, rec = hit
    if args.field in IMMUTABLE_FIELDS:
        print("REFUSED: '%s' is identity or provenance -- changing it makes a different record, "
              "it does not correct this one. File the new one and retire this one: "
              "hades.py link --id NEW --rel supersedes --to %s" % (args.field, args.id))
        return 2
    if args.field in LEDGER_FIELDS or args.field.startswith("_"):
        print("REFUSED: '%s' is written by the tool that made the change, not typed into it"
              % args.field)
        return 2
    known = set(sch.get("common_required", [])) | set(sch.get("common_types", {}))
    spec = sch["by_kind"].get(rec.get("kind") or "", {})
    known |= set(spec.get("required", [])) | set(spec.get("types", {})) | set(rec)
    if args.field not in known:
        print("REFUSED: unknown field '%s' for kind %s and the record does not carry it "
              "-- a typo would silently add a second truth" % (args.field, rec.get("kind")))
        return 2
    value = parse_value(args.value)
    amended = json.loads(json.dumps(rec))
    amended[args.field] = value
    amended["updated_at"] = now()
    problems = validate(amended, cfg, sch, path) + check_entrypoints(path, amended)
    if problems:
        print("REFUSED: the amended record fails its own contract, nothing was planned")
        for problem in problems:
            print("  %s" % problem)
        return 2
    plan = {"plan_id": "PLAN-" + uuid.uuid4().hex[:12].upper(), "created_utc": now(),
            "applied": False, "mode": "amend", "target_kind": rec.get("kind"),
            "record_id": args.id, "target_path": rel(path), "field": args.field,
            "from": rec.get(args.field), "to": value, "pre_image_sha1": pre_image_sha(path),
            "record": amended}
    PLANS.mkdir(parents=True, exist_ok=True)
    dump_json(PLANS / (plan["plan_id"] + ".json"), plan)
    print("PLAN %s | amend %s --field %s | %s -> %s"
          % (plan["plan_id"], args.id, args.field,
             json.dumps(rec.get(args.field), ensure_ascii=False),
             json.dumps(value, ensure_ascii=False)))
    print("review it, then: hades.py apply --plan %s --approve" % plan["plan_id"])
    if args.approve:
        args.plan = plan["plan_id"]
        return cmd_apply(cfg, sch, args)
    return 0


def cmd_apply_amend(cfg, sch, plan, pf):
    """Perform an approved amendment, or refuse without touching the record."""
    path = ROOT / plan["target_path"]
    if not path.is_file():
        print("REFUSED: the record this plan amends is no longer at %s" % plan["target_path"])
        return 2
    if pre_image_sha(path) != plan.get("pre_image_sha1"):
        print("REFUSED: STALE plan -- the record moved after this plan was written, so the "
              "plan describes a state that no longer exists. Look at the record, then plan again.")
        return 2
    amended = plan["record"]
    problems = validate(amended, cfg, sch, path) + check_entrypoints(path, amended)
    if problems:
        print("REFUSED: the amended record fails its own contract, nothing was written")
        for problem in problems:
            print("  %s" % problem)
        return 2
    entry = {"field": plan["field"], "from": plan["from"], "to": plan["to"], "utc": now(),
             "plan": plan["plan_id"]}
    amended.setdefault("amendments", []).append(entry)
    if path.suffix == ".md":
        path.write_text(to_markdown(amended), encoding="utf-8")
    else:
        dump_json(path, amended)
    # THE ORDER MATTERS: stamp the plan before any printing, so a console failure cannot leave
    # an applied amendment looking unexecuted and invite a second one. The pre-image check is
    # what makes a repeat safe: the bytes already moved, so the plan can only be STALE now.
    plan["applied"] = True
    plan["applied_utc"] = now()
    dump_json(pf, plan)
    print("AMENDED %s --field %s -> %s" % (plan["record_id"], plan["field"], rel(path)))
    print("next: hades.py doctor && hades.py index")
    return 0


def cmd_apply(cfg, sch, args):
    if not args.approve:
        print("REFUSED: apply needs --approve (nothing was written)")
        return 2
    pf = PLANS / (args.plan + ".json")
    if not pf.exists():
        raise SystemExit("ERROR: no such plan: %s" % args.plan)
    plan = load_json(pf)
    if plan.get("applied"):
        print("REFUSED: plan already applied -> %s" % plan.get("target_path"))
        return 2
    if plan.get("mode") == "amend":
        return cmd_apply_amend(cfg, sch, plan, pf)
    obj = plan["record"]
    kc = kind_cfg(cfg, obj["kind"])
    tp = ROOT / plan["target_path"]
    if tp.exists():
        raise SystemExit("ERROR: target already exists, refusing to overwrite: %s" % rel(tp))
    problems = validate(obj, cfg, sch, tp)
    if problems:
        print("REFUSED: record fails its own contract before being written")
        for p in problems:
            print("  %s" % p)
        return 2
    tp.parent.mkdir(parents=True, exist_ok=True)
    if tp.suffix == ".md":
        tp.write_text(to_markdown(obj), encoding="utf-8")
    else:
        dump_json(tp, obj)
    # scaffolds are written once, at creation: an amendment edits the record, it
    # does not regenerate the prose bodies a human may already have extended
    if kc["kind"] == "skill":
        if obj.get("entrypoint") == "SKILL.md":
            # a scaffold body only for a skill that has no prose yet: when the pack already
            # holds skills/<name>/SKILL.md the record points at it, and a second body in the
            # record folder is a parallel truth waiting to disagree
            (tp.parent / "SKILL.md").write_text(skill_md(obj), encoding="utf-8")
        for sub in ("scripts", "references", "tests"):
            (tp.parent / sub).mkdir(exist_ok=True)
    if kc["kind"] in ("project", "agent", "subagent"):
        (tp.parent / "OVERVIEW.md").write_text(overview_md(obj), encoding="utf-8")
    # THE ORDER MATTERS: stamp applied first, then print. v2 printed first and a
    # console encoding failure left an unmarked plan plus a duplicate project.
    plan["applied"] = True
    plan["applied_utc"] = now()
    plan["applied_path"] = rel(tp)
    dump_json(pf, plan)
    print("APPLIED %s -> %s" % (obj["id"], rel(tp)))
    print("next: hades.py doctor && hades.py index")
    return 0


def to_markdown(obj):
    """Full-fidelity markdown rendering of a record.

    The markdown layout is round-tripped by iter_records and rewritten by `link` and
    by amendments, so the file may not drop fields: whatever the record dict carries
    goes into the frontmatter (dicts as inline JSON), or `link --rel supersedes ...`
    on a markdown record would silently throw the edge away (issue #13). claim/notes
    render into the visible body for humans AND stay in the frontmatter, so the
    roundtrip cannot lose them either.
    """
    first = ("id", "kind", "name", "status", "classification", "created_at", "updated_at",
             "last_verified", "source_url", "observed_at", "topic", "tags")
    front = ["---"]
    emitted = set()
    for k in first:
        if k in obj and obj[k] is not None:
            front.append("%s: %s" % (k, json.dumps(obj[k], ensure_ascii=False)))
            emitted.add(k)
    # Every field the record carries rides in the frontmatter, prose included: a rewrite
    # (an amendment or a link) reads the frontmatter, so a field that only lived in the
    # rendered body would be deleted by being re-rendered -- what one script writes,
    # another has to be able to read back whole. The body still renders claim/notes for
    # humans; the frontmatter copy is so the roundtrip cannot lose them.
    for k in sorted(obj):
        if k in emitted or obj[k] is None:
            continue
        front.append("%s: %s" % (k, json.dumps(obj[k], ensure_ascii=False)))
    front.append("---")
    text = "\n".join(front) + "\n\n# %s\n\n" % obj.get("name", obj.get("id"))
    if obj.get("claim") or obj.get("notes"):
        text += (obj.get("claim") or obj.get("notes")) + "\n\n"
    text += "## منبع\n\n%s\n\n" % (obj.get("source_url") or "ثبت‌نشده -- بدون منبع، این ادعا را نقل نکن")
    text += "## وضعیت\n\n`%s` | مشاهده در `%s` | آخرین بررسی: `%s`\n" % (
        obj.get("status"), obj.get("observed_at", ""), obj.get("last_verified", ""))
    return text


def overview_md(obj):
    """A record's summary is a note, so it carries note frontmatter like every other note.

    Files the scripts write are judged by the same gates as files the human writes. A bare
    markdown summary passes in the repo -- the vault gates scan the template -- and fails in
    an installed brain, where 11_CONTROL sits inside the scanned root. Same bytes either way
    is the only version nobody has to remember.
    """
    stamp = str(obj.get("created_at") or today())
    kind = "project" if obj.get("kind") == "project" else "note"
    topics = obj.get("tags") or [str(obj.get("kind") or "record")]
    return ('---\nid: %s\ntype: %s\ntitle: "OVERVIEW — %s"\nstatus: raw\nowner: agent\n'
            'topics: [%s]\ncreated: %s\nupdated: %s\n---\n\n# %s\n\n> %s\n\n'
            "وضعیت رکورد: %s | شناسه: %s\n\n## بعدی\n\n"
            "- [ ] هدف و محدودیت را بنویس\n- [ ] رابطه‌ها را وصل کن\n") % (
        obj["id"], kind, obj["name"], ", ".join(str(t) for t in topics), stamp, stamp,
        obj["name"], obj.get("notes", ""), obj["status"], obj["id"])


def skill_md(obj):
    return "---\nname: %s\ndescription: %s\n---\n\n# %s\n\n%s\n\n## مرزها\n\n" \
        "بدون تأیید صریح: هیچ انتشار بیرونی، هیچ دسترسی به ۱۲/۱۳/۱۴، هیچ دستور تازه‌ای.\n\n" \
        "## مراحل\n\n۱. `hades.py doctor` و `hades.py status`\n۲. تکراری‌ها و رابطه‌ها را پیدا کن\n" \
        "۳. `hades.py plan` بساز و نشانم بده\n۴. فقط بعد از تأیید من apply کن\n" % (
            obj["id"], json.dumps(obj.get("description", ""), ensure_ascii=False), obj["name"], obj.get("notes", ""))


def cmd_new(cfg, sch, args):
    rc = cmd_plan(cfg, args)
    args.plan = None
    import io
    # extract the plan id we just printed by scanning newest plan file
    newest = max(PLANS.glob("PLAN-*.json"), key=lambda p: p.stat().st_mtime)
    plan = load_json(newest)
    print("(plan %s written; applying because --new is plan+apply in one step)" % plan["plan_id"])
    args.plan = plan["plan_id"]
    return cmd_apply(cfg, sch, args)


def cmd_list(cfg, args):
    recs = list(iter_records(cfg))
    if args.kind:
        recs = [(p, r) for p, r in recs if r.get("kind") == args.kind]
    if args.zone:
        recs = [(p, r) for p, r in recs if rel(p).startswith(args.zone)]
    print("records: %d" % len(recs))
    print("  %-22s %-13s %-18s %-26s %s" % ("id", "kind", "status", "name", "path"))
    for p, r in sorted(recs, key=lambda x: str(x[1].get("id"))):
        print("  %-22s %-13s %-18s %-26s %s" % (r.get("id"), r.get("kind"), (r.get("status") or "")[:18],
                                                (r.get("name") or "")[:26], rel(p)))
    return 0


def cmd_show(cfg, args):
    for p, r in iter_records(cfg):
        if r.get("id") == args.id:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            print("# file: %s" % rel(p))
            return 0
    print("NOT FOUND: %s" % args.id)
    return 1


def cmd_link(cfg, args):
    hit = find_record(cfg, args.id)
    if not hit:
        raise SystemExit("ERROR: no record %s" % args.id)
    p, r = hit
    key = args.rel if args.rel in cfg["relations"] else ("depends_on" if args.rel == "depends-on" else None)
    if not key:
        raise SystemExit("ERROR: unknown relation '%s'" % args.rel)
    for other in cfg["kinds"]:
        if args.to.startswith(other["prefix"] + "-"):
            if not kind_cfg(cfg, other["kind"]):
                pass
    recs = {r2.get("id") for _, r2 in iter_records(cfg)}
    if args.to not in recs:
        print("WARNING: %s does not exist yet -- link recorded, doctor will flag it as dangling" % args.to)
    rel_obj = r.setdefault("relations", {})
    lst = rel_obj.setdefault(key, [])
    if args.to not in lst:
        lst.append(args.to)
    r["updated_at"] = now()
    if p.suffix == ".md":
        p.write_text(to_markdown(r), encoding="utf-8")
    else:
        dump_json(p, r)
    print("linked %s --%s--> %s" % (args.id, key, args.to))
    return 0


def cmd_context(cfg, args):
    limit = args.max_chars or cfg["context_max_chars"]
    pack, used = [], 0
    start = None
    for p, r in iter_records(cfg):
        if r.get("id") == args.project:
            start = p
            pack.append(("manifest", p))
            break
    if not start:
        raise SystemExit("ERROR: project %s not in registry" % args.project)
    for f in sorted(start.parent.rglob("*")):
        if f.is_file() and f.suffix in (".md", ".json") and f != start:
            pack.append((f.name, f))
    # linked records by relation
    recs = {r.get("id"): (p, r) for p, r in iter_records(cfg)}
    first = recs.get(args.project, (None, {}))[1]
    for group in (first.get("relations") or {}).values():
        for t in (group if isinstance(group, list) else [group]):
            if isinstance(t, str) and t in recs and not is_denied(rel(recs[t][0]), cfg):
                pack.append(("linked:" + t, recs[t][0]))
    out = []
    for label, f in pack:
        rp = rel(f)
        if is_denied(rp, cfg):
            out.append("## DENIED (machine plane): %s\n" % rp)
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        room = limit - used
        if room <= 0:
            out.append("## TRUNCATED: context budget %d chars reached\n" % limit)
            break
        clipped = text[:room]
        used += len(clipped)
        out.append("## %s | %s (%d chars%s)\n\n%s\n" % (label, rp, len(text),
                   ", clipped" if len(clipped) < len(text) else ", whole", clipped))
    GEN.mkdir(parents=True, exist_ok=True)
    dest = GEN / "context" / (args.project + ".md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out), encoding="utf-8")
    print("context pack: %d chars of budget %d -> %s" % (used, limit, rel(dest)))
    return 0


def cmd_search(cfg, args):
    terms = [t.lower() for t in args.query.split()]
    hits = 0
    files = []
    for z in zone_dirs(cfg):
        if args.machine or not is_denied(z + "/", cfg):
            d = ROOT / z
            if d.exists():
                files += [f for f in d.rglob("*") if f.is_file() and f.suffix in (".md", ".json", ".txt")]
    for f in sorted(files):
        if any(seg in f.parts for seg in ("generated", "backups", "_site")):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        low = text.lower()
        if all(t in low for t in terms):
            hits += 1
            print("HIT %s" % rel(f))
            if hits >= args.limit:
                break
    print("matches: %d files (query: %s)" % (hits, args.query))
    return 0 if hits else 1


def cmd_promote(cfg, args):
    target_zone = {"candidates": "14_CANDIDATES", "production": "11_CONTROL"}.get(args.to)
    if not target_zone:
        raise SystemExit("ERROR: --to must be candidates or production")
    if not args.approve:
        print("REFUSED: promote needs --approve")
        return 2
    src = None
    for p, r in iter_records(cfg):
        if r.get("id") == args.id:
            src = (p, r)
            break
    if not src:
        raise SystemExit("ERROR: no record %s" % args.id)
    p, r = src
    gates = cfg["gate_rules"]["promote_requires"]
    missing = []
    ev = r.get("evaluation", {})
    sf = r.get("safety_review", {})
    if "evaluation.passed" in gates and not ev.get("passed"):
        missing.append("evaluation.passed is not true")
    if "safety_review.passed" in gates and not sf.get("passed"):
        missing.append("safety_review.passed is not true")
    if "human_approved" in gates and not r.get("human_approved"):
        missing.append("human_approved is not true")
    if "evidence_paths_exist" in gates:
        paths = r.get("evidence_paths") or []
        if not paths:
            missing.append("evidence_paths is empty")
        for e in paths:
            if not (ROOT / e).exists():
                missing.append("evidence file missing on disk: %s" % e)
    if missing:
        print("BLOCKED: promotion refused")
        for m in missing:
            print("  %s" % m)
        return 2
    new_kind = "candidate" if args.to == "candidates" else ("skill" if r.get("kind") in ("skill", "candidate") and (p.parent / "SKILL.md").exists() else "agent")
    new_cfg = kind_cfg(cfg, new_kind)
    ident = new_id(new_cfg["prefix"], taken=existing_ids(cfg))
    dest = ROOT / target_zone / new_cfg["container"].split("|")[0] / ("%s-%s" % (ident, ascii_slug(r.get("name", ident))))
    dest.mkdir(parents=True, exist_ok=False)
    out = dict(r)
    out.update({"kind": new_kind, "id": ident,
                "status": cfg["status_sets"].get(new_kind, cfg["status_sets"]["default"])[0],
                "promoted_from": r.get("id"), "promoted_utc": now(), "created_at": today()})
    if new_kind == "candidate":
        out["source_experiment_id"] = r.get("id")
    if new_kind in ("agent", "skill"):
        out["status"] = "approved"
    dump_json(dest / new_cfg["manifest"], out)
    if (p.parent / "SKILL.md").exists():
        (dest / "SKILL.md").write_text((p.parent / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
    print("PROMOTED %s -> %s (%s) at %s" % (r.get("id"), ident, new_kind, rel(dest)))
    print("source left in place; the training data and checkpoints were NOT copied")
    return 0


def cmd_sync(cfg, args):
    harness = None
    for p, r in iter_records(cfg):
        if r.get("id") == args.harness or r.get("name") == args.harness:
            harness = r
            break
    if not harness:
        print("REFUSED: unknown harness '%s' -- an unverified adapter is a claim, not an integration" % args.harness)
        return 2
    mirror_rel = harness.get("skills_dir")
    if not mirror_rel:
        print("REFUSED: harness %s has no skills_dir declared" % args.harness)
        return 2
    mirror = ROOT / mirror_rel
    approved = [(p, r) for p, r in iter_records(cfg)
                if r.get("kind") == "skill" and r.get("status") == "approved"
                and args.harness in (r.get("approved_for_harness_ids") or [])]
    mirror.mkdir(parents=True, exist_ok=True)
    synced = set()
    for p, r in approved:
        src = p.parent
        name = r["id"]
        dst = mirror / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.tmp-*"))
        # the record is the law; the prose body may live in the pack the hosts read.
        # a mirror that copies the pointer but not what it points at ships an empty skill
        body = ROOT / str(r.get("entrypoint") or "")
        if r.get("entrypoint") and body.is_file() and body.parent != src:
            shutil.copy2(str(body), str(dst / Path(r["entrypoint"]).name))
        synced.add(name)
        print("synced %s (%s)" % (name, r.get("name")))
    pruned = 0
    for existing in sorted(mirror.iterdir()):
        if existing.is_dir() and existing.name not in synced:
            shutil.rmtree(existing)
            pruned += 1
            print("pruned stale mirror: %s" % existing.name)
    print("harness %s: %d approved skills mirrored, %d stale pruned -> %s" % (args.harness, len(synced), pruned, rel(mirror)))
    return 0


def export_audit(cfg, path, quiet=False):
    src = (ROOT / path) if not Path(path).is_absolute() else Path(path)
    if not src.exists():
        raise SystemExit("ERROR: no such path: %s" % path)
    rp = rel(src.resolve()) if str(src).startswith(str(ROOT)) else path
    if is_denied(rp, cfg):
        return None, ["REFUSED: %s is in the denied machine plane" % rp]
    allowed = {".md", ".json", ".txt", ".yaml", ".yml", ".py", ".ps1", ".bat", ".cfg", ".toml"}
    blocked, valid = [], []
    for p in sorted(src.rglob("*")):
        if p.is_symlink():
            blocked.append((rel(p), "symlink"))
            continue
        if not p.is_file():
            continue
        if p.name in (".gitkeep", ".gitignore", ".DS_Store", "Thumbs.db", "desktop.ini"):
            continue
        if p.suffix not in allowed:
            blocked.append((rel(p), "not a text type"))
            continue
        mb = cfg["gate_rules"]["publish_max_file_mb"]
        if p.stat().st_size > mb * 1024 * 1024:
            blocked.append((rel(p), "over the %s MB publish limit" % mb))
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            blocked.append((rel(p), "not valid UTF-8"))
            continue
        text = strip_pattern_defs(text, p)
        names = [n for n, pat in SECRET_PATTERNS.items() if pat.search(text)]
        if not names:
            for m in ENTROPY_TOKEN.finditer(text):
                tok = m.group()
                if len(set(tok)) / len(tok) > 0.72 and re.search(r"[A-Za-z]", tok) and re.search(r"\d", tok):
                    before = text[max(0, m.start() - 40):m.start()]
                    if re.search(r"(?i)(key|token|secret|password|auth|credential)\W{0,4}$", before.strip()):
                        names.append("high-entropy-token")
                        break
        if names:
            blocked.append((rel(p), "possible secret: " + ",".join(names)))
            continue
        valid.append(p)
    if len(valid) > cfg["gate_rules"]["publish_max_files"]:
        blocked.append(("*", "too many files"))
    return valid, blocked


def cmd_export(cfg, args):
    valid, blocked = export_audit(cfg, args.path)
    if valid is None:
        print(blocked[0])
        return 2
    for p, why in blocked:
        print("BLOCKED %s => %s" % (p, why))
    for p in valid:
        print("READY   %s" % rel(p))
    print("export audit: %d ready, %d blocked" % (len(valid), len(blocked)))
    if blocked:
        print("REFUSED: publish is blocked until every BLOCKED line is resolved")
        return 2
    return 0


def cmd_publish(cfg, args):
    if not args.approve:
        print("REFUSED: publish needs --approve")
        return 2
    if not re.match(r"^[\w.-]+/[\w.-]+$", args.repo):
        print("REFUSED: --repo must be OWNER/NAME")
        return 2
    valid, blocked = export_audit(cfg, args.path)
    if valid is None or blocked:
        for p, why in (blocked or []):
            print("BLOCKED %s => %s" % (p, why))
        print("REFUSED: nothing published")
        return 2
    if shutil.which("gh") is None:
        print("REFUSED: GitHub CLI (gh) is not installed -- this package does not install tools for you")
        return 2
    try:
        rc = subprocess.run(["gh", "repo", "view", args.repo, "--json", "visibility"],
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
        if rc.returncode == 0:
            print("REFUSED: %s already exists (%s); v3 publishes only brand-new repos" %
                  (args.repo, json.loads(rc.stdout).get("visibility")))
            return 2
    except Exception:
        pass
    work = Path(os.environ.get("TEMP", "/tmp")) / ("hades-publish-" + uuid.uuid4().hex[:8])
    work.mkdir(parents=True)
    base = (ROOT / args.path).resolve()
    for p in valid:
        dst = work / p.relative_to(base)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(p.read_bytes())
    (work / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    cmds = [["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.name=HADES OS", "-c", "user.email=hades@local", "commit", "-q", "-m", "HADES OS v3 export"],
            ["gh", "repo", "create", args.repo, "--private", "--source", ".", "--push"]]
    for c in cmds:
        r = subprocess.run(c, cwd=work, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print("FAILED at: %s\n%s%s" % (" ".join(c), r.stdout, r.stderr))
            print("nothing was left published; work dir: %s" % rel(work))
            return 2
    try:
        rv = subprocess.run(["gh", "repo", "view", args.repo, "--json", "visibility,url"],
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
        info = json.loads(rv.stdout) if rv.returncode == 0 else {}
    except Exception:
        info = {}
    vis = info.get("visibility", "UNKNOWN")
    print("published %s | %d files | verified visibility: %s" % (args.repo, len(valid), vis))
    if vis != cfg["gate_rules"]["publish_visibility_required"]:
        print("WARNING: expected PRIVATE, read back %s -- check GitHub settings now" % vis)
        return 1
    print("OK: %s" % info.get("url", args.repo))
    return 0


def cmd_qc(args):
    bad = scan_fa(fa_doc_files())
    if not bad:
        print("persian hygiene: clean across %d files" % len(fa_doc_files()))
        return 0
    for p, hits in bad:
        print("%s: %s" % (p, json.dumps(hits, ensure_ascii=False)))
    return 1


def cmd_graph(cfg, args):
    recs = list(iter_records(cfg))
    ids = {r.get("id") for _, r in recs}
    edges, nodes = [], []
    for p, r in recs:
        nodes.append((r.get("id"), (r.get("name") or "")[:40]))
        for k, v in (r.get("relations") or {}).items():
            for t in (v if isinstance(v, list) else [v]):
                if isinstance(t, str) and t in ids:
                    edges.append((r.get("id"), t, k))
    GEN.mkdir(parents=True, exist_ok=True)
    lines = ["graph LR"]
    for i, n in sorted(nodes):
        label = (n + " " + i).strip()
        lines.append('  %s["%s"]' % (i, label.replace('"', "'")))
    for a, b, k in edges:
        lines.append("  %s -->|%s| %s" % (a, k, b))
    out = GEN / "graph.mmd"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("graph: %d nodes, %d typed edges -> %s" % (len(nodes), len(edges), rel(out)))
    for a, b, k in edges:
        print("  %s --%s--> %s" % (a, k, b))
    return 0


# ---------------------------------------------------------------- main
def build_parser():
    ap = argparse.ArgumentParser(prog="hades.py", description="HADES OS v3 registry and gates")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    d = sub.add_parser("doctor")
    d.add_argument("--json", action="store_true")
    sub.add_parser("index")
    common = ["--kind", "--name", "--description", "--status", "--classification", "--tags",
              "--container", "--parent", "--depends-on", "--variant-of"]
    p = sub.add_parser("plan")
    for f in common:
        p.add_argument("--" + f.lstrip("-").replace("-", "_"))
    p.add_argument("--type"); p.add_argument("--code-repo", action="store_true")
    p.add_argument("--url"); p.add_argument("--category"); p.add_argument("--org")
    p.add_argument("--version"); p.add_argument("--metric"); p.add_argument("--model")
    p.add_argument("--engine"); p.add_argument("--path"); p.add_argument("--project")
    p.add_argument("--produced-by"); p.add_argument("--platform"); p.add_argument("--channel")
    p.add_argument("--capabilities"); p.add_argument("--agent"); p.add_argument("--transport")
    p.add_argument("--endpoint"); p.add_argument("--event"); p.add_argument("--action")
    p.add_argument("--invocation"); p.add_argument("--name-slug"); p.add_argument("--schedule")
    p.add_argument("--mode"); p.add_argument("--runtime"); p.add_argument("--template-kind")
    p.add_argument("--isolation"); p.add_argument("--experiment")
    a = sub.add_parser("apply")
    a.add_argument("--plan", required=True); a.add_argument("--approve", action="store_true")
    n = sub.add_parser("new")
    for f in common:
        n.add_argument("--" + f.lstrip("-").replace("-", "_"))
    for extra in ["--type", "--url", "--category", "--model", "--version", "--engine", "--platform",
                  "--project", "--capabilities", "--transport", "--endpoint", "--event", "--action",
                  "--schedule", "--runtime", "--isolation", "--experiment", "--path", "--produced-by",
                  "--channel", "--agent", "--metric", "--mode", "--template-kind", "--name-slug",
                  "--org", "--invocation"]:
        n.add_argument(extra)
    n.add_argument("--code-repo", action="store_true")
    n.add_argument("--approve", action="store_true")
    l = sub.add_parser("list")
    l.add_argument("--kind"); l.add_argument("--zone")
    s = sub.add_parser("show")
    s.add_argument("--id", required=True)
    lk = sub.add_parser("link")
    lk.add_argument("--id", required=True); lk.add_argument("--rel", required=True); lk.add_argument("--to", required=True)
    st = sub.add_parser("set")
    st.add_argument("--id", required=True); st.add_argument("--field", required=True)
    st.add_argument("--value", required=True); st.add_argument("--approve", action="store_true")
    cx = sub.add_parser("context")
    cx.add_argument("--project", required=True); cx.add_argument("--max-chars", type=int)
    se = sub.add_parser("search")
    se.add_argument("--query", required=True); se.add_argument("--machine", action="store_true")
    se.add_argument("--limit", type=int, default=40)
    pr = sub.add_parser("promote")
    pr.add_argument("--id", required=True); pr.add_argument("--to", required=True); pr.add_argument("--approve", action="store_true")
    sy = sub.add_parser("sync")
    sy.add_argument("--harness", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--path", required=True)
    pu = sub.add_parser("publish")
    pu.add_argument("--path", required=True); pu.add_argument("--repo", required=True); pu.add_argument("--approve", action="store_true")
    sub.add_parser("qc")
    g = sub.add_parser("graph")
    return ap


def main(argv=None):
    cfg = config()
    sch = schema()
    args = build_parser().parse_args(argv)
    if args.cmd == "status":
        return cmd_status(cfg)
    if args.cmd == "doctor":
        return cmd_doctor(cfg, sch, args.json)
    if args.cmd == "index":
        return cmd_index(cfg)
    if args.cmd == "plan":
        return cmd_plan(cfg, args)
    if args.cmd == "apply":
        return cmd_apply(cfg, sch, args)
    if args.cmd == "new":
        if not args.approve:
            print("REFUSED: new needs --approve (it plans and applies in one step)")
            return 2
        return cmd_new(cfg, sch, args)
    if args.cmd == "list":
        return cmd_list(cfg, args)
    if args.cmd == "show":
        return cmd_show(cfg, args)
    if args.cmd == "link":
        return cmd_link(cfg, args)
    if args.cmd == "set":
        return cmd_set(cfg, sch, args)
    if args.cmd == "context":
        return cmd_context(cfg, args)
    if args.cmd == "search":
        return cmd_search(cfg, args)
    if args.cmd == "promote":
        return cmd_promote(cfg, args)
    if args.cmd == "sync":
        return cmd_sync(cfg, args)
    if args.cmd == "export":
        return cmd_export(cfg, args)
    if args.cmd == "publish":
        return cmd_publish(cfg, args)
    if args.cmd == "qc":
        return cmd_qc(args)
    if args.cmd == "graph":
        return cmd_graph(cfg, args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
