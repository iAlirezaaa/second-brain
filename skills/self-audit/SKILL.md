---
name: self-audit
description: Walk the whole repo as a stranger, turn every finding into a counted issue or shelf row, then fix them test-first. Run before a release, after a regression, or when the docs and the code have drifted apart.
---

# self-audit

An audit that ends in a paragraph of findings has changed nothing. Every finding becomes a
row with a number attached, and every fix carries a test that failed before it.

## 1. Rebuild what a stranger actually gets

```
python scripts/ci_hades_plane.py --battery     # a fresh clone: doctor, seeder, zone counts, hygiene
py -3.9  -m unittest discover -s tests
py -3.10 -m unittest discover -s tests
python scripts/health.py
```

Both Python versions, because CI runs both and a 3.10-only feature is a red build on Linux.
Do not audit your working folder — audit the clone replica. Untracked local files hide
missing `git add` entries, and that is how "works on my machine" is born.

## 2. Ask the questions that find real defects

For each claim in `README.md`, `00_START_HERE/*.md` and the doors: which command produces
this number, and does it produce it *now*? A count read from the owner's seeded folder is
not a property of the repo. Then: does every script a document names exist and run? Does
every path a document names resolve (`scripts/sync_hosts.py --lint` does this for the
entrypoint)? Is any gate silent on success, so nobody notices when it stops running? Can a
lie pass — a verdict without a probe, evidence that does not open, an id used twice?

## 3. File the finding where it cannot be forgotten

On GitHub, when you have write access (probe the credential, never print it):

```
python - <<'PY'   # or the equivalent gh/glab call — one issue per finding
# title = the observed wrong behaviour, body = repro command + expected + actual + severity
PY
```

Without access, the same row goes on the shelf instead — `14_CANDIDATES/loop/` with
`verdict: proposed`. Never a chat log. Issues and shelf rows are counted;
`python scripts/candidate_check.py` reconciles the arithmetic (`proposed == adopt + revise +
drop + keep_base + open`), so an ignored finding stays visible instead of quietly expiring.

## 4. Fix test-first, one theme per commit

Record where you started before you start: `python scripts/base.py --save --note "pre-audit"`.
It refuses unless every gate is green, which is the same preflight the audit wants anyway, and
it gives a fix that measures worse somewhere to go back to — `python scripts/base.py --recover`
restores those bytes, re-proves the fingerprint and writes `fell_back: true`.

Write the test that reproduces the finding, watch it fail, fix, watch it pass, commit that
one theme. A monolithic commit hides which change was load-bearing. Then close the issue
with the commit that fixed it, and if the finding taught a transferable lesson
(`skills/memory`) record it with evidence.

## 5. Say what did not get fixed

Report the numbers you measured — gates green, tests passing, issues closed, rows still
open — and stop. An audit that "improved everything" was not an audit.
