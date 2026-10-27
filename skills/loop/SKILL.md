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

## Turning a candidate into a change (agent protocol)

1. Pick ONE candidate (start at the top).
2. Write the plan as a note in `90_Agent_Output/` (what / why / files touched).
3. Implement against a fixture-backed test like the one in `tests/`.
4. Run `python scripts/health.py` + the full suite — both must be green.
5. Propose placement with `zone_check` — agent cannot file into `20_Notes`.
   Commit only after the zone + write gates pass.

## Stop conditions (bounded run)

- Stop after 3 cycles or when the report lists zero P1/P2 — no treadmill.
- Budget: each cycle ≤ what fits one session; never loop forever.
- Everything unattended writes ONLY to `14_CANDIDATES/loop/` and
  `90_Agent_Output/` — both agent-writable by the fence.
- Regressions don't get hidden: if a metric says REGRESSED twice in a row,
  STOP and report to the human instead of forcing another "fix".
