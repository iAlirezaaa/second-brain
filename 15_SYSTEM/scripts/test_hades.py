"""HADES OS v3 test battery -- every gate must be proven to bite.

Run with:  py -3.10 15_SYSTEM/scripts/test_hades.py [--keep]

A rule that is only written down is a wish. Each negative case below plants the
exact defect into a throwaway copy of the vault and requires the tool to refuse
it; if the tool goes quiet, the test fails. Every scratch vault is built fresh
from the seeder, so no case depends on another case's leftovers.
"""
import sys
import os
import re
import json
import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SRC = Path(__file__).resolve().parents[2]
PY = [sys.executable]


class Vault:
    """A throwaway vault: real scripts, real config, zero real records."""

    def __init__(self, keep=False):
        self.root = Path(tempfile.mkdtemp(prefix="hades-v3-test-"))
        self.keep = keep
        shutil.copytree(SRC / "15_SYSTEM/scripts", self.root / "15_SYSTEM/scripts")
        shutil.copytree(SRC / "15_SYSTEM/config", self.root / "15_SYSTEM/config")
        shutil.copytree(SRC / "15_SYSTEM/schemas", self.root / "15_SYSTEM/schemas")
        if (SRC / "15_SYSTEM/templates").exists():
            # templates ship Persian prose too, and qc must cover them
            shutil.copytree(SRC / "15_SYSTEM/templates", self.root / "15_SYSTEM/templates")
        for name in ("README.md", "AGENTS.md"):
            if (SRC / name).exists():
                shutil.copy2(SRC / name, self.root / name)
        shutil.rmtree(self.root / "15_SYSTEM/scripts/__pycache__", ignore_errors=True)
        self.run("init_structure.py")
        self.cfg = json.loads((self.root / "15_SYSTEM/config/system.json").read_text(encoding="utf-8"))

    def run(self, script, *args):
        p = subprocess.run(PY + [str(self.root / "15_SYSTEM/scripts" / script)] + [str(a) for a in args],
                           cwd=str(self.root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def hades(self, *args):
        return self.run("hades.py", *args)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def json_of(self, rel):
        return json.loads(self.read(rel))

    def put_json(self, rel, obj):
        self.write(rel, json.dumps(obj, ensure_ascii=False, indent=2))

    def paths(self, pattern="**/project.json"):
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.glob(pattern))

    def close(self):
        if self.keep:
            print("   scratch kept at %s" % self.root)
            return
        shutil.rmtree(self.root, ignore_errors=True)


def seed_records(v):
    """A minimal honest graph: one Persian-named project, an org, a model."""
    v.hades("new", "--kind", "project", "--name", "پروژه آزمایش انیمیشن",
            "--description", "fixture", "--type", "animation", "--approve")
    v.hades("new", "--kind", "organization", "--name", "Example Provider",
            "--description", "fixture", "--approve")
    v.hades("new", "--kind", "model", "--name", "Example Video Family",
            "--description", "fixture", "--category", "video_generation", "--approve")


def project_path(v):
    ps = v.paths()
    return ps[0] if ps else None


def is_ascii(s):
    return all(ord(c) < 128 for c in s)


# ------------------------------------------------------------------ cases
RESULTS = []


def check(label, cond, detail=""):
    RESULTS.append((label, bool(cond), detail))


# ---- positive path
def t_positive():
    v = Vault()
    try:
        c, o = v.hades("doctor")
        check("seeded vault is clean (errors: 0)", c == 0 and "errors: 0" in o, o.splitlines()[-1][:120])

        c, o = v.hades("plan", "--kind", "project", "--name", "پروژه تست فارسی",
                      "--description", "plan only", "--type", "animation")
        m = re.search(r"PLAN-[0-9A-F]+", o)
        check("plan a Persian-named project", c == 0 and bool(m), o.strip().splitlines()[0][:120] if o.strip() else "")
        plan_id = m.group(0) if m else "none"

        before = len(v.paths())
        c, o = v.hades("apply", "--plan", plan_id, "--approve")
        pp = project_path(v)
        check("apply creates exactly one folder", c == 0 and len(v.paths()) == before + 1,
              "folders %d -> %d" % (before, len(v.paths())))
        check("Persian name never becomes the path (ASCII paths only)", pp and is_ascii(pp), str(pp))
        rec = v.json_of(pp) if pp else {}
        check("record keeps the Persian name inside the manifest", rec.get("name") == "پروژه تست فارسی", str(rec.get("name")))

        c, o = v.hades("apply", "--plan", plan_id, "--approve")
        check("re-applying a plan is refused, not duplicated",
              c == 2 and "already applied" in o and len(v.paths()) == before + 1,
              "exit=%s folders=%d" % (c, len(v.paths())))

        c, o = v.hades("apply", "--plan", plan_id)
        check("apply without --approve is refused", c == 2 and "REFUSED" in o, o.strip()[:120])

        c, o = v.hades("new", "--kind", "organization", "--name", "No Approve Org", "--description", "x")
        check("new without --approve is refused", c == 2 and "REFUSED" in o, o.strip()[:120])

        seed_records(v)
        c, o = v.hades("index")
        n = re.search(r"indexed (\d+) records \((\d+) unreadable\)", o)
        check("index counts records with a real number", bool(n) and int(n.group(1)) >= 3 and n.group(2) == "0", o.strip()[:120])

        c, o = v.hades("search", "--query", "انیمیشن")
        k = re.search(r"matches: (\d+)", o)
        check("Persian search hits the Persian note", c == 0 and bool(k) and int(k.group(1)) >= 1, o.strip().splitlines()[-1][:120])

        c, o = v.hades("qc")
        check("persian hygiene gate is clean on shipped docs", c == 0 and "clean" in o, o.strip()[:140])

        tpl = sorted((v.root / "15_SYSTEM/templates").glob("*.md"))
        if tpl:
            original = tpl[0].read_text(encoding="utf-8")
            tpl[0].write_text(original + "\n" + chr(0x9762) + "\n", encoding="utf-8")
            c, o = v.hades("qc")
            check("the hygiene gate covers the templates folder, not just zones",
                  c == 1 and "15_SYSTEM/templates" in o, o.strip().replace("\n", " | ")[:150])
            tpl[0].write_text(original, encoding="utf-8")
        else:
            check("templates exist to be covered by qc", False, "no 15_SYSTEM/templates/*.md in source vault")

        c, o = v.hades("doctor")
        check("positive path still leaves doctor green", c == 0 and "errors: 0" in o, o.strip()[:120])

        pid = rec.get("id")
        c, o = v.hades("context", "--project", pid)
        chars = len(o)
        check("context pack stays under the config budget",
              c == 0 and chars <= v.cfg["context_max_chars"] + 400,
              "%d chars (budget %d)" % (chars, v.cfg["context_max_chars"]))

        c, o = v.hades("graph")
        check("graph renders without crashing", c == 0, o.strip()[:100])

        c, o = v.run("wiki.py", "build")
        b = v.json_of("02_WIKI/_site/build.json")
        human_only = all(int(s[:2]) <= 10 for s in b["sources"] if re.match(r"^\d\d_", s))
        check("wiki builds and exports only human-plane files",
              c == 0 and b["pages"] >= 1 and human_only and b["machine_plane_zones_included"] == 0,
              "pages=%d" % b["pages"])
        site = v.read("02_WIKI/_site/index.html")
        check("wiki page is rtl and noindex", 'dir="rtl"' in site and "noindex" in site, "")
    finally:
        v.close()


# ---- doctor negatives
def t_doctor(label, mutate, expect, level="error"):
    v = Vault()
    try:
        seed_records(v)
        c0, o0 = v.hades("doctor")
        if c0 != 0:
            check(label + " (baseline was green)", False, "baseline exit=%s" % c0)
            return
        mutate(v)
        c, o = v.hades("doctor")
        hit = [l for l in o.splitlines() if expect.lower() in l.lower()]
        # warnings must be visible but must not break the vault; errors must exit 1
        want_exit = 1 if level == "error" else 0
        check("doctor catches (%s): %s" % (level, label),
              c == want_exit and bool(hit),
              (hit[0].strip()[:150] if hit else "no line matched '%s' (exit=%s)" % (expect, c)))
    finally:
        v.close()


def m_duplicate_id(v):
    src = v.root / v.paths("**/model.json")[0]
    shutil.copytree(str(src.parent), str(v.root / "04_INTELLIGENCE/models/MOD-DUPLICATE-x"))


def m_dangling(v):
    pp = project_path(v)
    rec = v.json_of(pp)
    rec["depends_on"] = ["PRJ-DEADBEEF"]
    v.put_json(pp, rec)


def m_typo_id(v):
    """A reference with a wrong-shaped id can never resolve; it must not pass."""
    pp = project_path(v)
    rec = v.json_of(pp)
    rec["depends_on"] = ["PRJ-DEADBEE"]
    v.put_json(pp, rec)


def m_status_folder(v):
    pp = project_path(v)
    rec = v.json_of(pp)
    rec["status"] = "completed"
    v.put_json(pp, rec)


def m_secret_token(v):
    v.write("01_INBOX/leak.md", "# note\nOPENAI_KEY=sk-" + "abcdefghijkl" * 3 + "\n")


def m_secret_labelled(v):
    v.write("01_INBOX/creds.md", "api_key = \"Zx9" + "Qw3rT7yU0iP2aS4dF6gH8j" + "\"\n")


def m_secret_entropy(v):
    v.write("01_INBOX/ent.md", "AUTH_TOKEN: aKs9" + "ZmQ4xT7vB2nL8pR3wY6cE1uI0o" + "\n")


def m_runtime_manifest(v):
    src = v.read(v.paths("**/model.json")[0])
    v.write("12_RUNTIME/model.json", src)


def m_nonascii_path(v):
    d = (v.root / Path(project_path(v))).parent
    d.rename(d.parent / "PRJ-تست-فارسی")


def m_gitignore_drift(v):
    gi = v.read(".gitignore").replace("13_LAB/", "13_LAB_DISABLED/")
    v.write(".gitignore", gi)


def m_nested_git(v):
    (v.root / "03_PROJECTS/nested/.git").mkdir(parents=True, exist_ok=True)
    (v.root / "03_PROJECTS/nested/.git/HEAD").write_text("ref: refs/heads/main", encoding="utf-8")


def m_missing_readme(v):
    (v.root / "08_LEARNING/README.md").unlink()


def m_drop_machine_zone(v):
    """A fresh clone of the published repo has no 12_RUNTIME: it is gitignored
    machine state. doctor must account for that, not call it a defect."""
    shutil.rmtree(str(v.root / "12_RUNTIME"))


def m_drop_human_zone(v):
    shutil.rmtree(str(v.root / "08_LEARNING"))


def m_drop_quarantine_zone(v):
    """14_CANDIDATES is also gitignore_required, but its loop shelf is tracked by
    exception -- so its absence IS a defect. The two flags must not blur."""
    shutil.rmtree(str(v.root / "14_CANDIDATES"))


def m_git_at_vault_root(v):
    """The vault's own repo is the vault. Only a repo *inside* a zone is stranded."""
    (v.root / ".git").mkdir(parents=True, exist_ok=True)
    (v.root / ".git/HEAD").write_text("ref: refs/heads/main", encoding="utf-8")


def m_stale_date(v):
    pp = project_path(v)
    rec = v.json_of(pp)
    rec["last_verified"] = "2024-01-01"
    v.put_json(pp, rec)


def m_bad_date(v):
    pp = project_path(v)
    rec = v.json_of(pp)
    rec["last_verified"] = "not-a-date"
    v.put_json(pp, rec)


def m_cjk(v):
    v.write("00_START_HERE/HYGIENE_PROBE.md", "# یادداشت " + chr(0x9762) + " تست\n")


def m_glued(v):
    v.write("00_START_HERE/HYGIENE_PROBE.md", "# فقطadvertise و workflowها\n")


def m_unknown_id(v):
    pp = project_path(v)
    rec = v.json_of(pp)
    rec["id"] = "prj-lowercase"
    v.put_json(pp, rec)


def m_missing_field(v):
    pp = project_path(v)
    rec = v.json_of(pp)
    del rec["classification"]
    v.put_json(pp, rec)


def m_missing_evidence(v):
    v.hades("new", "--kind", "experiment", "--name", "Evidenceless", "--description", "goal",
            "--isolation", "none", "--approve")
    ep = v.paths("**/experiment.json")
    if not ep:
        return
    rec = v.json_of(ep[0])
    rec["evidence_paths"] = ["13_LAB/no_such_file.md"]
    v.put_json(ep[0], rec)


def m_bad_status(v):
    pp = project_path(v)
    rec = v.json_of(pp)
    rec["status"] = "shipped"
    v.put_json(pp, rec)


def m_zone_mismatch(v):
    src = v.root / project_path(v)
    dst = v.root / "05_WORKS/stray/project.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(src), str(dst))


# ---- gate negatives (command refusals)
def t_refusals():
    v = Vault()
    try:
        seed_records(v)

        c, o = v.hades("promote", "--id", "EXP-00000000", "--to", "candidates")
        check("promote without --approve is refused", c == 2 and "REFUSED" in o, o.strip()[:120])

        c, o = v.hades("new", "--kind", "experiment", "--name", "Bare Experiment",
                       "--description", "raise the score over the baseline",
                       "--isolation", "none", "--approve")
        exp_paths = v.paths("**/experiment.json")
        check("an experiment can be created in 13_LAB", bool(exp_paths), (o or "").strip().replace("\n", " | ")[:170])
        if not exp_paths:
            return
        exp = v.json_of(exp_paths[0])
        c, o = v.hades("promote", "--id", exp["id"], "--to", "candidates", "--approve")
        blocked = c == 2 and "BLOCKED" in o
        named = all(k in o for k in ("evaluation.passed", "safety_review.passed", "human_approved", "evidence_paths"))
        check("promote of an ungated experiment is blocked", blocked and named, o.strip().replace("\n", " | ")[:170])

        exp = v.json_of(exp_paths[0])
        exp.update({"evaluation": {"passed": True}, "safety_review": {"passed": True},
                    "human_approved": True, "evidence_paths": ["13_LAB/missing-evidence.md"]})
        v.put_json(exp_paths[0], exp)
        c, o = v.hades("promote", "--id", exp["id"], "--to", "candidates", "--approve")
        check("promote is blocked when the evidence file is not on disk",
              c == 2 and "evidence file missing on disk" in o, o.strip().replace("\n", " | ")[:170])

        v.write("13_LAB/missing-evidence.md", "# proof\nnumbers, not adjectives\n")
        c, o = v.hades("promote", "--id", exp["id"], "--to", "candidates", "--approve")
        cand = v.paths("14_CANDIDATES/**/*.json")
        check("promotion passes when all four gates hold",
              c == 0 and "PROMOTED" in o and len(cand) == 1, o.strip().replace("\n", " | ")[:170])
        if cand:
            c2, o2 = v.hades("doctor")
            check("a promoted candidate leaves doctor green", c2 == 0 and "errors: 0" in o2, o2.strip()[:140])
            src_still = (v.root / exp_paths[0]).exists()
            check("promotion copies out, it does not move the lab original", src_still, "")

        c, o = v.hades("sync", "--harness", "HAR-DEADBEEF")
        check("sync to an unknown harness is refused", c == 2 and "unknown harness" in o, o.strip()[:140])

        c, o = v.hades("new", "--kind", "harness", "--name", "Test Harness", "--description", "x",
                       "--runtime", "other", "--capabilities", "skills", "--approve")
        hp = v.paths("**/*harness*.json")
        check("a file-layout harness is visible to the registry",
              bool(hp) and "HAR-" in o, (o.strip() + " | paths=" + str(hp))[:160])
        if not hp:
            return
        har = v.json_of(hp[0])
        c, o = v.hades("list", "--kind", "harness")
        check("list finds the harness by id and name", har["id"] in o and "Test Harness" in o, o.strip()[:140])

        c, o = v.hades("sync", "--harness", har["id"])
        check("sync without a declared skills_dir is refused",
              c == 2 and "no skills_dir declared" in o, o.strip().replace("\n", " | ")[:160])

        c, o = v.hades("new", "--kind", "skill", "--name", "Demo Skill",
                       "--description", "does one useful thing", "--status", "approved", "--approve")
        sp = v.paths("**/skill.json")
        check("an approved skill can be created for sync", bool(sp), o.strip().replace("\n", " | ")[:160])

        har["skills_dir"] = "12_RUNTIME/harness_memory/test-harness-skills"
        v.put_json(hp[0], har)
        if sp:
            sk = v.json_of(sp[0])
            sk["approved_for_harness_ids"] = [har["id"]]
            v.put_json(sp[0], sk)
            (v.root / Path(sp[0]).parent / "SKILL.md").write_text("# demo skill\n", encoding="utf-8")
            c, o = v.hades("sync", "--harness", har["id"])
            mirror = v.root / har["skills_dir"]
            n_dirs = len([d for d in mirror.iterdir() if d.is_dir()]) if mirror.exists() else 0
            check("sync mirrors exactly the approved skills",
                  c == 0 and "1 approved skills mirrored" in o and n_dirs == 1,
                  o.strip().replace("\n", " | ")[:170] + " | mirrored dirs=%d" % n_dirs)
            c, o = v.hades("doctor")
            check("a synced mirror does not create duplicate records",
                  c == 0 and "errors: 0" in o, o.strip().replace("\n", " | ")[:170])
            sk2 = v.json_of(sp[0])
            sk2["status"] = "draft"
            v.put_json(sp[0], sk2)
            c, o = v.hades("sync", "--harness", har["id"])
            check("sync prunes a skill that fell back to draft",
                  "pruned stale mirror" in o and "0 approved skills mirrored" in o,
                  o.strip().replace("\n", " | ")[:170])

        c, o = v.hades("publish", "--path", "04_INTELLIGENCE", "--repo", "someone/thing")
        check("publish without --approve is refused", c == 2 and "REFUSED" in o, o.strip()[:120])

        c, o = v.hades("export", "--path", "12_RUNTIME")
        check("export of the machine plane is refused",
              c == 2 and "denied machine plane" in o, o.strip()[:150])

        c, o = v.hades("export", "--path", "04_INTELLIGENCE")
        blocked = [l for l in o.splitlines() if l.startswith("BLOCKED")]
        check("export audits every file and prints counts",
              "export audit:" in o and "ready" in o and len(blocked) == 0, o.strip().splitlines()[-1][:140])

        v.write("11_CONTROL/leaky/mcp.json",
                json.dumps({"id": "MCP-ABC12345", "kind": "mcp", "name": "Leaky", "status": "draft",
                            "classification": "internal", "created_at": "2026-10-24",
                            "endpoint": "https://x", "transport": "http",
                            "headers": {"Authorization": "Bearer " + "abc123" * 5}}, ensure_ascii=False, indent=2))
        c, o = v.hades("export", "--path", "11_CONTROL/leaky")
        check("export blocks a manifest carrying a bearer token",
              c == 2 and "possible secret" in o, o.strip().replace("\n", " | ")[:160])

        c, o = v.hades("new", "--kind", "deliverable", "--name", "Final Cut",
                       "--description", "no provenance", "--status", "approved", "--approve")
        check("a deliverable without provenance is refused at creation",
              c != 0 and ("project_id" in o or "required" in o.lower()), o.strip().replace("\n", " | ")[:170])

        c, o = v.hades("plan", "--kind", "not-a-kind", "--name", "X", "--description", "y")
        check("an unknown kind cannot be planned", c != 0, o.strip()[:120])

        c, o = v.run("wiki.py", "build", "--include", "11_CONTROL")
        check("wiki refuses to export the machine plane", c == 2 and "REFUSED" in o, o.strip()[:140])
    finally:
        v.close()


PROBE_MD = "\n".join([
    "# سرصفحه پروب",
    "",
    "**پررنگ** و *کج* و `code` و [پیوند](../README.md).",
    "",
    "%s. یک" % chr(0x06F1),
    "%s. دو" % chr(0x06F2),
    "",
    "```",
    "py -3.10 one",
    "py -3.10 two",
    "```",
    "",
    "> نقل قول",
    "",
    "| ستون | چیز |",
    "| --- | --- |",
    "| الف | ب |",
    "| `a|b` | ج |",
    ""])


def t_wiki():
    """The renderer must render, and a link to an anchor that does not exist must stop the build."""
    v = Vault()
    try:
        v.write("08_LEARNING/wiki-render-probe.md", PROBE_MD)
        c, o = v.run("wiki.py", "build")
        site = v.read("02_WIKI/_site/index.html")
        start = site.index('<section id="08-learning-wiki-render-probe"')
        end = site.index("</section>", start)
        probe = site[start:end]
        check("wiki builds a planted probe page", c == 0 and len(probe) > 80, o.strip()[:120])
        for label, needle in [
            ("bold renders as strong", "<strong>"),
            ("italic renders as em", "<em>"),
            ("inline code renders as code", "<code>code</code>"),
            ("markdown link points at the page anchor", '<a href="#readme">'),
            ("ordered list keeps its Persian marker", 'ol class="ord"'),
            ("block quote renders", "<blockquote>"),
            ("table renders", "<table>"),
            ("a pipe inside a code span stays inside one cell", "<code>a|b</code>"),
            ("code block keeps its line breaks", "py -3.10 one" + chr(10) + "py -3.10 two"),
        ]:
            check("wiki renderer: %s" % label, needle in probe, "missing from section: " + needle)
        raw_left = [m for m in ("**", chr(96) + "code" + chr(96)) if m in probe]
        check("no raw markdown survives the build", not raw_left, str(raw_left))
        check("no dead anchor in a green build",
              'href="#' in site and not v.json_of("02_WIKI/_site/build.json").get("dead_links"), "")

        v.write("08_LEARNING/wiki-render-probe.md", PROBE_MD + "\n[[صفحه\u200cای که وجود ندارد]]\n")
        c, o = v.run("wiki.py", "build")
        check("a link to an anchor this build does not contain is refused",
              c == 2 and "REFUSED" in o and "anchor" in o, o.strip().replace("\n", " | ")[:160])
        check("the refusal happens before the site is rewritten",
              "<strong>" in v.read("02_WIKI/_site/index.html"), "site was overwritten by a refused build")
    finally:
        v.close()


def t_archive():
    """A status the docs promise must have a container the tool can place it in."""
    v = Vault()
    try:
        c, o = v.hades("new", "--kind", "project", "--name", "Retired Show", "--description", "x",
                       "--type", "animation", "--status", "archived", "--approve")
        placed = "03_PROJECTS/archived/" in o.replace("\\", "/")
        c2, o2 = v.hades("doctor")
        check("an archived project has a container and keeps doctor green",
              c == 0 and placed and c2 == 0 and "errors: 0" in o2,
              "placed=%s | %s" % (placed, o2.strip().replace("\n", " ")[:120]))
    finally:
        v.close()


def t_status_accounts_every_zone():
    """status must reconcile to 16: on disk + excused-by-boundary + unexcused.
    A count that silently drops zones is how '16/16' became un-reproducible."""
    v = Vault()
    try:
        shutil.rmtree(str(v.root / "12_RUNTIME"))
        c, o = v.hades("status")
        lines = o.splitlines()
        disk = next((l for l in lines if l.startswith("zones on disk:")), "")
        boundary = next((l for l in lines if l.startswith("absent at the documented")), "")
        on_disk, total = (-1, -1)
        nums = re.search(r"(\d+)/(\d+)", disk)
        if nums:
            on_disk, total = int(nums.group(1)), int(nums.group(2))
        excused = len([z for z in ("12_RUNTIME", "13_LAB") if z in boundary])
        check("status reconciles every declared zone (disk + boundary = declared)",
              c == 0 and on_disk + excused == total == len(v.cfg["zones"]) and "12_RUNTIME" in boundary,
              "disk=%s excused=%s printed=%s cfg_zones=%s | %s / %s"
              % (on_disk, excused, total, len(v.cfg["zones"]), disk, boundary))
        check("an excused zone is not also reported as missing",
              "NOT excused" not in o, o.strip().replace("\n", " | ")[:160])
    finally:
        v.close()


def t_markdown_and_amendments():
    """Issues #13 and #12: what `apply` writes, the registry keeps seeing; a wrong
    record is corrected through plan -> review -> apply --approve; `supersedes`
    really retires the replaced record instead of being an unused word."""
    v = Vault()
    try:
        c, o = v.hades("new", "--kind", "wiki_note", "--name", "Gates Law",
                       "--description", "definition body", "--approve")
        m = re.search(r"APPLIED (WIK-[0-9A-F]+)", o)
        wid = m.group(1) if m else None
        wiki_files = v.paths("02_WIKI/**/*.md")
        on_zone = [p for p in wiki_files if wid in p]
        check("a markdown-layout record is written as <ID>-<slug>.md",
              c == 0 and bool(wid) and len(on_zone) == 1, o.strip().replace("\n", " | ")[:170])
        if not (c == 0 and wid):
            return
        c, o = v.hades("show", "--id", wid)
        check("show finds the file apply just wrote (issue #13)", c == 0 and wid in o, o.strip()[:120])
        c, o = v.hades("list", "--kind", "wiki_note")
        check("list --kind counts the markdown record", c == 0 and "records: 1" in o and wid in o,
              o.strip()[:120])
        c, o = v.hades("doctor")
        check("doctor enumerates the markdown record and stays green",
              c == 0 and "errors: 0 | warnings: 0" in o and "registry records: 1" in o,
              o.strip()[:150])
        c, o = v.hades("index")
        check("index counts one record for the wiki note", c == 0 and bool(re.search(r"indexed 1 records", o)),
              o.strip()[:120])

        c, o = v.hades("new", "--kind", "wiki_note", "--name", "Gates Law Two",
                       "--description", "second", "--approve")
        m = re.search(r"APPLIED (WIK-[0-9A-F]+)", o)
        wid2 = m.group(1) if m else None
        if not (c == 0 and wid2):
            check("a second markdown record applies", False, o.strip().replace("\n", " | ")[:140])
            return
        c, o = v.hades("link", "--id", wid2, "--rel", "supersedes", "--to", wid)
        link_ok = c == 0 and "linked" in o
        rec_after = v.read(md_file(v, wid2))
        check("link on a markdown record keeps kind and the edge (issue #13)",
              link_ok and "supersedes" in rec_after and "wiki_note" in rec_after,
              (o.strip() + " | file has kind=%s edge=%s" % ("wiki_note" in rec_after, "supersedes" in rec_after))[:170])
        v.hades("index")
        cat = v.json_of("15_SYSTEM/generated/catalog.json")
        rows = {r["id"]: r for r in cat.get("records", [])}
        retired = {r["id"]: r for r in cat.get("superseded", [])}
        check("a superseded record leaves the active index (issue #12)",
              wid in retired and retired.get(wid, {}).get("superseded_by") == wid2
              and wid2 in rows and cat.get("superseded_count") == 1,
              json.dumps({"records": sorted(rows), "superseded": cat.get("superseded")},
                         ensure_ascii=False)[:170])
        c, o = v.hades("doctor")
        check("doctor names the retirement and counts only active records",
              c == 0 and "errors: 0" in o and "superseded (retired from the active index)" in o
              and wid in o and wid2 in o and bool(re.search(r"registry records: 1\b", o)),
              o.strip().replace("\n", " | ")[:150])
        c, o = v.hades("status")
        check("status counts one record for one thing",
              c == 0 and "registry records: 2" in o
              and "superseded (retired from the active index): 1 of 2" in o,
              o.strip()[:150])

        wiki2 = md_file(v, wid2)
        before = v.read(wiki2)
        c, o = v.hades("set", "--id", wid2, "--field", "name", "--value", "Gates Law Renamed")
        m = re.search(r"PLAN-[0-9A-F]{12}", o)
        check("set writes an amend plan and prints the diff",
              c == 0 and bool(m) and "--field name" in o and "apply --plan" in o,
              o.strip().replace("\n", " | ")[:160])
        if not (c == 0 and m):
            return
        plan_id = m.group(0)
        c, o = v.hades("apply", "--plan", plan_id)
        check("an amendment is refused without --approve", c == 2 and "REFUSED" in o, o.strip()[:120])
        c, o = v.hades("apply", "--plan", plan_id, "--approve")
        after = v.read(wiki2)
        check("apply --approve writes the amendment to disk",
              c == 0 and "AMENDED" in o and "Gates Law Renamed" in after and before != after,
              o.strip().replace("\n", " | ")[:170])
        check("the amendment stamps updated_at for the audit trail", "updated_at:" in after, "")
        c, o = v.hades("doctor")
        check("doctor stays green after the amendment", c == 0 and "errors: 0" in o,
              o.strip()[:140])

        snapshot = v.read(wiki2)
        c, o = v.hades("set", "--id", wid2, "--field", "classification", "--value", "topless")
        check("an amendment breaking the contract is refused",
              c == 2 and "REFUSED" in o and "classification" in o, o.strip().replace("\n", " | ")[:160])
        c, o = v.hades("set", "--id", wid2, "--field", "created_at", "--value", "2000-01-01")
        check("identity fields cannot be amended", c == 2 and "REFUSED" in o, o.strip()[:120])
        c, o = v.hades("set", "--id", wid2, "--field", "nams", "--value", "typo")
        check("an unknown field is refused (a typo is a second truth)", c == 2 and "REFUSED" in o,
              o.strip()[:120])
        check("every refused amendment changed nothing on disk", v.read(wiki2) == snapshot, "")
    finally:
        v.close()


def md_file(v, wid):
    """The markdown record's file, found by its id -- never by a glob order that the
    random hex inside the ids decides."""
    hits = [p for p in v.paths("02_WIKI/**/*.md") if wid in p]
    return hits[0] if hits else None


# ---- harness bridge (phase 22)
def t_harness_bridge():
    v = Vault()
    try:
        # the door's own helpers (common/memory/candidate_check) live in scripts/;
        # a scratch vault only ships 15_SYSTEM, so bring the package along
        shutil.copytree(SRC / "scripts", v.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        # the run ledger: an actor the registry never heard of cannot run
        c, o = v.run("runs.py", "start", "--agent", "AGT-ghost", "--goal", "nope")
        check("harness: a ghost actor cannot start a run",
              c == 2 and "no registry record AGT-ghost" in o, o.strip()[:140])
        c, o = v.hades("new", "--kind", "agent", "--name", "Bridge Runner",
                       "--description", "fixture", "--approve")
        agt = [ln.split()[1] for ln in o.splitlines() if ln.startswith("APPLIED ")][0]
        c, o = v.run("runs.py", "start", "--agent", agt, "--goal", "prove the bridge")
        run_id = [ln.split()[1] for ln in o.splitlines() if ln.startswith("RUN ")][0] if c == 0 else ""
        check("harness: a registered actor starts a run", c == 0 and run_id.startswith("RUN-"),
              o.strip()[:140])
        c, o = v.run("runs.py", "step", "--run", run_id, "--text", "opened the door")
        check("harness: a run takes a step", c == 0 and "STEP" in o, o.strip()[:140])
        c, o = v.run("runs.py", "finish", "--run", run_id, "--status", "completed",
                     "--summary", "door proven")
        check("harness: a run finishes once", c == 0 and "completed" in o, o.strip()[:140])
        c, o = v.run("runs.py", "step", "--run", run_id, "--text", "too late")
        check("harness: a finished feed refuses steps", c == 2 and "REFUSED" in o, o.strip()[:140])
        c, o = v.run("runs.py", "list")
        check("harness: list shows the closed run", c == 0 and run_id in o, o.strip()[:140])
        c, o = v.run("runs.py", "promote", "--run", run_id, "--dimension", "invariant")
        check("harness: a finished run promotes into a registered row",
              c == 0 and "PROMOTED cand-" in o, o.strip()[:160])
        promoted_rows = list((v.root / "14_CANDIDATES/loop").glob("cand-*-run-*.md"))
        check("harness: the promoted row is on the shelf with the feed embedded",
              len(promoted_rows) == 1 and "opened the door" in promoted_rows[0].read_text(encoding="utf-8"),
              str(promoted_rows))
        c, o = v.run("runs.py", "promote", "--run", run_id)
        check("harness: promoting twice is refused", c == 2 and "promoting twice" in o, o.strip()[:140])
        wf_path = v.root / "15_SYSTEM" / "workflows" / "battery-demo.json"
        wf_path.parent.mkdir(parents=True, exist_ok=True)
        wf_path.write_text(json.dumps({"name": "battery demo", "steps": [
            {"name": "read", "type": "tool_call", "tool": "core.fs_read",
             "args": {"path": "15_SYSTEM/config/system.json"}},
            {"name": "stop", "type": "done", "note": "engine walked it"}]}), encoding="utf-8")
        c, o = v.run("orchestrator.py", "workflow", "validate", "--file", str(wf_path))
        check("backend: the workflow validator is the gate",
              c == 0 and "VALID" in o, o.strip()[:140])
        c, o = v.run("orchestrator.py", "workflow", "run", "--file", str(wf_path), "--agent", agt)
        check("backend: the engine walks the workflow end to end",
              c == 0 and "WORKFLOW battery demo -> COMPLETED" in o, o.strip()[:160])
        feeds = list((v.root / "12_RUNTIME" / "agent_runs").glob("*/steps.jsonl"))
        check("backend: the run transcript holds the engine feed",
              any("core.fs_read" in f.read_text(encoding="utf-8") for f in feeds),
              str(feeds)[:140])
        c, o = v.run("orchestrator.py", "tool", "call", "--tool", "core.ltm_store",
                     "--args", '{"text": "sneaky"}', "--agent", agt)
        check("backend: a write tool refuses an unapproved context",
              c == 2 and "not approved" in o, o.strip()[:140])

        # the MCP door over the wire, in a subprocess, exactly like a harness talks to it
        server = v.root / "15_SYSTEM/scripts/mcp_server.py"
        proc = subprocess.Popen(PY + [str(server), "--root", str(v.root)], cwd=str(v.root),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        def send(obj):
            proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
            proc.stdin.flush()

        def recv():
            return json.loads(proc.stdout.readline().decode("utf-8", errors="replace"))

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                         "clientInfo": {"name": "battery", "version": "0"}}})
        r = recv()
        check("harness: initialize names the brain",
              r["result"]["serverInfo"]["name"] == "hades-second-brain", str(r)[:140])
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in recv()["result"]["tools"]]
        check("harness: twelve tools exposed",
              set(names) == {"capabilities", "lesson_propose", "lesson_recall", "source_search", "vault_search", "memory_recall", "registry_list", "registry_show",
                             "doctor_status", "runs_list", "runs_show", "candidate_propose"},
              str(names)[:140])
        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "registry_list", "arguments": {}}})
        text = recv()["result"]["content"][0]["text"]
        check("harness: registry_list sees the seeded agent", agt in text, text[:140])
        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": "runs_list", "arguments": {}}})
        text = recv()["result"]["content"][0]["text"]
        check("harness: runs_list shows the promoted run through the door",
              run_id in text and '"promoted"' in text, text[:200])
        send({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
              "params": {"name": "doctor_status", "arguments": {}}})
        text = recv()["result"]["content"][0]["text"]
        runs_count = len([d for d in (v.root / "12_RUNTIME" / "agent_runs").iterdir()
                          if d.is_dir()])
        check("harness: doctor_status counts the run and the record",
              ('"runs": %d' % runs_count) in text and '"records": 1' in text, text[:200])
        send({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
              "params": {"name": "candidate_propose", "arguments": {
                  "dimension": "invariant", "cue": "the battery spoke to the brain",
                  "lesson": "the door answers on the wire", "confidence": 0.8}}})
        text = recv()["result"]["content"][0]["text"]
        check("harness: candidate_propose files a registered row",
              "PROPOSED cand-" in text, text[:140])
        rows = list((v.root / "14_CANDIDATES/loop").glob("cand-*-mcp-*.md"))
        ledger = ""
        ledger_path = v.root / "14_CANDIDATES/loop/ledger.jsonl"
        if ledger_path.is_file():
            ledger = ledger_path.read_text(encoding="utf-8")
        check("harness: the proposal landed on the shelf and in the ledger",
              len(rows) == 1 and "proposed" in ledger, "%d row(s); ledger %d char(s)"
              % (len(rows), len(ledger)))
        proc.stdin.close()
        check("harness: the door exits cleanly on EOF", proc.wait(timeout=30) == 0)
        for stream in (proc.stdout, proc.stderr):
            try:
                stream.close()
            except OSError:
                pass
    finally:
        v.close()


def guard(fn, *a):
    """A crash in one case must not hide the verdict of the other 40."""
    try:
        fn(*a)
    except Exception as exc:
        check("%s raised %s" % (getattr(fn, "__name__", "case"), type(exc).__name__), False, str(exc)[:200])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="leave scratch vaults on disk for inspection")
    args = ap.parse_args()
    print("HADES OS v3 test battery | python %s" % sys.version.split()[0])
    print("source vault: %s" % SRC)

    guard(t_positive)
    for label, fn, expect, level in [
        ("duplicate id", m_duplicate_id, "duplicate id", "error"),
        ("dangling relation", m_dangling, "dangling relation", "error"),
        ("malformed id reference", m_typo_id, "malformed id reference", "error"),
        ("status disagrees with folder", m_status_folder, "disagrees with folder", "error"),
        ("secret: labelled key", m_secret_labelled, "possible secret", "error"),
        ("secret: openai-style token", m_secret_token, "possible secret", "error"),
        ("secret: high-entropy token", m_secret_entropy, "possible secret", "error"),
        ("registry manifest inside 12_RUNTIME", m_runtime_manifest, "registry manifest inside 12_RUNTIME", "error"),
        ("non-ASCII registry path", m_nonascii_path, "non-ASCII path segment", "error"),
        ("gitignore drift from config", m_gitignore_drift, "gitignore does not exclude", "error"),
        ("nested git repo", m_nested_git, "nested git repo", "error"),
        ("zone without README", m_missing_readme, "zone without README", "error"),
        ("gitignored machine zone deleted", m_drop_machine_zone, "documented git boundary", "warn"),
        ("human-plane zone deleted", m_drop_human_zone, "missing zone", "error"),
        ("quarantine zone deleted", m_drop_quarantine_zone, "missing zone: 14_CANDIDATES", "error"),
        ("the vault's own .git at its root", m_git_at_vault_root, "errors: 0", "warn"),
        ("stale last_verified", m_stale_date, "treat as unverified", "warn"),
        ("unparseable date", m_bad_date, "unparseable date", "warn"),
        ("CJK character inside Persian", m_cjk, "persian hygiene", "warn"),
        ("Latin glued to Persian", m_glued, "persian hygiene", "warn"),
        ("id that breaks the pattern", m_unknown_id, "id", "error"),
        ("missing required field", m_missing_field, "classification", "error"),
        ("status outside the declared set", m_bad_status, "status", "error"),
        ("record in the wrong zone", m_zone_mismatch, "outside its zone", "error"),
        ("evidence path that is not on disk", m_missing_evidence, "evidence file does not exist", "error"),
    ]:
        guard(t_doctor, label, fn, expect, level)
    guard(t_refusals)
    guard(t_wiki)
    guard(t_archive)
    guard(t_status_accounts_every_zone)
    guard(t_markdown_and_amendments)
    guard(t_harness_bridge)

    ok = sum(1 for _, p, _ in RESULTS if p)
    bad = len(RESULTS) - ok
    for label, passed, detail in RESULTS:
        print("%s %s" % ("PASS" if passed else "FAIL", label))
        if not passed:
            print("     -> %s" % detail)
    print("-" * 64)
    print("checks: %d | passed: %d | failed: %d" % (len(RESULTS), ok, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
