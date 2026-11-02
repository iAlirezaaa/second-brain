---
id: index-reference-maps
type: resource
title: "Reference maps: one line per repo this brain was reverse-engineered from"
status: evergreen
owner: agent
topics: [architecture, agents, knowledge-management, provenance]
created: 2026-11-02
updated: 2026-11-02
---

# Reference maps

`00_START_HERE/PROJECT_CHARTER.md` §3 names three reference repos and asks for their logic, not
their stack — and it forbids blind copying. Each map below is the standing answer for one of them:
what upstream actually is (verified from its own README), what HADES adopted, what it refused with
the reason, and the script **plus the test** holding each adopted piece. One line per map here, so
no map is a note nobody links. The last two rows are peers the owner's brief added after the
charter was written: one is the same discipline pointed at a design process instead of a codebase,
the other is the closest existing product to this brain's own idea.

| Map | Upstream | Held by |
|---|---|---|
| [[superagi-to-hades-map]] | `TransformerOptimus/SuperAGI` — the orchestration stack: agents, tools, workflow, vector seam | `15_SYSTEM/scripts/backend/`, `15_SYSTEM/scripts/mcp_server.py`, `15_SYSTEM/scripts/runs.py` |
| [[harness2-to-hades-map]] | `google-research/harness2` — recursive harness refinement: Propose → Probe → Compose, keep-base | `scripts/loop.py`, `scripts/probe.py`, `scripts/candidate_check.py`, `scripts/promote.py`, `scripts/base.py` |
| [[claude-obsidian-to-hades-map]] | `AgriciDaniel/claude-obsidian` — a second brain that respects its vault: transaction core, lint, secret hygiene | `15_SYSTEM/scripts/hades.py`, `scripts/write_gate.py`, `scripts/link_check.py`, `scripts/issues.py` |
| [[elephant-goldfish-to-hades-map]] | `google/elephant-goldfish-model` — design with an elephant, review with a goldfish: five stages, zero-context reviewers, one artifact per round | `scripts/goldfish_check.py`, `11_CONTROL/reviewers/`, `skills/goldfish-review/`, `skills/elephant-draft/`, `skills/drift-report/` |
| [[graphify-to-hades-map]] | `Graphify-Labs/graphify` — the nearest peer: local deterministic parsing, every edge explained, no vector store (engine refused, its edge-confidence and schema-versioning schemas adopted) | `scripts/link_check.py`, `scripts/candidate_check.py`, `scripts/health.py`, `rules/*.schema.json`, `ROADMAP.md` phase 44 |

Companion maps in the same folder: [[eight-memory-planes]] — one row per memory plane, with its
writer, its reader and the test that proves the store exists — and [[conversation-memory-path]],
which is not an upstream repo but the audit trail of this brain's own conversation-memory path
(charter §11): one row per step, the exact command, the refusal quoted from the code, and the test
that proves the refusal still fires, with an honest `NO_ROW` wherever the repo has no mechanism.

Two house rules shape this folder, and they disagree on purpose:

- **The maps carry backticked paths, never wiki links.** `scripts/install.py` ships
  `02_WIKI/reference_maps` into an installed home but not this `indexes/` folder, so a link written
  in a map would dangle in every home it lands in — and `link_check.py`, run there by
  `tests/test_phase16_host_independence.py`, would rightly refuse it.
- **This index is the reachable place.** It is never shipped, and every note it links is a tracked
  file in this repo, which is what makes those links safe here and nowhere else.
