---
id: map-harness2-to-hades
type: resource
title: "harness2 → HADES: what to adopt, what to refuse, and why"
status: evergreen
owner: agent
topics: [architecture, agents, reverse-engineering, harness, evidence, recovery]
created: 2026-11-02
updated: 2026-11-02
---

# harness2 → HADES map

Reverse-engineering note for [harness2](https://github.com/google-research/harness2), named as
**reference two** in `00_START_HERE/PROJECT_CHARTER.md` §3, which asks for exactly six things
from it: agent/task execution management, performance control and evaluation, error management
and retry, preserving the state of in-flight work, reliability and reproducibility of results,
and context management across the agent cycle — adapting only what is genuinely useful, and
refusing "copying without scrutiny, adding an unnecessary dependency, or complicating the
system without reason" (§3, closing paragraph).

What upstream *is*, stated from its own README (read 2026-11-02): "a plug-and-play framework
for recursive agent harnessing in an open world", where a harness is "the system around a model
that enables it to act as an agent: prompts, tools, memory, skills, orchestration, and more".
Task-level recursion refines the harness for the current task through a contrastive
**Propose → Probe → Compose** step — "propose edits", "probe their effects on the same task",
"compose a refined harness from behavioral contrasts between executions" — without ground-truth
feedback, over "invariant and domain edits". Harnessing-level recursion "updates a persistent
improvement harness with adopted harnesses and evidence-supported lessons from each task". Its
executor runs a real agent substrate (OpenCode by default, Codex behind `--substrate cx`), the
README states plainly that executor network access is unrestricted and the Codex sandbox is
disabled, and model-backed runs "incur API costs".

What HADES *did* with that is not a rumour: it is in this repo's own tracked text.
`rules/candidate.schema.json`, `scripts/probe.py`, `scripts/base.py` and `scripts/candidate_check.py`
each name harness2 in their own docstring; `15_SYSTEM/memory/lessons.jsonl` carries three rows
whose `source` field says `harness2 port` or names it directly.

## The verdict in one sentence

harness2 proved a **loop that only believes what it measured**; HADES took the loop and left the
model out of it — Propose/Probe/Compose became the shelf's three doors, the contrast between
executions became a content fingerprint a clone can re-derive, and the "keep what measured good"
policy became bytes on disk plus a command, because a policy with no mechanism behind it is a
wish.

## Adoption table

| harness2 concept | What it actually is there | Verdict in HADES | Script that holds it here | Test that proves it runs today |
|---|---|---|---|---|
| Propose → Probe → Compose (task-level recursion) | the current harness edits its own surface, the edit is probed on the same task, a refined harness is composed from the contrast | **adopted as the shelf's three doors, minus the self-editing** — `loop.py` proposes typed rows, `probe.py` executes the command the row itself declares, `promote.py` / `loop.py --dispose` compose the outcome into the vault or the ledger | `scripts/loop.py` → `scripts/probe.py` → `scripts/promote.py`, contract in `rules/candidate.schema.json` | `tests/test_phase7.py`, `tests/test_phase12_probe.py`, `tests/test_phase13_candidate_contract.py` |
| "a claim about behaviour is only evidence if something was executed and its output was looked at" | the rule the pipeline rests on | **adopted verbatim and made a fence** — `verdict: helped` with no probe record, or with a probe that never ran, is refused; a checkbox is not a measurement | `scripts/candidate_check.py` (`check_candidate`, `PROBE_OUTCOMES`) | `tests/test_phase13_candidate_contract.py::test_behaviour_claim_without_a_probe_is_refused`, `::test_a_probe_that_never_ran_is_not_evidence` |
| invariant vs domain edits (the two edit types the pipeline names) | typed edit surface, contrasted separately | **adopted as `dimension`, with a harder bar** — `invariant` means the row would move the measuring apparatus (`rules/`, `scripts/`, `tests/`), so a real run is always required, whatever the verdict says | `rules/candidate.schema.json` (`required.dimension`), `scripts/candidate_check.py` (`needs_probe`) | `tests/test_phase13_candidate_contract.py::test_invariant_candidates_always_need_a_run`, `::test_an_unknown_dimension_or_verdict_is_refused` |
| behavioral contrast between executions | the refinement signal: two runs, look at what differed | **adopted as content-addressed state** — the tree is inventoried and fingerprinted before and after the probe, and the candidate's own bytes are hashed, so an edit made after the run cannot inherit the run's evidence | `scripts/common.py` (`tree_inventory`, `state_fingerprint`, `inventory_diff`) | `tests/test_phase12_probe.py::test_the_ledger_records_after_and_the_candidate_digest`, `tests/test_phase13_candidate_contract.py::test_a_probe_taken_on_an_older_tree_is_stale` |
| an edit whose rollout produced nothing; an edit that lands off-surface | the probe's safety rules — an off-surface edit is bounced back by name | **adopted and hardened into exit codes** — `undelivered` and `unsafe-mutating` exit 1, so nothing that produced nothing can be promoted on top of it | `scripts/probe.py` (`outcome_of`, `unsanctioned_moves`, `probe_writes`) | `tests/test_phase12_probe.py::test_producing_nothing_is_unsafe_not_unproven`, `::test_writing_where_the_candidate_said_nothing_is_unsafe` |
| what a probe may execute | a full agent substrate with a live model and open network | **adopted as an allowlist with two named refusals** — argv only, `.py` only, only `scripts/` and `15_SYSTEM/scripts/`, and `base.py` (recovery is the owner's act) and `install.py` (writes outside the repo) refused by name with the reason printed | `scripts/probe.py` (`ALLOWED_DIRS`, `REFUSED_PROBES`) | `tests/test_phase12_probe.py::test_the_installer_is_reserved_because_it_writes_outside_the_repo`, `tests/test_phase30_registry_hardening.py::test_the_recovery_script_is_reserved_and_the_reason_names_the_owner` |
| keep the harness that measured better; discard the one that did not | upstream keeps adopted harnesses across tasks; its README names no rollback command and no fallback flag | **adopted as a mechanism, precisely because upstream leaves it as policy** — the last known good state is bytes on disk plus the fingerprint proving those bytes are the state the record describes | `scripts/base.py` (`--save` refuses a red house, `--recover` restores and re-proves, `--status` compares) | `tests/test_phase20_known_good_base.py`, `14_CANDIDATES/loop/bases.jsonl` (the measured bases, one line each) |
| `keep_base` as a legitimate result | not every probe improves; saying so is the honest output | **adopted as a verdict AND a disposition** — "deciding to change nothing needs no run"; a `keep_base` row stays on the shelf where it can be read and is never promotable | `rules/candidate.schema.json` (`verdict.keep_base`), `scripts/candidate_check.py` (`DISPOSITIONS`), `scripts/promote.py` (`candidate_gate`) | `tests/test_phase13_candidate_contract.py::test_keep_base_stays_on_the_shelf`, `tests/test_phase14_typed_candidates.py::test_drop_closes_the_row_and_the_arithmetic_still_adds_up` |
| the persistent improvement harness with evidence-supported lessons (harnessing-level recursion) | a second recursion level: adopted harnesses + lessons guide the next refinement | **adopted as the repo's own memory, read before acting** — the first move in `AGENTS.md` is `memory.py --recall`, and a lesson whose evidence path no longer opens is refused at write time | `scripts/memory.py`, `rules/memory.schema.json`, `15_SYSTEM/memory/lessons.jsonl` | `tests/test_phase15_repo_memory.py` |
| recursion across runs: worse is not noted, it is reverted | the outer loop | **adopted as a loud ratchet** — each cycle compares with the previous run in `history.json`; a REGRESSED verdict is printed and a P1 signal exits non-zero | `scripts/loop.py` (`ratchet`, `candidates`), `14_CANDIDATES/loop/history.json` | `tests/test_phase7.py::test_regression_detected_when_situation_worsens`, `::test_no_new_failure_is_stable_not_regressed` |
| refining without ground-truth feedback (the loop judges its own edits) | no labels; the contrast is the judge | **partly refused: the judge stays a human holding a receipt** — a row the loop raised is `verdict: proposed`, legal on the shelf, never promotable | `scripts/promote.py` (`candidate_gate`), `scripts/loop.py` (`row_text`) | `tests/test_phase14_typed_candidates.py::test_promote_refuses_a_row_that_was_only_proposed` |
| the eight editable harness surfaces (system prompt, guardrails, memory, tool guidance, subagents, skills, scripts, plugins) | the thing the agent is allowed to rewrite about itself | **adopted as definitions, refused as an edit target** — the same surfaces are registry kinds in `11_CONTROL`, changed only through `plan` → `apply --approve`; the system prompt is one canon file projected to every host | `15_SYSTEM/config/system.json` (`kinds`), `11_CONTROL/`, `scripts/sync_hosts.py` | `tests/test_phase17_control_plane.py`, `tests/test_phase16_host_independence.py` |
| the benchmark suite and its five commands (`setup → check → run → judge → report`, `--k`, parallel/sequential modes) | open-world work tasks judged against published rubrics | **refused** — no downloaded rubric, no model judge, no per-run cost; measurement here is a command run inside this repo plus a locally curated case set that refuses to compare itself with a different case set | `scripts/probe.py`, `15_SYSTEM/scripts/backend/retrieval_eval.py` | `tests/test_retrieval_golden.py`, `tests/test_phase12_probe.py` |
| unrestricted executor network, sandbox disabled, API-cost runs | stated in the README as the operating condition | **refused (charter §2, the non-negotiable independence law)** — stdlib only, offline, no keys; `pyproject.toml` declares no runtime dependency at all and CI runs the suite on ubuntu + windows across 3.9 and 3.12 | `pyproject.toml`, `.github/workflows/ci.yml` | `tests/test_phase29_vector_seam.py` (patches `socket` to prove nothing calls out), `tests/test_phase16_host_independence.py` |
| automatic recursive self-modification of the harness | the framework's whole point | **refused** — agents propose, humans decide; the machine plane may write to `14_CANDIDATES/loop/` and nowhere else in the human plane | `rules/zones.json`, `scripts/zone_check.py`, `skills/loop/SKILL.md` | `tests/test_phase3.py` |

## The spine, in the order it shipped

`14_CANDIDATES/loop/` is where this landed, and the order is in the git log, readable after a
`git clone`: the probe first (`fd5ff3b`, "a behaviour claim needs one real execution behind it"),
then the contract that judges the claim (`fc5a18b`, issue #3), then typed rows and the ledger
that counts them (issue #9), then the base and the way back (`9167e99`, `9275521` — the roadmap
row that admits the piece was still unshipped). Four files carry the spine:

- **Propose** — `scripts/loop.py` collects signals (integrity gates, test failures, stale inbox,
  unanswered searches, TODO debt) and writes one typed row per signal, each naming evidence a
  reader can open. A cue already on the shelf is not proposed twice.
- **Probe** — `scripts/probe.py` runs the row's declared command once, diffs the tree, names
  every move, and records `pass` / `fail` / `undelivered` / `unsafe-mutating` in
  `14_CANDIDATES/loop/probes/` (gitignored state — which is why a shelf row cites the exported
  snapshot, never the probe folder; see `tests/test_phase19_evidence_survives_a_clone.py`).
- **Judge** — `scripts/candidate_check.py` is the fence over `rules/candidate.schema.json`:
  evidence must resolve, a verdict must match the outcome of a *fresh* probe, and the ledger's
  count identity `proposed == adopt + revise + drop + keep_base + open` must hold against the
  folder. It is a gate in `scripts/health.py`, so a shelf that lies fails CI.
- **Compose** — `scripts/promote.py` moves an adopted row into the human plane and writes the
  `adopt` disposition itself; `scripts/loop.py --dispose` records `revise`, `drop` or `keep_base`
  and refuses to type `adopt` by hand, because adopt is a move, not a label.

## keep_base is an output, and the base is bytes

Charter §3's harness2 list asks for error handling and retry, preserved state, and
reproducibility. The honest reading is that a run which measures worse must not be kept, and
that "the state before it" has to be a thing, not a memory. `scripts/base.py` is that thing:

- `--save` runs `scripts/health.py` first and refuses a red house — nothing that could not pass
  becomes the thing everybody falls back to;
- the snapshot covers exactly what `common.state_fingerprint` counts, so `15_SYSTEM/backups/` is
  paperwork and recording a base cannot invalidate the state it just recorded;
- `--recover` restores the bytes, re-proves the fingerprint, and appends `fell_back: true` to the
  recovery journal `scripts/base.py` names (`RECOVERY_JOURNAL`, `14_CANDIDATES/loop/recovery.jsonl`
  — the file a fall back creates, not one that ships); it reverts the **brain**, never the shelf,
  and files added since the base are named and left alone instead of deleted by a script asked to
  go backwards;
- a journal entry whose snapshot bytes are gone is refused out loud — a record is not an artifact.

The law lives where an agent reads it before acting (`AGENTS.md`, "The way back is a mechanism,
not an intention"), and `tests/test_phase20_known_good_base.py` is red if any of it drifts.

## What was refused, and why it stays visible

The refusals are not deletions; they are rows with reasons, in the charter's own terms (§2
independence, §3 "no blind copying, no unnecessary dependency, no needless complication"):

- **the model in the loop** — a runtime LLM editing its own harness needs a paid model call and
  a second harness to host it. Refused: no server, no paid service. The deterministic engine is
  `15_SYSTEM/scripts/backend/engine.py`, and an LLM step is a human decision, never a step type.
- **the executor substrate (OpenCode / Codex)** — refused as a dependency; the harness door here
  is the protocol harnesses already speak, `15_SYSTEM/scripts/mcp_server.py`.
- **unrestricted network and a disabled sandbox** — refused (charter §2): the probe is argv-only,
  `.py`-only, and confined to two script directories.
- **published benchmark rubrics as the judge** — refused: an outcome a reader cannot reproduce
  after `git clone` is not evidence, so the judge is a real command plus the golden set in
  `tests/fixtures/retrieval-golden.json`.
- **automated self-repair** — refused: `verdict: proposed` never leaves the shelf, and the two
  scripts that could reach outside the repo or undo the owner's state are reserved by name.
- **auto-raised "improvement" without a measurement** — refused: `NO_ENTRY` and `keep_base` are
  legal answers, so a cycle that found nothing has a row that says so instead of a fabricated
  lesson.

## Health law learned from this

A freshness gate is only worth what its fingerprint is worth. `common.state_fingerprint` measures
the tree **minus its paperwork** (`PAPERWORK_SKIP_PATHS`: the shelf, the runtime plane, the
backups, the generated catalogue), so filing a decision never ages a measurement while any real
edit always does — `tests/test_phase12_probe.py::test_filing_paperwork_does_not_invalidate_a_measurement`
and `tests/test_phase36_doors_tell_the_truth.py::test_an_index_run_does_not_age_a_probe` hold
both halves. That is harness2's contrast, made to survive a human writing down what happened.

## Final folder structure — answer

Nothing moved, nothing was added at the top level; every piece of this port landed inside an
existing zone:

```
00_START_HERE/            untouched (the charter names harness2 in §3)
01_INBOX … 10_ARCHIVE     untouched — the human plane
11_CONTROL/               registry kinds stand in for the "editable harness surfaces"
14_CANDIDATES/loop/       the shelf: rows, ledger.jsonl, bases.jsonl, gaps.jsonl, reports
15_SYSTEM/scripts/        the deterministic engine and the door (no harness2 substrate)
scripts/                  loop.py, probe.py, candidate_check.py, promote.py, base.py, memory.py
rules/                    candidate.schema.json, memory.schema.json, zones.json
02_WIKI/reference_maps/   this map, beside the SuperAGI map
```

`14_CANDIDATES/loop/probes/` is deliberately outside the tracked plane: probe records are the
evidence *inside* a row, never the row's citation. The boundary is `common.clone_readable()` and
the test that polices it is `tests/test_phase19_evidence_survives_a_clone.py`.

## Still open, in order of value

1. **Rows still waiting for a human** — six rows sit on the shelf, `proposed` and undecided
   (`14_CANDIDATES/loop/ledger.jsonl`). harness2 composes automatically; this repo does not, so
   the count identity keeps them visible until the owner disposes them.
2. **`keep_base` is never taken for you** — the probe may not run `base.py` by design; a
   self-restoring agent is a refusal, not a backlog item.
3. **The improvement harness is one undifferentiated ledger** — `15_SYSTEM/config/issues.json`
   still carries #25 (`lessons are not typed by plane`), so error memory and decision memory share
   one file and a reader cannot ask it for only one kind. harness2 keeps its lessons attached to
   the harness that earned them; until that row closes, this repo's rows carry a `verdict` and a
   `source` but no plane.
4. **Nothing reverts a change on its own** — `scripts/base.py --recover` is a command, not a
   reaction; the ratchet in `scripts/loop.py` shouts REGRESSED and stops, because deciding to go
   backwards belongs to the owner (charter §13, recoverability with a human in the seat).

Closed while this port was still open: the loop's cadence, which used to be a cron comment and a
remembered habit at once, is now a registry record
(`11_CONTROL/schedules/SCH-0D1E2F3A-improvement-loop.json`) read through
`scripts/loop.py --due` (phase 28).

## Where a fresh reader starts

`python scripts/health.py` (the shelf gate included), then `python -m unittest discover -s tests`
with `tests/test_phase12_probe.py`, `tests/test_phase13_candidate_contract.py`,
`tests/test_phase14_typed_candidates.py` and `tests/test_phase20_known_good_base.py`, then
`python scripts/base.py --status` to see the base and the current state side by side. The sibling
maps in this folder are `02_WIKI/reference_maps/superagi-to-hades-map.md`,
`02_WIKI/reference_maps/claude-obsidian-to-hades-map.md` and the index at
`02_WIKI/indexes/reference-maps.md`.
