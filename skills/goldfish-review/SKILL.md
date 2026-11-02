---
name: goldfish-review
description: Attack a design doc with zero-context subagents — zoom out, comprehension, three critics, re-audit, implementation readiness — then resolve the findings and hand the report to the human. Run it on every design doc before anything is built.
run_protocol: bounded
---

# goldfish-review

**Stop condition, first:** *If your harness has no subagent tool, stop and tell the user: a
review in the same context is not a Goldfish review.* No fallback, no degraded mode, no "this
time I will be objective". Say that sentence and end the run.

## The two roles

| role | context it is given | job |
|---|---|---|
| elephant | the project, the requirements, every earlier decision | explore and draft (`skills/elephant-draft`) |
| goldfish | the document and the source it cites, nothing else | find missing assumptions, unclear requirements, implementation risks |

Three mandates sit on every goldfish persona, and `python scripts/goldfish_check.py --personas`
refuses one missing any: **Strict Read-Only Protocol** (`writes: none`), **Stateless Mindset**
(a fresh subagent, handed no summary, reading no earlier round), **No Chitchat** (findings or
nothing). The personae are data, not prose: `11_CONTROL/reviewers/egm-*.md`, each declaring its
stage, range, audit vectors, bounded reading list and dispatch mode. `egm-comprehension` is
`spawn: direct` — a reviewer handed a synthesiser's summary of the document never read it — and a
stage the report's frontmatter records with no reviewer row behind it is refused.

## The split, and the ranges

Find the header `## Detailed Implementation Plan` (synonyms accepted: `## Implementation Plan`,
`## Work Breakdown`, `## Implementation Steps`). Above it is the **feature range**; from it down
is the **implementation range**. Re-resolve both to line numbers before *every* round: a fix
moves lines, and a stale range means the reviewer read a different document than the one being
graded. The gate refuses a range pointing past the end of the doc, and stage 9 over a doc with
no such header.

## Five stages, in dispatch order

1. `zoom_out` — `egm-zoom-out` reads the document cold; its report lands at
   `90_Agent_Output/reviews/<FEATURE>/rounds/egm-zoom-out-<round>.md` and the roster row names it.
2. `comprehension` — `egm-comprehension`, spawned **directly**, never through a synthesiser. Its
   report opens with two headings, verbatim: `What this proposes` and `How the existing system
   works, per the document`.
3. `critic` — over the feature range: `egm-design`, `egm-structural`, `egm-style`.
4. `intermediate_zoom_out` — `egm-zoom-out` again, auditing only what the applied fixes *added*.
5. `implementation_readiness` — over the implementation range: `egm-implementation-readiness`,
   `egm-codebase-details`, `egm-style`.

One synthesiser per stage collects the reports and dedups; it never paraphrases the document for
a reviewer, because a reviewer that reads a summary is not a goldfish.

## The loop, and when it stops

Severities 🔴 Blocker / 🟡 Major / 🟢 Nit, ids `<reviewer>-<round>-<n>`. A synthesizer spawns
parallel reviewers per stage (hierarchical) or one flat pass; either way **a reviewer that times
out, fails or returns no report did not review** — retry it once, then record it `failed`; never
count it as a reviewer with zero findings. A **clean round** is one where every dispatched
reviewer ran in a fresh context and none raised an unsettled Blocker or Major; a reviewer
recorded as not run makes the round *not* clean. **Converged** = two consecutive clean rounds.
Cap = 5 rounds. **Churn**: a new finding whose scope is an applied fix, and reverting that fix
would resolve it — say so, and stop re-fixing; settled findings are never re-opened under their
own id, while a fix that recurs gets a new id that reopens it. One re-audit per stage, maximum;
whatever survives becomes a recorded accepted trade-off.

## Resolve (elephant-side, one category per finding)

`CONTEST` — you are wrong, and it must be checkable: cite `file` or `file:symbol`, and the gate
refuses a contest whose evidence does not open. `ESCALATE` — the evidence lives outside the
files a reviewer can read: do not fix, give it to the human. `PROPOSE FIX` — name the edit.
`DECLINE` — nits only. Three rules: **do not add context only to satisfy a reviewer**, **do not
contest a comprehension gap** (rewrite the paragraph or cut the claim), **do not change a
severity**.

## The artifact

`90_Agent_Output/reviews/<FEATURE>/goldfish_review_report.md` — frontmatter `review_of`,
`stages`, `rounds`, `verdict` (converged | capped | aborted | in_progress) — plus the tables the
gate parses: `## Target`, `## Reviewers` (`reviewer | stage | range | round | context | status |
report`), `## Findings` (`id | reviewer | round | severity | status | category | reason |
evidence`), `## Rounds` (`round | clean | unsettled | not_run | note`), `## Comprehension`,
`## Accepted trade-offs`. Keep each reviewer's own report beside it: the run is only evidence if
a `git clone` can open it. Then judge it — the gate re-derives every verdict below from the
artifact, so a word typed in the wrong column does not pass:

```
python scripts/goldfish_check.py --report 90_Agent_Output/reviews/<FEATURE>/goldfish_review_report.md
```

## Then the human decides

Print the Target, the reviewer-status table and the prioritised findings with their proposed
edits, and ask: **auto-accept / continue / interactive breakdown / comment / custom**. Nothing
moves into `00`–`10` until the answer arrives (`python scripts/promote.py`, `hades.py apply
--approve` are the only doors). A review the gate refused is not a review.

## Boundaries

- never reads the drafting conversation, never reads another round's reasoning
- writes only into `90_Agent_Output/` and `14_CANDIDATES/loop/`; the human plane is the human's
- no dependency, no network, no server; Python 3.9 standard library, or the design is refused
- no typed counts: `python scripts/doc_report.py --write` owns the numbers
