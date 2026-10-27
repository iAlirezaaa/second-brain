---
name: loop
description: The continuous-improvement ratchet — one cycle per run; the human promotes what it produces.
run_protocol: bounded
---

# loop — the house gets stronger while you sleep

**Law:** the loop never edits the human plane and never edits code directly. It
collects signals, writes candidates to `14_CANDIDATES/loop/`, and stops. The
human promotes the good candidates (that is the whole promotion gate).

## One cycle

```
python scripts/loop.py                 # full: + test suite
python scripts/loop.py --no-tests      # fast, e.g. before other work
```

The cycle is also scheduled nightly as GitHub Actions `loop` — reports land in
`14_CANDIDATES/loop/` as commits you can review on GitHub.

## Inside the report

- **Health signals** — links, frontmatter, tests, TODO hygiene.
- **Ratchet** — comparing *this run vs the previous*: `improved / stable /
  REGRESSED`. A REGRESSED line is the loudest item in the house.
- **Candidates** — prioritized P1 (red house → fix now), P2 (backlog: pending
  approvals, unanswered searches), P3 (hygiene). P1 makes the script exit 1,
  so CI and agents cannot sleep on it.

## The candidate contract

A row on the shelf is a claim, so it carries evidence. `rules/candidate.schema.json`
is the law and `scripts/candidate_check.py` is the fence (`15_SYSTEM/templates/
loop-candidate-NOTE.md` is the shape to copy):

- `dimension:` `invariant` (you would change the measuring apparatus — rules, scripts,
  tests) or `domain` (you would change content). An invariant row always needs a run.
- `cue` / `lesson` / `evidence` / `confidence` / `verdict`. `verdict: helped` without a
  fresh probe is a checkbox, not a measurement, and `promote` refuses it.
- `keep_base` is an output, not a failure: measuring and deciding to change nothing
  needs no run. `NO_ENTRY` is the legal empty row — "nothing in memory applied" is data.
- Freshness is content-addressed: a probe records the state fingerprint and the digest of
  the claim itself, so neither a later repo change nor an edited verdict inherits old evidence.

## Turning a candidate into a change (agent protocol)

1. Pick ONE candidate (start at the top).
2. Write the plan as a note in `90_Agent_Output/` (what / why / files touched).
3. Implement against a fixture-backed test like the one in `tests/`.
4. `python scripts/probe.py --candidate 14_CANDIDATES/loop/<row>.md` — one real
   execution of the declared command; then `python scripts/candidate_check.py` must pass.
5. Run `python scripts/health.py` + the full suite — both must be green.
6. Propose placement with `zone_check` — agent cannot file into `20_Notes`.
   Commit only after the zone + write gates pass.

## Stop conditions (bounded run)

- Stop after 3 cycles or when the report lists zero P1/P2 — no treadmill.
- Budget: each cycle ≤ what fits one session; never loop forever.
- Everything unattended writes ONLY to `14_CANDIDATES/loop/` and
  `90_Agent_Output/` — both agent-writable by the fence.
- Regressions don't get hidden: if a metric says REGRESSED twice in a row,
  STOP and report to the human instead of forcing another "fix".
