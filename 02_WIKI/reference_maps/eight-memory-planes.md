---
id: map-eight-memory-planes
type: resource
title: "The eight memory planes: store, writer, reader, proof"
status: evergreen
owner: agent
topics: [memory, architecture, provenance, registry]
created: 2026-10-28
updated: 2026-11-02
---

# The eight memory planes

Charter section 5 asks for persistent memory in eight planes — project, repository, agent,
task, error, decision, knowledge, conversation — "structured, searchable,
contradiction-aware". This map answers the first three claims plane by plane: which paths
carry it, who writes it, who reads it, and which test proves the reader still works. The
machine-readable copy lives at `15_SYSTEM/config/system.json` → `memory_planes`;
`scripts/plane_check.py` fails when a plane is dropped from that map, when a tracked store
no longer opens, or when a reader script, test or this document goes missing. Counts below
were measured on 2026-10-28 with `hades.py list`, `memory.py --list` and `doctor`.

## The map

| plane | tracked store | disposable store | writer | reader | proof |
|---|---|---|---|---|---|
| project | `03_PROJECTS/<container>/<PRJ-id>/project.json` | — | `hades.py plan --kind project` → `apply --approve` | `hades.py list/show`, MCP `registry_list` | `tests/test_phase21_records_are_visible.py` |
| repository | `HANDOFF.md`, `CHANGELOG.md`, `MEMORY.md` | — | `scripts/handoff.py`, `scripts/doc_report.py`, `scripts/memory.py --render` | every host reads `HANDOFF.md` §1 before acting (`AGENTS.md`) | `tests/test_phase18_measured_docs.py` |
| agent | `11_CONTROL/agents/<AGT-id>/agent.json` + `OVERVIEW.md` | `.kb/ltm.sqlite` (FTS5 store/fetch, `backend/ltm.py`) | `hades.py plan --kind agent` | `hades.py list --kind agent`, MCP `registry_list` | `tests/test_phase17_control_plane.py` |
| task | `09_OPERATIONS/tasks/TSK-*.json` | `12_RUNTIME/agent_runs/<RUN>/{run.json,steps.jsonl}` | `hades.py plan --kind task`; `runs.py start/step` | `runs.py list/show`, MCP `runs_list`/`runs_show` | `tests/test_phase22_harness_bridge.py` |
| error | `15_SYSTEM/memory/lessons.jsonl` | — | `memory.py --add` (a lesson whose evidence does not open, whose plane is missing or unmapped, whose verdict contradicts a live lesson, or whose validity window cannot be read is refused at the door) | `memory.py --recall`, `memory.py --contradictions`, `memory.py --windows`, MCP `memory_recall` | `tests/test_phase15_repo_memory.py`; the `plane` field (issue #25) and the contradiction rule (issue #24) are proven by `tests/test_phase40_lesson_planes_and_contradictions.py` and refused by `memory.py --check`; the `verified_at`/`expires` window (phase 44) by `tests/test_phase44_lesson_validity_windows.py` |
| decision | `02_WIKI/decisions/`, `09_OPERATIONS/decisions/` | — | plan door, then `hades.py set` for amendments | `hades.py show/list`, `hades.py search --query` | `tests/test_phase22_amend_a_record.py` |
| knowledge | `02_WIKI/**`, `skills/**` | `.kb/kb.sqlite` (currently `vault-template` only) | plan door, `scripts/promote.py` | `hades.py search --query` (BM25 over repo prose), `wiki.py` | `tests/test_retrieval_golden.py` |
| conversation | `15_SYSTEM/integrations/local-sources.md` (the contract) | `.brain-data/{sources,learning}` | `sources.py import/batch`, explicit selection only | `source_search` MCP, `sources.py search`, `lesson_recall` | `tests/test_sources.py` |

Provenance is structural, not decorative. Registry records carry `id`, `kind`,
`created_at`, `status` and an `amendments` ledger written by the tool that changed them.
Lesson rows carry `date`, `source`, `evidence` paths that the gate opens, `confidence`, a
verdict from a closed set, and a `plane` from the eight mapped ids (or the stated `unclassified`)
so an error-plane lesson is told from a decision-plane one without reading prose (issue #25). Imported sources carry `origin`, `imported_at` and the sha256
of the bytes actually stored; an approved lesson additionally carries the proposal id and
the approval receipt. `HANDOFF.md` cites the commit it was generated at.

## What the clone can open today

- **project** — 0 records; the five containers and `portfolios/` ship with `.gitkeep` only.
- **repository** — `HANDOFF.md` is refreshed by `handoff.py` and refused when its numbers
  drift (`doc_report.py --check`); 26 lessons; `CHANGELOG.md` records what shipped.
- **agent** — 2 agent records (`AGT-78188303 repo-auditor`, `AGT-B746F5DE loop-runner`),
  both `draft`; 10 skill records in `11_CONTROL/skills`.
- **task** — 0 task records; 0 runs in this clone because `12_RUNTIME/` is absent at the
  git boundary by design (`hades.py doctor` says so). The reader is proven with fixtures.
- **error** — 26 lessons with evidence, each now typed by a `plane` field (of the active rows:
  11 error, 8 agent, 4 decision, 3 knowledge; measured with `memory.py --migrate-planes`). There
  is still no separate error store, but the rows no longer hide their kind: `memory.py --check`
  refuses a row with a missing or unmapped plane, and `--migrate-planes` assigns one from each
  row's own `source`/`topics` (issue #25). See `--contradictions` for the pair report below.
- **decision** — 0 records of kind `decision`; the one recorded decision is a `wiki_note`
  (`WIK-B7ED0084`, draft) under `02_WIKI/decisions`.
- **knowledge** — 1 registry note plus plain notes under `02_WIKI/`; `hades.py search`
  covers the repo's own prose (human zones, `skills/`, root documents) and skips
  `15_SYSTEM`. `kb.py` indexes this repo's human plane too (phase 27), 43 notes here,
  machine plane excluded by `common.clone_readable()`'s boundary.
- **conversation** — nothing imported into this clone; the store is gitignored and local.
  The reader shipped with phases 31–34 (`source_search`, `sources.py search`), but with an
  empty store it answers nothing, and extraction is still a manual act with no defined
  skill or gate. Issue #20 keeps the extraction path open; `kb.py` over this repo's corpus
  shipped in phase 27.
  A disposable lab measured the whole path on 35 imported sources (duplicate add 0,
  transfer verified, one conflict refused then accepted with `--allow-conflicts`,
  propose → evaluate → approve → recall with origin preserved); the numbers are in
  `HANDOFF.md` §2 and the store was discarded with the lab.

## Fresh clone rule

A plane's tracked store must open in a clone with no disposable state. `plane_check.py`
requires every `tracked_store` path and reports `disposable_store` paths only when absent,
so `12_RUNTIME/`, `.brain-data/` and `.kb/` never make the gate red. The same boundary is
enforced again by `tests/test_phase19_evidence_survives_a_clone.py`, which refuses evidence
that lives behind it.

## Contradiction awareness is measured and enforced (issue #24)

Charter section 5 asked for memory that is "contradiction-aware", and for a long time nothing
compared two pieces of knowledge: `supersedes` retired a definition (registry only), amendments
recorded field changes on one record, the candidate shelf asked a human. The issue said the
**definition** must be written down and measured before the code. It now is.

Two **active** lessons contradict when all four conditions hold on folded text:

1. **same plane** — both rows carry the identical `plane` value (issue #25's field);
2. **shared topic** — their `topics` lists intersect on at least one entry;
3. **high cue-overlap** — the Jaccard similarity of the two cues is at least `0.50`, where a cue's
   tokens are what `memory.py`'s own `tokens()` yields (lowercased, stopwords and sub-three-letter
   words dropped) and Jaccard is `|A ∩ B| / |A ∪ B|`;
4. **opposite verdict** — the verdict pair is `helped` vs `hurt`. `keep_base`, `proposed`,
   `confounded` and `no_observed_effect` are deliberately not opposite to `helped`: treating them
   as such would read agreement as conflict.

The similarity is stdlib, deterministic and reproducible from a `git clone` — no model, no
embedding, `vector_search` stays off.

**The threshold is measured, not guessed.** On the shipped ledger (325 active pairs):

| measurement | number |
|---|---|
| closest same-plane + shared-topic pair by cue-overlap | `0.31` (`mem-gates-that-pass-locally-are-not-green` / `mem-gates-break-on-local-state`) — and it **agrees**, so a lower bound would invent a conflict |
| pairs of opposite verdict (`helped` vs `hurt`) | `0` at every threshold |
| active contradictions on the shipped ledger | `0` |

`0.50` sits above every agreeing pair yet below a "same situation, opposite conclusion" overlap,
so it fires only on a real disagreement. Because the shipped ledger genuinely has **no**
contradiction, none was rewritten — the ledger stayed append-only and honest, and the rule is
proven with fixtures instead (`tests/test_phase40_lesson_planes_and_contradictions.py` shows the
refusal in one direction and the pass in the other).

**See it yourself:**

```
python scripts/memory.py --check           # refuses (nonzero) when an ACTIVE pair conflicts
python scripts/memory.py --contradictions  # prints every measured pair with its numbers
```

A pair linked by `supersedes` (one lesson retired the other) is reported as **resolved**, not
refused — the conflict became a decision, which is exactly what `supersedes` is for. If a genuine
active conflict ever lands, `--check` refuses it and the human decides whether to supersede,
correct the evidence, or file it on `14_CANDIDATES/loop/` as a candidate note; the gate surfaces
the disagreement, it never silently edits the history that produced it.

## A lesson states how long it is certain for (phase 44)

Graphiti and Zep keep two clocks on every edge: when a fact was discovered and when it stops
being true. The LLM that would have to decide the second one is refused by charter §2, but the
window itself is free, so a lesson row may now carry two optional calendar days:

| field | means | absent means |
|---|---|---|
| `verified_at` | the day a person last re-checked this row's evidence | nobody re-checked it |
| `expires` | the last day the claim still counts as certain | **evergreen** — the row states no window |

The rule, in one line and enforced by `scripts/memory.py`: **no `expires` = evergreen;
`expires >= today` = current; `expires < today` = stale; a field that is not a `YYYY-MM-DD` day,
a `verified_at` in the future, or an `expires` that closes before it opened = invalid.**

A stale row is a *named gate row*, not a quiet one:

```
python scripts/memory.py --check      # INVALID  STALE mem-<id>: expires YYYY-MM-DD, N day(s) past…
python scripts/memory.py --windows    # the measured counts, one line per dated claim
python scripts/memory.py --recall "…" # [id | verdict | conf] the lesson  [STALE: expires …]
```

`--check` refuses (exit 1, so `health.py` goes red) and `--recall` marks the answer, because a
claim a reader holding only this clone cannot re-check must never be reported as merely OK. What
the gate does **not** do is edit: the row, its line in `MEMORY.md` and its bytes in
`lessons.jsonl` survive the refusal — retiring a claim is a human act through
`--add --supersedes`, re-verifying one is a human act through `--verified-at`/`--expires` on a new
row. A superseded row that is stale is reported by `--windows` and not refused, since it is not
presented as certainty anywhere.

One rule, two readers: the machine plane's door has no separate memory of its own —
`mcp_server.py`'s `memory_recall` tool calls `memory.recall()` and appends the same
`memory.recall_mark()`, so an agent asking the ledger a question sees the identical
`[STALE: expires …, re-check before applying]` suffix a human sees in `--recall`, and the row is
still returned. `tools/list` says so in the tool's own description
(`tests/test_phase44_lesson_validity_windows.py::TheDoorMarksTheWindowToo`).

**The measurement behind the default, not a wish.** `python scripts/memory.py --windows` on this
repo prints the live counts, and every count it has ever printed on the shipped ledger is the same
shape: **zero stale**. Not one shipped lesson carries `expires` or `verified_at`, so none can be
out of its window — which is why `absent = evergreen` is the default. The alternative (key the rule
on the existing `date` field and call anything older than N days stale) would have aged every row by
a claim the row never made: `date` is when the lesson was written, not when it stops being true. The
row count is deliberately not quoted here — a hand-typed number in a reference map goes false the
moment a lesson lands, and a lesson landing is the normal business of this repo. Read it from
`--windows`. No date was written into `15_SYSTEM/memory/lessons.jsonl` to make the gate bite; the
refusals above are proven with fixtures
(`tests/test_phase44_lesson_validity_windows.py`), and there is no `--migrate-window` command,
because migrating would mean inventing a window for every lesson in the ledger.

## What a lesson's tags are NOT

The window is about a *claim*, not about a tool. The behaviour tags a phase-44 harness door
carries (`read_only` / `idempotent` / `destructive`, cross-checked against an actor's
`tool_allowlist`) live in `15_SYSTEM/scripts/mcp_server.py --check-tools` and
`backend/tools_kit.py`; they are listed here only so the two vocabularies are not confused for
one another.
