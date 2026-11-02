---
name: drift-report
description: Compare the checked-in documents against the tree they describe — one cold scout, a bounded list, a drift report the gate can refuse. Run it after any change to a script, a zone, a gate or a measured number.
run_protocol: bounded
---

# drift-report

A document that describes a file the tree no longer holds is not stale prose, it is an
instruction that fails. EGM checked that with `/egm-drift-report`; here the same job runs on a
fresh subagent and lands in an artifact `scripts/goldfish_check.py` can refuse.

**Stop condition, first:** *If your harness has no subagent tool, stop and tell the user: a
review in the same context is not a Goldfish review.* A scout that shares the editor's context
reports the edit as fact.

## 1. Ask the doors that already measure

```
python scripts/health.py           # the gates that already measure links, planes, shelf, hosts, numbers
python scripts/doc_report.py --check   # a typed number that stopped being a measurement
python scripts/sync_hosts.py --check   # a projection that drifted from AGENTS.md
python 15_SYSTEM/scripts/hades.py doctor
```

These are drift too — do not re-check them by hand, and do not write their verdict into the
report as an opinion.

## 2. Send the scout

`11_CONTROL/reviewers/egm-explorer.md`, one dispatch, read-only (`writes: none`), handed one
folder and the document list. It enumerates **leaf files first**, then rolls a folder up only
after every child is described. Past **15 directories** it stops and reports the count to the
human instead of flattening what it never read — the report says `reported_to_human` and the
gate refuses a longer list that does not.

## 3. The report

`90_Agent_Output/reviews/drift-<YYYY-MM-DD>.md`: note frontmatter plus `scout_directories: <n>`
and `verdict: clean | drifted`, then

```markdown
## Enumeration
| field | value |
| --- | --- |
| directories | 12 |

## Drift
| document | citation | verdict | note |
| --- | --- | --- | --- |
| 00_START_HERE/START.md | scripts/gone_away.py | gone | the step names a script the tree dropped |
```

Verdicts are `gone` (the file is really not there), `stale` (it exists, the sentence about it is
wrong) and `moved` (it lives elsewhere now). An `ok` row is not drift — it is noise that makes
the real rows skimmable, and the gate says so.

```
python scripts/goldfish_check.py --drift 90_Agent_Output/reviews/drift-<YYYY-MM-DD>.md
```

It re-checks every row: the document must exist, the document must actually *name* the citation
it is accused of (a drift report can invent a defect), and a file called `gone` that is on disk
means the report is the stale thing.

## 4. Fix, or hand it over

One row becomes one finding: correct the document, or file the finding in
`14_CANDIDATES/loop/` with the command you ran and the output it printed (`skills/self-audit`).
A `drifted` verdict with nothing filed and nothing fixed is a report nobody read.

## Boundaries

- reads `00`–`10`, `11_CONTROL` and `scripts/`; never cites `12_RUNTIME`, `13_LAB` or a probe shelf
- edits nothing: the scout has no write tool, and a reviewer holding one is an editor
- no dependency, no network, no server; Python 3.9 standard library
- never re-measures a documented number by hand — `python scripts/doc_report.py --write` owns it
