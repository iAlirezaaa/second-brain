---
id: map-graphify-to-hades
type: resource
title: "graphify → HADES: what to adopt, what to refuse, and why"
status: evergreen
owner: agent
topics: [architecture, knowledge-management, gate, provenance, retrieval]
created: 2026-11-02
updated: 2026-11-02
---

# graphify → HADES map

Reverse-engineering note for [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify):
a tool that turns a codebase — with its docs, SQL schemas, configs and PDFs — into a queryable
knowledge graph. Its own pitch, quoted from that repo's README, is three rules this repo already
shares: **local deterministic parsing**, **every edge explained**, **no vector store**. Facts below
are its mechanics as inventoried from its README, `docs/how-it-works.md` and `ARCHITECTURE.md`
(measured 2026-11-02: Apache-2.0, Python, 140,699 stars, last push 2026-11-01, requires Python
3.10+ and `uv`/`pipx`). Nothing here installs from it.

It is the closest peer this brain has, and the most instructive, because it arrives at the same
place from the opposite direction: it builds a graph over a code tree, this repo *is* a graph over
a note tree. So the interesting question is not whether its engine fits — it plainly does not — but
which of its **schemas** survive once the engine is thrown away. All three below do.

## The verdict in one sentence

graphify's engine (tree-sitter grammars ×~40, NetworkX, graspologic/Leiden, an LLM semantic pass,
a cloud) is **refused**; its honesty about edges — a confidence tag on every relationship, an
ambiguous edge escalated to a human instead of kept quiet, a schema version stamped inside the
artifact, and a benchmark published with reproduction commands — is **adopted**, because that is
the same instinct `health.py` already encodes when it refuses a gate that reports `errors: 0` over
something it cannot see.

## Adoption table

| graphify concept | What it actually is there | Verdict in HADES | Where it lands here |
|---|---|---|---|
| tree-sitter AST extraction over ~40 languages | a compiled parser dependency per language | **refuse** — charter §3 forbids adding an unnecessary dependency, and §2 requires capabilities to live inside the project; this repo's "AST" is the wikilink graph, which is already explicit in the text | `scripts/link_check.py`, `scripts/kb.py` (stdlib `sqlite3` FTS5 only) |
| NetworkX + graspologic + Leiden community detection | third-party graph mathematics, optional extras | **refuse** — a `pip install` wall and a Python 3.10+ floor for a vault of a few hundred notes; degree and reachability are a dict and a BFS | `15_SYSTEM/config/system.json` keeps `requires-python = ">=3.9"` |
| LLM semantic pass over docs/PDFs/media, and Graphify Cloud | a model call (and a subscription) inside the indexing path | **refuse** — charter §2: swapping the model must not lose data or capability, so no inference is allowed to stand between an author and their own vault | `scripts/kb.py` indexes without a model; the write path has no LLM step at all |
| `graphify install` registering a skill into the assistant | the tool writes into the host's config | **refused as a mechanism, inverted here** — the brain never writes into a harness; each host gets a generated pointer it can delete | `scripts/sync_hosts.py`, `11_CONTROL/` |
| Edge confidence `EXTRACTED` / `INFERRED` / `AMBIGUOUS` (`docs/how-it-works.md` "Confidence tagging": `confidence` — `EXTRACTED`, `INFERRED`, or `AMBIGUOUS`) | who decided this edge exists | **adopted as a schema** — `extracted` (the author typed the wikilink), `inferred` (a gate or the indexer derived it), `ambiguous` (a candidate row) | ROADMAP Phase 44, edge-confidence row |
| "AMBIGUOUS — flagged in the report for manual review" | uncertainty is never silently trusted | **adopted, and it is already this repo's law** — an uncertain relation is a row on `14_CANDIDATES/` waiting for a human, not an edge in the graph | `scripts/candidate_check.py`, `scripts/promote.py` (`--approve` is the human door) |
| Discrete confidence rubric (0.95 / 0.85 / 0.75 / 0.65 / 0.55; `EXTRACTED` always 1.0) | a scale that cannot fake precision | **adopted as a principle** — this repo records *who wrote the edge*, not a float nobody calibrated; a five-point rubric without an eval set would be a made-up number | `02_WIKI/reference_maps/eight-memory-planes.md` (provenance per plane) |
| `also_seen` — keep the highest-confidence copy, list every other copy weakest-first | the same relation sighted twice is information, not a duplicate | **adopted for the candidate ledger** — a re-raised candidate accumulates evidence on one row instead of spawning a twin | `14_CANDIDATES/loop/*.jsonl` |
| `graph.schema_version` + `graph.graphify_version` stamped inside `graph.json` ("so integrations can detect incompatible format changes") | the file declares which contract wrote it | **adopted** — a generated JSON file that names its own schema version lets a gate refuse a stale file instead of mis-parsing it | ROADMAP Phase 44, `schema_version` row; `rules/*.schema.json` |
| God nodes ("the most-connected concepts") and Leiden communities with **LLM-free labels** | structural signals that say where the vault is thick and where it is split | **adopted without clustering** — degree-0 notes (unreachable by retrieval) and bridge notes (one link holding two clusters together) computed from the wikilinks already present | ROADMAP Phase 44, link-graph readout row → `scripts/health.py` |
| Path query ends with "the path's overall confidence: that of its weakest hop" | a chain is only as trustworthy as its worst link | **adopted as a rule for reports** — a review or drift report is graded by its least-settled finding, not its average | `scripts/goldfish_check.py` (an unsettled Blocker or Major makes the round dirty) |
| Rationale as a first-class node (`# NOTE:` / `# WHY:` comments, ADR/RFC citations linked to the code) | the *why* is a retrievable object, not a comment that rots | **already here, strengthened** — a lesson is a note with its own id, topic and provenance, so the reason survives the code that prompted it | `scripts/memory.py`, `15_SYSTEM/memory/lessons.jsonl` |
| Benchmarks published with the harness, the model, the budgets and reproduction commands, plus judge agreement (90.6%, Cohen's kappa 0.81) | a claim you can re-run | **adopted as the standard for any number this repo prints** — which is why `doc_report.py --check` refuses a hand-typed count | `scripts/doc_report.py`, `tests/test_installed_home.py` |
| Content-hash fingerprinting; unchanged files skip re-extraction | incremental, deterministic re-runs | **adopted, already present** — the fingerprint/state pattern gates rework on real change | `scripts/common.py` (`state_fingerprint`) |
| Hyperedges (a group relation over 3+ nodes) in `G.graph["hyperedges"]` | relations the pairwise graph cannot express | **refuse for now** — nothing in the vault needs a 3-node edge that a note plus its links cannot say; recorded so the refusal is deliberate, not an oversight | this map |
| `.graphifyrc` `language.inc=php`: without it a file "parses as the wrong language… the graph looks populated while the real symbols are missing" | the silent-failure mode, named by its own authors | **adopted as the argument for stated skips** — a gate that reads nothing still prints an `OK —` line, so a pass is never an absence | `scripts/health.py` docstring, `scripts/ci_floor.py`, `scripts/version.py` |
| "Always pass `root`… ids can end up carrying path segments from the machine they were extracted on" (`ARCHITECTURE.md`) | machine-local paths leaking into stable identifiers | **adopted as the reason for the citation rule** — every citation in this repo is repo-relative and must open in a fresh clone | `scripts/common.py` (`clone_readable`), `scripts/goldfish_check.py` |

## What transfers, and why the schemas survive without the engine

The engine and the schemas are separable because each schema is a statement about **provenance**,
not about parsing:

- a confidence tag answers "who asserted this edge?" — answerable for a wikilink by reading the
  file, no parser needed;
- a schema version answers "which contract wrote this file?" — one key in JSON;
- degree answers "can retrieval reach this note at all?" — a link count;
- the weakest-hop rule answers "how far can I trust this chain?" — a `max()` over severities.

All four are decisions about what the repo is willing to claim, which is exactly the material
`14_CANDIDATES/` and `15_SYSTEM/memory/lessons.jsonl` are already made of. None of them needs a
dependency, a port, a key or a model.

## Where each adopted piece lands (script + test)

| piece | script | data | test |
|---|---|---|---|
| edge confidence on the link graph | `scripts/link_check.py` (assertion source per edge) | `14_CANDIDATES/` for `ambiguous` | the phase-44 tests added with the ROADMAP rows |
| link-graph readout | `scripts/health.py` (one row per gate) | the vault's own wikilinks | `tests/test_phase16_host_independence.py` counts the `OK` lines, so a new row must print one |
| `schema_version` in generated JSON | the writer in `scripts/memory.py`, `15_SYSTEM/scripts/hades.py` | `rules/*.schema.json` | the gate that refuses a file whose stamp is absent or stale |
| the citation rule | `scripts/common.py` (`clone_readable`) | — | `tests/test_phase43_goldfish_method.py` (a citation naming a file a clone cannot open is refused) |

## Not a fourth charter reference

`00_START_HERE/PROJECT_CHARTER.md` §3 names three reference repos; graphify is **not** one of them.
It entered on the owner's brief of this run ("also check the other repos and see what they do"), the
same way `google/elephant-goldfish-model` did, and it is surveyed in `ROADMAP.md` Phase 44 rather
than promoted to a charter §3 source. `02_WIKI/indexes/reference-maps.md` carries the row.

## Final folder structure — answer

Nothing new: one note, no new zone, no new dependency.

```
02_WIKI/reference_maps/  + this map
ROADMAP.md               phase 44 surveyed line and four rows (three adopted, one refused)
02_WIKI/indexes/         + the row in reference-maps.md
```

`scripts/*`, `rules/*`, `15_SYSTEM/*` and `vault-template/*` are untouched by this map: a map is the
standing answer to "what did we take and what did we refuse", and the code that takes it is the
phase-44 work it describes.
