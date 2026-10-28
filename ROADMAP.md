# ROADMAP — iAlirezaaa/second-brain (HADES OS v3)

A standalone, self-improving agentic operating system: a plain-markdown brain with a gated
registry, persistent memory, and its own improvement loop — stdlib-only Python, no app, no
network, no paid service. **This file is a public promise:** every idea lands here with a size
estimate, gets built test-first, and is ticked continuously by the repo's own engineers
(human + agents + nightly loop). The owner's brief — `00_START_HERE/PROJECT_CHARTER.md` —
outranks this file: phases here *implement* the charter, and a conflict is filed on
`14_CANDIDATES/loop/` with the section number, never resolved silently.

**Status chips:** 🟢 done · 🟡 in progress · 🔵 planned · ⛔ refused (with the reason kept)
**Sizes:** S = one script/gate, M = script + tests + doc surface, L = subsystem
**Sources:** each phase cites where the idea came from (competitive insight, not cargo-cult).

Golden rules (tested, not aspirational): zero broken links · fenced zones · nothing is ingested
until it is linked · contradictions are recorded, never overwritten · every feature ships with a
test before the next starts · evidence survives a `git clone` · a gate that reports `errors: 0`
over something it cannot see is a silent gate, not a clean house.

---

## Shipped history (compressed)

Phases 0–8 (vault template, integrity toolchain, inbox triage + write gate, FTS5 keyword KB,
rituals, CI, continuous-improvement loop, public project standard + the HANDOFF machine) and
phases 12–24 (repo memory ledger, host independence with `AGENTS.md` as single canon, the
control-plane registry, measured documents, evidence-survives-a-clone, `keep_base`/`--recover`,
the registry laws: `set` amendments, `supersedes` retirement, content enumeration, one file one
contract, the MCP harness door, agent runs in the disposable plane, and the SuperAGI backend
package) are done — every row test-gated, the full trail in `CHANGELOG.md` and the git log.
Phase 8 established the public project standard and handoff. Phases 31–34 add the private
source memory the charter's §5 asks for: explicit import, a rebuildable index, provenance,
evidence-backed lessons, retrieval measurement, transfer between devices, and a
capability catalogue that never installs without approval.
Current floor, measured at the time of writing: **333 unittests, a 120-check HADES battery,
6 health gates, CI on ubuntu+windows × 3.9/3.12, 26 recorded lessons.**

---

## Phase 25 — The charter audit: the yardstick measured · 🟢

*Source: the charter itself (§15: the order of work) and the handoff's own admission that the
charter "has not been audited against the repo yet". A charter nobody has measured against is
decoration. Audit: `00_START_HERE/CHARTER_AUDIT.md` — 11/15 honoured, 3 partial, 1 gap.*

- [x] **S** Walk `00_START_HERE/PROJECT_CHARTER.md` §1–§15 section by section; for each, run or
      name the command that shows whether the repo honours it today. Output: the audit table in
      `00_START_HERE/CHARTER_AUDIT.md`, every row carrying evidence (command + output), `NO_ENTRY`
      where a section is unimplemented.
- [x] **S** File every gap as a GitHub issue with the section number and the proving command —
      #20 (§5/§11 memory planes), #21 (§7 manager agent), #22 (§3 reference maps); the open
      §8 backlog (#15–#17) named in the audit.
- [x] **S** Amend this roadmap from the audit's verdicts: phases 26–27 implement the §5/§11
      verdicts, ⛔ rows carry the refusals with the section number that justifies them.

## Phase 26 — The eight memory planes, mapped and gated · 🔵

*Source: charter §5 (project, repository, agent, task, error, decision, knowledge, conversation
memory — "each memory type is stored in a specific place and is accessible to the agent").*

- [ ] **S** Write the mapping: which existing store holds which plane (projects → `03_*` records,
      agents → `11_CONTROL` + backend actor registry, errors → `lessons.jsonl`, decisions →
      `02_WIKI/decisions/`, knowledge → `kb.py` + wiki, task/runs → `runs.py` ledger,
      conversation → promoted rows, repository → HANDOFF/CHANGELOG). The mapping is a doc row
      with evidence, not a claim.
- [ ] **M** Close the real gaps the mapping exposes — the honest expectation: conversation
      memory has no reader surface and `kb.py` covers the template, not the repo corpus. Each
      gap becomes an issue first, then a test-first fix.
- [ ] **S** A health gate that fails when a memory plane's store is missing or unreadable — so
      the charter's §5 is enforced by a gate, not remembered by the next agent.

## Phase 27 — The brain searches its own corpus · 🔵

*Source: charter §1 (the system must manage its own information) — today `kb.py` ingests the
*vault-template*, while the tracked prose it should index lives beside it.*

- [ ] **M** Point `kb.py` at the tracked repo (human plane only; machine plane excluded by the
      same boundary `common.clone_readable()` declares) with the existing golden-set gate as the
      regression harness.
- [ ] **S** Decide, with a measurement first, how retired records surface in `search`/`list`
      (handoff §4: the index is settled, the reading surface is not).
- [ ] **S** BM25 recency boost behind a measured eval — only if the golden set shows it wins.

## Phase 28 — Scheduler seam: one clock for the rituals · 🔵

*Source: charter §6 (continuous improvement cycle) + the backend's pure `schedules.is_due`
math — two clocks exist (nightly loop + backend schedules); one should tell the truth.*

- [ ] **S** `scripts/loop.py` (and the weekly ritual skill) read their due-date from
      `backend/schedules.is_due` — pure math, no new dependency, one definition of "due".
- [ ] **S** The loop's cadence lands as a `schedule` record in the registry, so the
      improvement cycle itself is a governed definition, not a cron comment.

## Phase 29 — Semantic layer, only behind a flag and only with evidence · ⛔ today

*Source: charter §1's smarter-over-time promise vs. the standing owner decision.*

- [ ] **S** behind `vector_search: false`: an optional embedding seam (interface + a
      deterministic test double) so the day it is enabled it plugs into the same gates.
      **Refused by default:** no embedder dependency, no network call, no activation without a
      golden-set eval that beats BM25 and the owner's explicit approval (charter §2).

## Phase 30 — Registry hardening leftovers · 🔵

*Source: the unification merges that shipped phases 21–24 — the leftovers are named in the
handoff, not invented here.*

- [ ] **S** `link` goes through the plan door: an edge that retires a record is a structural
      change and should be reviewable like one (today it writes through, gated but unreviewed).
- [ ] **S** `supersedes` cycle guard: A superseding B while B supersedes A currently retires
      both silently — the single `superseded_by` map makes a cycle unrepresentable instead of
      detected; `doctor` should error on a cycle the way it errors on self-supersession.
- [ ] **M** per-kind status vocabularies: 20 of 33 kinds fall back to
      `draft|tested|approved|deprecated` — decide each kind's set, then let the gates enforce
      what is written.
- [ ] **S** recovery on the probe's own initiative stays refused unless the owner grants the
      permission explicitly — reverting a tree from an unattended measurement is a bigger
      permission than naming one.

## Phase 31 — Private source memory with provenance · 🟢

*Source: charter §5 (knowledge and conversation memory must be stored and accessible) and the
owner's brief: keep what was produced and researched, retrieve it with its source, and keep
raw data separate from extracted knowledge. The store is local and explicit — nothing is
scanned or fetched on its own.*

- [x] **M** `15_SYSTEM/scripts/backend/sources.py`: explicit import of one selected UTF-8
      file (or validated bytes) into `.brain-data/sources/<id>/{raw.txt,metadata.json}`; the
      id is the sha256 of kind + origin + content, so re-importing the same bytes and origin
      is idempotent and changed content is a new record. Metadata records kind, origin,
      original filename, import time, format and checksum. The raw bytes stay authoritative.
- [x] **M** A rebuildable SQLite index (`rebuild`) with word-frequency tables and a
      BM25-style ranking that keeps a slower text-scan path for older indexes; every rebuild
      validates every record first and leaves the previous index in place on refusal.
      `search` returns kind, origin, filename and import time with every hit.
- [x] **M** Harness conversation adapters (`codex-jsonl`, `claude-stream-json`,
      `cursor-stream-json`) that index only user/assistant text, refuse mixed sessions and
      keep the selected raw JSONL. No automatic session discovery.
- [x] **S** Declared import path: `sources.py import|rebuild|search|batch` and the MCP
      tools `source_search` + `lesson_propose`/`lesson_recall`; a manifest is previewed with a
      content-bound `plan_id` before `--apply`. Batch never scans folders.
- [x] **S** Tests: `tests/test_sources.py` (round-trip, duplicates, corrupt/interrupted
      records, BOM/CRLF preservation, adapter projections, CLI), `tests/test_batch.py`
      (stale plan, all-or-nothing preview, partial-failure reporting).

## Phase 32 — Transfer between devices with conflicts named · 🟢

*Source: charter §5 + the owner's brief: multi-device use, conflict detection, backups and
sensitive-data control. The chosen mechanism is an explicit folder transfer with a preview;
a sync service is refused until a measurement justifies one.*

- [x] **S** `source_sync.transfer`: preview first; copies only complete, validated records;
      reports new / already-present / conflicts; a conflict is a second content with the same
      kind and origin and is copied only with `--allow-conflicts`, both versions kept.
- [x] **S** Approval receipts are local decisions: they are previewed but imported only with
      `--include-approvals`, and a receipt without its proposal is refused.
- [x] **S** `verify-copy` compares every source, proposal and approval byte-for-byte and
      returns nonzero on a missing or changed record; extras are allowed.
- [x] **S** Sensitive-data boundary: `.brain-data/` is gitignored and behind the clone
      boundary, the docs state it is not encrypted or backed up, and the default tool read
      scope refuses `.env`, key/credential filenames, `.git`, `secrets` and the runtime,
      lab, candidate, backup and client-metadata zones (`backend/access.py`).
- [x] **S** Tests: `tests/test_source_sync.py` (idempotency, conflict preview, corruption
      before copy, missing source, hidden incomplete record, approval import, invalid
      proposal/receipt), `tests/test_access_boundary.py` (search and resource reads, symlink
      aliasing, credential paths).

## Phase 33 — Evidence-backed lessons and measured retrieval · 🟢

*Source: charter §6/§11 (learn from what happened, keep the evidence, improve with a
measurement) and the owner's brief: lessons from permitted data, retrieval quality before
and after a change, rollback available.*

- [x] **M** `backend/learning.py`: a proposal must cite an imported source id and an exact
      quote that is present in the source; the id is a digest of the content, so a modified
      proposal is refused. `evaluate` re-checks the source checksum and quote and whether the
      chosen query retrieves that source. `approve` requires `--approve`, re-evaluates and
      writes a receipt. `recall` returns only approved lessons with their source and origin.
- [x] **S** The evaluation states its limit out loud: it does not establish that a lesson is
      true, useful or improves performance. Extraction stays a human/agent interpretation,
      not an asserted fact.
- [x] **M** `backend/retrieval_eval.py` + `tests/fixtures/retrieval-golden.json`: mean
      recall and MRR on an independently curated case set; both reports must share the case
      set, limit and corpus hash; any regression in either metric fails the comparison.
- [x] **S** Tests: `tests/test_learning.py` (source→proposal→evaluation→approval→recall,
      bad evidence, changed record, tampered proposal, CLI approval), `tests/test_retrieval_golden.py`.

## Phase 34 — Capability catalogue and approval-gated install · 🟢

*Source: charter §7 (register roles and abilities) and the owner's brief: a catalogue of
skills, plugins and tools with compatibility, origin and permissions, a suggestion per
session, and installation only after approval.*

- [x] **S** `15_SYSTEM/scripts/capabilities.py` + `backend/capabilities.py`: inventory of
      active registry skills, plugins, MCP records, extensions and built-in tools with
      origin, permissions, approval list and installation state; `--task` returns keyword
      matches, `--harness-id` reports `approved` / `not_approved` / `unknown`. Retired and
      deprecated records are excluded. The MCP tool `capabilities` exposes the same read-only view.
- [x] **M** `backend/install_skill.py` + `15_SYSTEM/scripts/install_skill.py`: plan → apply
      → never replace. The plan binds skill id, harness, destination, file digests and a
      `plan_id`; apply requires `--approve`, refuses a stale or modified plan, writes only
      into a new directory, and leaves `.install-incomplete` on a partial write.
- [x] **S** Tests: `tests/test_capabilities.py` (registry + built-in inventory, suggestions,
      retired records, CLI/MCP), `tests/test_install_skill.py` (review required, no
      replacement, stale source, unapproved record, visible incomplete install).

## Distribution & scale (parked) · ⛔/🔵

- [ ] 🔵 multi-host installer flags (`--host codex|opencode|gemini|claude`) — one skill tree,
      many agents; only after a second harness actually asks for it.
- [ ] ⛔ HTTP/server layer: refused while MCP-over-stdio answers every harness that exists —
      a port, a daemon and a key surface are the SuperAGI stack this repo exists to not need
      (charter §2). Revisit only with a named consumer.
- [ ] ⛔ GitHub Pages docs site: content is the bottleneck, not tooling; the README is the site.
