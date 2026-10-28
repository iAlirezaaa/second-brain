---
id: map-eight-memory-planes
type: resource
title: "The eight memory planes: store, writer, reader, proof"
status: evergreen
owner: agent
topics: [memory, architecture, provenance, registry]
created: 2026-10-28
updated: 2026-10-28
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
| error | `15_SYSTEM/memory/lessons.jsonl` | — | `memory.py --add` (a lesson whose evidence does not open is refused) | `memory.py --recall`, MCP `memory_recall` | `tests/test_phase15_repo_memory.py` |
| decision | `02_WIKI/decisions/`, `09_OPERATIONS/decisions/` | — | plan door, then `hades.py set` for amendments | `hades.py show/list`, `hades.py search --query` | `tests/test_phase22_amend_a_record.py` |
| knowledge | `02_WIKI/**`, `skills/**` | `.kb/kb.sqlite` (currently `vault-template` only) | plan door, `scripts/promote.py` | `hades.py search --query` (BM25 over repo prose), `wiki.py` | `tests/test_retrieval_golden.py` |
| conversation | `15_SYSTEM/integrations/local-sources.md` (the contract) | `.brain-data/{sources,learning}` | `sources.py import/batch`, explicit selection only | `source_search` MCP, `sources.py search`, `lesson_recall` | `tests/test_sources.py` |

Provenance is structural, not decorative. Registry records carry `id`, `kind`,
`created_at`, `status` and an `amendments` ledger written by the tool that changed them.
Lesson rows carry `date`, `source`, `evidence` paths that the gate opens, `confidence` and
a verdict from a closed set. Imported sources carry `origin`, `imported_at` and the sha256
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
- **error** — 26 lessons with evidence; there is no separate error store, and the rows do
  not say which plane they belong to (issue #25).
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

## Contradiction awareness is not implemented

No plane compares two memories and reports a conflict. The nearest mechanisms each solve a
narrower problem: `supersedes` retires a registry definition; the `amendments` ledger
records field changes on one record; `memory.py` can supersede one lesson with another; the
candidate shelf asks a human to review. Two wiki notes that disagree, or a lesson whose
evidence stopped supporting it after another lesson landed, surface nowhere. Filed as
issue #24 rather than claimed here.
