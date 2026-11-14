# ROADMAP — iAlirezaaa/second-brain-os (Second Brain OS; engine codename HADES v3)

A standalone, self-improving agentic operating system: a plain-markdown brain with a gated
registry, persistent memory, and its own improvement loop. The stack it runs on today is
stdlib-only Python, no app, no network, no paid service — and that is a **revisable executive
law**, not an eternal one: `00_START_HERE/CONSTITUTION.md` keeps stdlib-only as the safe default
and unlocks a dependency, an HTTP API, a local server or a vector index only through six
conditions (a named problem, a measured baseline, a before/after win with repeat counts, a cost
and risk review, a bounded blast radius with a stdlib fallback and the flag still false, and a
decision record in `09_OPERATIONS/decisions/`). A refusal in this file is therefore about
*absence of evidence*, never about size.
**This file is a public promise:** every idea lands here with a size estimate, gets built
test-first, and is ticked continuously by the repo's own engineers (human + agents + nightly
loop). The precedence ladder is the constitution, then the owner's brief
`00_START_HERE/PROJECT_CHARTER.md`, then the executive-law register, then this file and the code:
phases here *implement* the constitution, and a conflict is filed on `14_CANDIDATES/loop/` with
the section number, never resolved silently.

**Status chips:** 🟢 done · 🟡 in progress · 🔵 planned · ⛔ refused (with the reason kept)
**Sizes:** S = one script/gate, M = script + tests + doc surface, L = subsystem
**Sources:** each phase cites where the idea came from (competitive insight, not cargo-cult).

Golden rules (tested, not aspirational): zero broken links · fenced zones · nothing is ingested
until it is linked · contradictions are recorded, never overwritten · every feature ships with a
test before the next starts · evidence survives a `git clone` · a gate that reports `errors: 0`
over something it cannot see is a silent gate, not a clean house.

---

## P1 — Claude Code CLI temporary MCP config (issue #106; stacked PR pending)

- [ ] **S** Generate `--client claude-code` JSON in the explicit
      `mcpServers.second-brain` stdio shape for `claude --mcp-config FILE`,
      retaining absolute checkout/interpreter paths and the security boundary
      of #104. No host settings writes or permissions are granted.
- [ ] Extend the existing synthetic host config regression for Unicode paths,
      missing/symlinked server refusals, and unchanged other host formats.
      Document a targeted read-tool smoke (not a read-only guarantee).
- [ ] **Merge gate:** installed-host handshake is a separate compatibility test;
      this snippet needs seven green CI jobs and current branch-protection
      requirements, currently blocked by obsolete Ubuntu contexts (#107).

**Next 1:** version-pinned installed Claude Code/Codex/OpenCode handshake with
synthetic source-cited recall and explicit host write-denial checks.
**Next 2:** ADR for opt-in reversible registration with backups, explicit
consent, conflict detection and tested rollback.

---

## P0 — Reject escaped MCP server paths in host snippets (issue #104; PR review pending)

- [ ] **S** Refuse both final-file symlinks and **symlinked ancestor directories**
      under the resolved checkout root in `scripts/mcp_config.py`. Also refuse
      a resolved server outside the checkout (including Windows reparse-point
      escapes). Synthetic reproduction on Linux, 2026-11-14: the old guard
      accepts an external target when `15_SYSTEM/scripts` is a symlink, even
      though `mcp_server.py` itself is a regular file.
- [ ] Extend the existing host-config symlink regression (no inflated test
      count) for all three clients. Preserve normal paths, Unicode, and the
      guarantee that the generator never edits host settings.
- [ ] **Merge gate:** CI must pass Ubuntu/Windows Python 3.9/3.12 plus three
      backup jobs. A local-path check is not installed-host verification.

**Next 1:** version-pinned Codex/Claude/OpenCode synthetic host handshake and
explicit write-permission review.
**Next 2:** ADR for opt-in reversible host registration (consent, backups,
conflict detection and rollback), without automatic changes to user settings.

---

## P1 — Safe Codex CLI local MCP snippet (issue #102; verified in PR #103)

- [x] **S** Generate a stdlib-only TOML `[mcp_servers.second-brain]` entry
      with absolute interpreter/server paths and `enabled = false`. Windows
      and supplementary Unicode paths are escaped correctly; no installed
      Codex compatibility has been asserted.
- [x] Existing host-config regression checks Codex, missing/symlinked
      files, nonmutation and Windows/Persian paths; English/Persian
      onboarding was updated with manual-merge limitations.
- [x] Test-only TOML escape-case regression repaired after CI
      #43537155432; full 7/7 CI passed in #43549027077. PR #103 merged
      as `bb5e8f68df1ef5427a26c055c6f5cd7965b4da90`.
      This proves output shape and gates, **not** a real installed client.

**Next 1:** installed Codex local-client synthetic handshake with version and
permissions recorded.
**Next 2:** proposal/ADR for explicit-consent reversible host registration.

---

## P1 — Native OpenCode V2 MCP registration (issue #100; verified in PR #101)

- [x] **S** Match the first-party OpenCode V2 config contract:
      `mcp.servers.second-brain` with `type: local`, an absolute command
      and `disabled: true` pending human inspection of existing write tools.
      The previous V1 `mcp.second-brain` and `enabled: true` output
      did not use the *native* V2 schema (observed 2026-11-13 at
      https://opencode.ai/docs/mcp-servers). The official
      https://opencode.ai/docs/migrate-v1 explicitly says V2 still accepts
      supported V1 configurations for migration. **No prior connection
      failure has been reproduced or claimed.**
- [x] Make the generated snippet, placeholder example, regression assertions
      and English/Persian onboarding docs agree; preserve Claude Desktop behavior
      and all refusal tests. No host configuration is mutated.
- [x] Seven jobs completed successfully in CI #43522910025; PR #101 merged
      as `78dc28f4d7b873159c4f431cd553fb0e1ccb0a83`. Full Ubuntu/Windows
      Python 3.9/3.12 health/unit-test matrix and backup jobs verified. This is **schema compliance only**:
      installed OpenCode and its permissions have not been independently tested.

**Next 1:** test a real version-pinned OpenCode V2 handshake on a disposable
synthetic note before claiming host compatibility.
**Next 2:** build an explicit opt-in, reversible setup flow (proposal/ADR,
user confirmation, existing-config backup and verified rollback).

---

## P1 — Portable MCP host registration and offline stdio check (#96, #98)

- [x] **M** Generate portable, machine-local Claude Desktop/OpenCode JSON with
      `scripts/mcp_config.py`, without changing host settings or permission grants.
      All 7 CI jobs passed on the updated branch (run #43486609444);
      PR #97 merged as `674afe63ae688822e790f9925d72ac89db5d9a9a`;
      issue #96 closed. Configuration generation alone does not connect a host.
- [x] **S** Add `scripts/mcp_smoke.py`: with a synthetic `02_WIKI` note
      inside a disposable root, launch the **real** MCP server over stdio and
      check JSON-RPC initialize, tagged tool discovery, a provenance-bearing
      `vault_search` result and strict-session refusal of
      `candidate_propose` without session metadata. Require no candidate shelf
      and JSON-only exit status. Regression: `tests/test_mcp_smoke.py`
      (2 tests; issue #98; PR #99 merged after seven green CI jobs in
      run #43507137025).
- [x] `python scripts/health.py`, full Python 3.9/3.12 Windows/Ubuntu
      matrix and cross-host backup CI passed in run #43507137025; PR #99
      merged as `0f6ed4290b494505437909e4740849d54e295527`.
      The probe does not certify third-party host integrations or OS-backed
      access control.

**Next 1:** verify actual Claude Code/Codex/OpenCode connections with
explicit version/permission gates, synthetic fixtures and per-host approvals.
**Next 2:** write a separate ADR and rollback-tested plan for opt-in,
reversible host registration that preserves existing configs.


---

## P0 — Portable Python entrypoints (issue #46; CI #280 green, PR #95 merged)

- [x] **S** Replace the stale `py -3.10` Windows command pin in the public
      first-session guide, `AGENTS.md`, rendered agent-host entrypoints and the
      Persian `00_START_HERE/START.md`. Test portability with
      `tests/test_portable_python_entrypoints.py` and keep generated hosts in
      sync. The supported floor remains Python 3.9, verified by the OS CI matrix.
- [x] Verified this focused onboarding slice across seven Linux/Windows CI jobs
      in run #280 and merged PR #95. Issue #46 stays **open**: older project-internal documents
      may still carry hardcoded interpreter commands; they need their own scoped
      audit and an inventory before closure.

**Next 1:** finish #46 by inventorying all remaining version-pinned Markdown
and updating supported examples without rewriting historical evidence.
**Next 2:** verify a provenance-preserving, explicitly read-only MCP quickstart
with a denied-write fixture and no added runtime permissions.

---

## P0 — Reproducible offline first-recall smoke metrics (issue #93; PR #94 merged)

- [x] **S** Add `scripts/first_success.py` with an independent disposable synthetic
      note fixture per trial, real CLI ingest/search, machine-readable success and latency,
      a bounded repeat count and a nonzero failure exit; guard with
      `tests/test_first_success_probe.py` (four regressions; merged PR #94).
- [x] Verified on Python 3.9/3.12 Ubuntu/Windows CI before PR #94 merged.
      The measurement excludes clone/setup and is **not** an end-to-end five-minute
      UX test or semantic-memory benchmark; do not claim these from synthetic timings.

**Next 1:** time the complete clean-clone + first search procedure separately
on real supported platforms with a published fixture and environment details.
**Next 2:** add a minimal provenance-aware MCP client example that demonstrates
safe read and an explicitly denied write, without changing permission defaults.

---

## P0 — Local KB alias boundary (issue #90; merged PR #91; CI #275 verified)

- [x] **S** Ignore symlinked Markdown, symlinked parent directories and
      broken links during KB indexing; never mistake an out-of-root target for
      a clone-readable local note. Implementation: `scripts/kb.py`;
      synthetic coverage: `tests/test_kb_corpus_symlink_boundary.py`.
- [x] Ran health and the complete OS/Python matrix; merged #91, closed #90,
      and document that pre-existing indexes need a fresh
      `python scripts/kb.py ingest` to discard formerly indexed aliases.
      This is not a TOCTOU-safe filesystem sandbox or a blanket security claim.

**Next 1:** validate a real five-minute clean-clone recall path and record
wall time with the same fixed fixture (no fabricated benchmark).
**Next 2:** use the local-first MCP client's existing read-only tools for a
small, deterministic demonstration with explicit provenance and denials.

---

## P0 — CI time-invariant test gates (issue #88; verified on CI #270; merged in #89)

- [ ] **S** Phase 44 validity-window fixtures: replace the frozen test epoch in
      `tests/test_phase44_lesson_validity_windows.py` with the runner's calendar day.
      The failing baseline is [CI run 43397264607](https://github.com/iAlirezaaa/second-brain-os/actions/runs/43397264607):
      four failed OS/Python jobs; two phase-44 failures come from 2026-11-02
      fixtures expiring on 2026-11-06. This patch does not change the runtime
      clock, permissions, memory ledger, or stale-memory refusal.
- [ ] Verify across Python 3.9/3.12 and Ubuntu/Windows, then merge only if
      `python scripts/health.py`, the unittest suite and the clean-clone checks pass.
      PR #87 regression was corrected on its branch; this track still needs onboarding CI/merge.

**Next 1:** repair the independent regression in PR #87 and rerun its CI.
**Next 2:** capture a reproducible under-five-minute offline recall journey
from a clean clone and measure search success and time without fabricated results.

---
## Product adoption and discoverability track (planned, evidence-gated)

**North-star:** independent users can install, recall a useful sourced note,
understand the privacy boundary and safely connect an AI host in minutes. Organic
stars are a *lagging signal*, never a substitute for usability or verified quality.
The plan below does not claim shipped features.

- [ ] **P0 — Five-minute first success:** repair onboarding, keep an offline first-recall
      walkthrough in `README.md` and `skills/first-session/SKILL.md`, and verify it in
      `tests/test_first_session_onboarding.py` (issue #86; merged PR #87 after green CI).
- [ ] **P0 — Trust first:** finish high-impact bugs in the open issue ledger and CI;
      require a reproducible clean-clone pass on Windows and Ubuntu before promotion.
- [ ] **P1 — One-click-ish host setup:** independently test an opt-in, reversible
      setup path for Claude Code, Codex and OpenCode; no silent permissions.
- [ ] **P1 — Show, don't promise:** add a short reproducible demonstration,
      offline setup comparison, clear source provenance and measured retrieval examples.
- [ ] **P1 — Distribution:** refresh repository topics and social preview, publish
      trustworthy release notes, provide contributor-friendly issues, and engage relevant
      communities without spam, paid/automated stars or fabricated benchmarks.
- [ ] **P2 — Optional local interface:** plan a low-dependency read-only dashboard for
      memory, sources, agent runs and permission denials; keep CLI and Markdown usable.
- [ ] **P2 — Competitor-informed evaluation:** benchmark graph/entity retrieval,
      time-aware recall, source-backed search and agent memory blocks against a frozen
      local baseline before adding implementations; retain the stdlib offline fallback.

**Next two slices after onboarding:** (1) audit a CI/health refusal with an
independently reproducible test; (2) build a disposable, documented five-minute
MCP client integration and ensure the permission gate refuses unsafe writes.

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
The current floor is measured, not typed: the table in `README.md` (regenerated by
`scripts/doc_report.py --write`, gated by `scripts/health.py`) carries the test count, the
HADES battery and the lesson ledger, and CI runs the suite on ubuntu + windows across the
supported Python versions.

The owner's five-phase brief — audit → knowledge core → harnesses and sync → learning →
ecosystem — is the arc phases 25–35 implement. `00_START_HERE/PLAN_FA.md` (Persian) maps every
requirement of that brief to the command that proves it and names the gaps; the only item that
is still **planned rather than shipped** is the fine-tuning pipeline in phase 36 below.

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

## Phase 26 — The eight memory planes, mapped and gated · 🟢

*Source: charter §5 (project, repository, agent, task, error, decision, knowledge, conversation
memory — "each memory type is stored in a specific place and is accessible to the agent").
Shipped: `15_SYSTEM/config/system.json` → `memory_planes` (tracked store, disposable store,
reader, test and map per plane), `02_WIKI/reference_maps/eight-memory-planes.md` (one row per
plane, measured inventory, provenance description) and `scripts/plane_check.py`, a seventh
health gate that refuses a dropped plane, a missing tracked store, an empty folder or a
reader/test/map that no longer exists. Proved by `tests/test_phase26_memory_planes.py` — nine
tests, five of which break a fixture on purpose and read the gate's refusal.*

- [x] **S** Write the mapping: which existing store holds which plane (projects → `03_*` records,
      agents → `11_CONTROL` + backend actor registry, errors → `lessons.jsonl`, decisions →
      `02_WIKI/decisions/`, knowledge → `kb.py` + wiki, task/runs → `runs.py` ledger,
      conversation → promoted rows, repository → HANDOFF/CHANGELOG). The mapping is a doc row
      with evidence, not a claim.
- [x] **M** Close the real gaps the mapping exposes — the honest expectation: conversation
      memory has no reader surface and `kb.py` covers the template, not the repo corpus. Each
      gap becomes an issue first, then a test-first fix. Filed instead of half-built: #20 keeps
      the conversation extraction path and `kb.py` (phase 27); #24 contradiction awareness (no
      measured definition yet); #25 lessons carry no plane field.
- [x] **S** A health gate that fails when a memory plane's store is missing or unreadable — so
      the charter's §5 is enforced by a gate, not remembered by the next agent.

## Phase 27 — The brain searches its own corpus · 🟢

*Source: charter §1 (the system must manage its own information) — `kb.py` used to ingest the
*vault-template*, while the tracked prose it should index lived beside it. Shipped: the index
now covers the clone-readable human plane (43 notes here, 28 in an installed home), excludes
the machine plane, template, dot-folders and agent doors by `common.clone_readable()`'s own
boundary, strips frontmatter before indexing, keeps raw text for snippets while matching on
folded text, and refuses a missing or stale index instead of answering from it. Retirement
now has a visible surface: `list` counts active/retired and marks the retired row,
`search` marks the retired record's own file, `show` names who retired it, and the MCP door
carries `superseded_by`. Measured before the change: 4 list rows / 1 retired / 0 markers;
5 search hits / 1 on the retired file / 0 markers. The last item was measured and refused:
3 of 43 notes declare `updated:` and the other 40 fall back to mtime — one distinct day (the
checkout) in any clone — so a recency term had no signal; a recency-aware re-rank moved
recall@1 / MRR by 0.000 at every weight from 0.05 to 1.0.*

- [x] **M** Point `kb.py` at the tracked repo (human plane only; machine plane excluded by the
      same boundary `common.clone_readable()` declares) with the existing golden-set gate as the
      regression harness. The phase-4 gate is repointed; `tests/test_phase27_repo_corpus.py`
      proves the boundary, the installed home and the shared golden fixture.
- [x] **S** Decide, with a measurement first, how retired records surface in `search`/`list`
      (handoff §4: the index is settled, the reading surface is not). Measured, then marked on
      `list`, `search` and `show`; four tests cover the three CLI surfaces and the MCP door.
- [x] **S** BM25 recency boost behind a measured eval — only if the golden set shows it wins.
      Measured first, then refused: date coverage 3/43 explicit (40 notes share one fallback
      date), golden recall@1 1.000 / MRR 1.000 unchanged at alpha 0.05–1.0. Nothing was ranked
      by date; `tests/test_phase27_repo_corpus.py` pins relevance-over-recency, and the two
      conditions for revisiting sit in handoff §4. Measuring it also exposed the phase-4 gate:
      four of its five cases were near-ties, re-picked by margin with a 0.5 floor.

## Phase 28 — Scheduler seam: one clock for the rituals · 🟢

*Source: charter §6 (continuous improvement cycle) + the backend's pure `schedules.is_due`
math — two clocks exist (nightly loop + backend schedules); one should tell the truth.*

- [x] **S** `scripts/loop.py --due` imports `15_SYSTEM/scripts/backend/schedules.py::is_due` instead of re-deriving
      it; exit 0 = due, 3 = not due, 1 = refused (no record, paused, unreadable spec), and the
      check writes nothing. The weekly ritual skill asks the same function first.
- [x] **S** The loop's cadence is a governed definition: `SCH-0D1E2F3A` (kind `schedule`,
      `{"daily_at": "02:00"}` UTC, target `scripts/loop.py`), with `SCH-0D1E2F3B`
      (`{"every_minutes": 10080}`) governing the weekly ritual. The Actions cron is the alarm;
      the record is the rule. `tests/test_phase28_schedule_seam.py` adds 14 tests (373 total).

## Phase 29 — Semantic layer, only behind a flag and only with evidence · 🟢 seam shipped, ⛔ activation

*Source: charter §1's smarter-over-time promise vs. the standing owner decision.*

- [x] **S** behind `vector_search: false`: `15_SYSTEM/scripts/backend/vector.py` ships one `Embedder`
      interface, `cosine`/`rank` as pure functions, and `HashingEmbedder` — a sha256
      bag-of-words double, deterministic across processes, with `production = False`.
      `scripts/vector.py status|probe` shows the seam running offline; `scripts/vector_check.py`
      is the eighth health gate. `11_CONTROL/vector/activation.json` is the evidence door
      (verdict, BM25/candidate rates, positive margin, ≥5 cases with a case-set digest,
      approver and date). **Refused by default:** no embedder dependency, no socket, and
      activation stays shut even with perfect evidence while no production embedder is
      registered. 22 tests in `tests/test_phase29_vector_seam.py` (395 total).

## Phase 30 — Registry hardening leftovers · 🟢

*Source: the unification merges that shipped phases 21–24 — the leftovers are named in the
handoff, not invented here. Shipped on `phase-30-registry-hardening` in four commits
(`b9563ac`, `710dd20`, `bf65c1e`, `4a5f094`) with 19 new tests in
`tests/test_phase30_registry_hardening.py`.*

- [x] **S** `link` goes through the plan door: a `supersedes` edge retires its target, so it
      now writes a `mode: link` plan with the record's `pre_image_sha1`, waits for
      `apply --plan … --approve`, refuses a changed file and records the amendment. Additive
      relations still write through — `depends-on` never removes a record from the index.
- [x] **S** `supersedes` cycle guard: `doctor` walks the relation as a directed graph and
      errors on each cycle (`A -> B -> A`), with self-edges left to the self-supersession
      check and dangling targets left alone. The walk is read-only; it does not model a cycle
      as a legal state.
- [x] **M** per-kind status vocabularies: all 34 kinds in `system.json` now own a status set
      (20 sets added; 20 of the 34 kinds used to fall back to `default`). `default` remains
      only for a kind added without one, and `GUIDE_FA_EN.md` lists every set in both
      languages.
- [x] **S** recovery on the probe's own initiative stays refused unless the owner grants the
      permission explicitly — `scripts/probe.py` refuses `scripts/base.py` (recovery is the
      owner's decision) and `scripts/install.py` (writes outside the repo) by name.

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
      tools `source_import` + `source_search` + `lesson_propose`/`lesson_recall`; a manifest is
      previewed with a content-bound `plan_id` before `--apply`. Batch never scans folders.
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
      lab, candidate, backup and client-metadata zones (`15_SYSTEM/scripts/backend/access.py`).
- [x] **S** Tests: `tests/test_source_sync.py` (idempotency, conflict preview, corruption
      before copy, missing source, hidden incomplete record, approval import, invalid
      proposal/receipt), `tests/test_access_boundary.py` (search and resource reads, symlink
      aliasing, credential paths).

## Phase 33 — Evidence-backed lessons and measured retrieval · 🟢

*Source: charter §6/§11 (learn from what happened, keep the evidence, improve with a
measurement) and the owner's brief: lessons from permitted data, retrieval quality before
and after a change, rollback available.*

- [x] **M** `15_SYSTEM/scripts/backend/learning.py`: a proposal must cite an imported source id and an exact
      quote that is present in the source; the id is a digest of the content, so a modified
      proposal is refused. `evaluate` re-checks the source checksum and quote and whether the
      chosen query retrieves that source. `approve` requires `--approve`, re-evaluates and
      writes a receipt. `recall` returns only approved lessons with their source and origin.
- [x] **S** The evaluation states its limit out loud: it does not establish that a lesson is
      true, useful or improves performance. Extraction stays a human/agent interpretation,
      not an asserted fact.
- [x] **M** `15_SYSTEM/scripts/backend/retrieval_eval.py` + `tests/fixtures/retrieval-golden.json`: mean
      recall and MRR on an independently curated case set; both reports must share the case
      set, limit and corpus hash; any regression in either metric fails the comparison.
- [x] **S** Tests: `tests/test_learning.py` (source→proposal→evaluation→approval→recall,
      bad evidence, changed record, tampered proposal, CLI approval), `tests/test_retrieval_golden.py`.

## Phase 34 — Capability catalogue and approval-gated install · 🟢

*Source: charter §7 (register roles and abilities) and the owner's brief: a catalogue of
skills, plugins and tools with compatibility, origin and permissions, a suggestion per
session, and installation only after approval.*

- [x] **S** `15_SYSTEM/scripts/capabilities.py` + `15_SYSTEM/scripts/backend/capabilities.py`: inventory of
      active registry skills, plugins, MCP records, extensions and built-in tools with
      origin, permissions, approval list and installation state; `--task` returns keyword
      matches, `--harness-id` reports `approved` / `not_approved` / `unknown`. Retired and
      deprecated records are excluded. The MCP tool `capabilities` exposes the same read-only view.
- [x] **M** `15_SYSTEM/scripts/backend/install_skill.py` + `15_SYSTEM/scripts/install_skill.py`: plan → apply
      → never replace. The plan binds skill id, harness, destination, file digests and a
      `plan_id`; apply requires `--approve`, refuses a stale or modified plan, writes only
      into a new directory, and leaves `.install-incomplete` on a partial write.
- [x] **S** Tests: `tests/test_capabilities.py` (registry + built-in inventory, suggestions,
      retired records, CLI/MCP), `tests/test_install_skill.py` (review required, no
      replacement, stale source, unapproved record, visible incomplete install).

## Phase 35 — An installed brain is a whole brain · 🟢

*Source: issue #27 and the owner's decision that an install uses the repo's sixteen zones,
not the old template folders.*

- [x] **M** `scripts/install.py` lays the same sixteen zones the repo uses, read from
      `15_SYSTEM/config/system.json`, and ships what the gates judge: `15_SYSTEM/scripts`
      (registry door, backend, MCP), `15_SYSTEM/schemas`, `15_SYSTEM/memory`,
      `15_SYSTEM/integrations`, `15_SYSTEM/migrations`, `15_SYSTEM/templates`,
      `02_WIKI/reference_maps`, `AGENTS.md`, `.gitignore` and `tests/test_installed_home.py`.
      The home's `system.json` carries `"home": true` and binds every plane's `test` to that
      one proof file, so the map an installed brain ships is a map it can re-run.
- [x] **S** `vault-template/` is now only the starter (`index.md`, `_templates`); the old
      `00_Inbox…90_Agent_Output` folders are gone from installs. Migration note in
      `CHANGELOG.md`: an existing home keeps its notes where they are and gains the zones
      beside them; nothing is moved or deleted by the installer.
- [x] **M** `tests/test_phase16_host_independence.py` now runs the *installed* `health.py`
      (the old version ran the source repo's script, so every root-only gate judged the repo
      and a home with no readers, no map and no registry door passed), asserts the eight
      plane line, runs the installed suite, and compares the zone shape to the source.
- [x] **S** Measured in a fresh `--target` home: install prints 16 zones / 6 plane stores /
      `34 kinds, 16 zones, 8 planes proved by tests/test_installed_home.py`; health reports
      8/8 gates OK (12 tracked stores, 4 disposable absent by design); the home suite runs
      5 tests; `memory.py --recall` answers `NO_ENTRY`; `hades.py list` opens the registry.
- [x] 🔵 Limitation closed by phase 46: the installer has an update path. `--upgrade HOME` judges
      every shipped path against the digest its own record lays in the home (`scripts/install.py::MANIFEST_REL`),
      so a brain is upgraded in place and a note a person wrote is never overwritten by a script.

## Phase 36 — Fine-tuning pipeline, only behind an independent eval · 🔵

*Source: the owner's brief, phase 4 ("the next phase adds a data-preparation and fine-tuning
pipeline with an independent evaluation set; a model improvement is never claimed without
measurable evidence"). The first step (the dataset builder) shipped in phase 36; the eval gate,
the before/after claim and the recovery path shipped with it and this list did not notice. What
was re-measured here, on 2026-11-02, is the tree, not the memory: `git tag --contains 3cb54da` and
the commands each row now names. The fine-tuning step itself is still unbuilt — deliberately, and
the ⛔ row below is the reason: no dataset manifest, no independent eval, no before/after report
means no claim.*

- [x] 🟢 **M** A dataset builder over approved sources only: every training example cites a
      `source_import` id and a byte range, and a source the owner has not marked shareable is
      refused rather than silently included. The dataset manifest records source ids, counts
      and a digest, so a training run can be reproduced from records alone. Shipped as
      `15_SYSTEM/scripts/backend/dataset.py` behind `sources.py dataset-share | dataset-build |
      dataset-verify`: marking is a preview unless `--approve` is passed, `build` slices each
      record's own `raw.txt` so the cited range reproduces the example text byte for byte,
      and `dataset-verify` re-hashes a folder against its manifest. Eight tests in
      `tests/test_phase36_dataset.py` prove the refusal, the byte ranges, the digest and the
      tamper check.
- [x] 🔵 **S** An independent evaluation set in the `tests/fixtures/retrieval-golden.json`
      format, with a gate that refuses any case id appearing in the training manifest — an
      eval that shares examples with training measures memorisation, not retrieval.
      Shipped as `tests/fixtures/retrieval-independent-eval.json` (a hand-curated set, its
      `provenance` field says who made it and when, and every case carries the id the gate needs)
      plus `15_SYSTEM/scripts/backend/dataset.py::leak_check`, reached by
      `python 15_SYSTEM/scripts/sources.py dataset-eval-gate DATASET_DIR EVAL_JSON`; it answers
      `{ok, leaks, cases, dataset_digest}` — every leak names the case, the identifier and the
      dataset digest it collided with — and the command exits 1 unless `ok` is true.
      `tests/test_phase42_independent_eval_gate.py` proves the refusal for a case id, an example
      id, an expected source id and a document origin, and proves a tampered dataset cannot pass.
      *The row was still open in the tree that shipped the feature: `git tag --contains 3cb54da`
      answers `v0.1.0 v0.2.0`, so `v0.1.0`'s own release body described this gate while the row
      above it still read `- [ ]`. A row that describes work the tree already contains is not an
      open item, it is a second truth — the same defect class the link readout reports for prose,
      so re-measure the roadmap against the filesystem before ticking it.*
- [x] 🔵 **S** Before/after comparison through `sources.py compare-benchmarks`: acceptance is
      a repeatable recall/MRR gain with a positive margin over the golden set, not one lucky
      run; a regression fails the comparison as it does today.
      `retrieval_eval.claim()` answers `IMPROVEMENT` only when *every* repeat improved both mean
      recall and MRR by at least a stated positive margin on the same cases and corpus, and the
      claim names the `scripts/base.py --save` state it stands on; `REGRESSION` and `NO_IMPROVEMENT`
      are the other two answers, and a margin of zero, a non-number, an unequal repeat count or a
      missing base is a `ValueError`, not a softer verdict.
- [x] 🔵 **S** A recovery path shipped with the result: `scripts/base.py --save` records the
      state the change started from, and the report carries the `--recover` command that
      undoes it. A model or settings change without a measured baseline and a way back is
      refused.
      `--save` writes the green state and `--recover [--stamp X] [--note why] [--candidate FILE]`
      falls back to it, each act journalled in `14_CANDIDATES/loop/recovery.jsonl` and checked
      against the base's own identity. `load_base` returns the refusal a record cannot answer for
      and `scripts/base.py:199` prints it, so a snapshot whose bytes are gone is a `REFUSED` and
      not a reported success — `test_a_journal_entry_whose_bytes_are_gone_is_refused_not_faked`
      in `tests/test_phase20_known_good_base.py` proves that, and
      `test_recovery_reverts_the_brain_and_keeps_the_lessons` proves a recovery never rewrites the
      shelf or the lesson ledger. Exactly one act per run, enforced at `scripts/base.py:294`.
- [ ] ⛔ A "better model" claim with no dataset manifest, no independent eval and no
      before/after report — refused, by the brief's own rule and this repo's measurement law.

## Phase 37 — The version stops being a hand-typed number · 🟢

*Source: the owner's brief (2026-11-02) — "assume 0.0.3 and let the version follow the size of
the work; put that rule in the code". Issue #4 removed the hand-typed test-count badge for the
same reason; `VERSION` was the last hand-typed number the repo trusted. Measured before the
change: `VERSION` 0.0.3, `pyproject.toml` 0.0.3, README title `HADES OS v0.01`, README badge
`v0.0.3`, one tag `v0.0.3` and 121 commits after it — three of those five places disagreed and
no gate could see it.*

- [x] **S** `scripts/version.py --check` compares every place the number lives — `VERSION`,
      `pyproject.toml`, the README title, the README badge and the changelog section — and
      refuses by name: `INVALID the README title says 'HADES OS v0.01' while VERSION says
      '0.0.3'`. A released number must appear in `CHANGELOG.md`; an unreleased one must have a
      non-empty `## [Unreleased]`, so shipped code with no changelog entry is a red gate too.
- [x] **M** The bump is derived from the work, not from a feeling: `--bump auto` reads the
      commit subjects since the last tag (`git describe --tags`) and takes the highest signal —
      `feat!`/`BREAKING CHANGE` → major, `feat` → minor, `fix`/`perf` → patch, and
      `docs`/`test`/`chore`/`refactor`/`ci`/`style` → `NO_BUMP`. Prose that carries no type is
      never a bump. At 0.x a breaking change raises the **minor**, because SemVer §4 makes the
      minor the breaking level below 1.0 and the jump to 1.0 is the owner's decision, not an
      agent's.
- [x] **S** No tag is ever created by the gate. `--bump` writes `VERSION` and `pyproject.toml`,
      then prints the two commands a human runs (`git tag v… && git push origin v…`) — a tag is
      a published promise. One test asserts the bump leaves no tag behind.
- [x] **M** 16 tests in `tests/test_phase37_version_gate.py`: the whole ladder, both refusal
      shapes (drift and empty-unreleased), the malformed `0.003`, the printed release command,
      and a check over this folder itself so the repo cannot disagree with its own number again.
- [x] **M** The same disease in the workflows: `ubuntu-latest` moved to Ubuntu 26.04 on
      2026-11-01, that image has no CPython 3.9 x64 build, and every `ci` and `loop` run died in
      `setup-python` — five red runs — while the local gates stayed green and the README still
      claimed "Python 3.9+". The nightly loop, the repo's headline promise, had silently stopped.
      `scripts/ci_floor.py` joins the health gates: it compares `requires-python`, the ci matrix, the
      runner images those jobs ride (no floating `ubuntu-latest`), and the `python floor` rows in
      README and START; `tests/test_phase37_ci_python_floor.py` adds 15 tests, one per refusal.

## Phase 38 — A stranger is told how to work here · 🟢

*Source: the owner's brief (2026-11-02) — "the description must be clear and complete". A repo
whose rules live only in the maintainer's head is a repo nobody but the maintainer can finish.*

- [x] **S** `CONTRIBUTING.md` rewritten as the protocol in working order: issue first → test
      first → the registry door → the candidates shelf → `doc_report.py --write` in the same
      commit → the version derived by `scripts/version.py` → a goldfish review by a reviewer with
      no context. All ten gates named in a table, so "run the checks" is a command, not a rumour.
- [x] **S** `.github/CODEOWNERS`: the canon (`AGENTS.md`), the judging scripts (`health.py`,
      `promote.py`, `version.py`, `ci_floor.py`, `write_gate.py`, `zone_check.py`, `rules/`), the
      workflows, the registry (`11_CONTROL/`), the config and the candidate shelf each have an
      owner — the files where a quiet edit does the most damage.

## Phase 39 — The two missing reference maps · 🟢

*Source: issue #22 (charter §3) — harness2 and claude-obsidian shipped logic that only lived in
prose history; only SuperAGI had an adopt/refuse artifact.*

- [x] **S** `harness2-to-hades-map.md` (15 rows: 7 adopted whole, 4 adopted with a named refusal,
      4 refused) and `claude-obsidian-to-hades-map.md` (16 rows: 7 / 6 / 3), in the shape of the
      SuperAGI map — every adopted row cites the script **and** the test that proves it.
- [x] **S** The maps are enumerated by `02_WIKI/indexes/reference-maps.md` rather than
      `[[wikilink]]`ed from each other: `scripts/install.py` ships `reference_maps/` but not
      `indexes/`, so a link inside a map would dangle in every installed home. Measured: 158
      backticked repo paths stat'ed, all 23 cited `file::test` names matched a real `def test_…`;
      zero exceptions taken, the only misses are upstream paths, gitignored paperwork and journals
      a script creates on its first run — now worded as such. `00_START_HERE/CHARTER_AUDIT.md` §3
      points at all three maps.

## Phase 40 — The lessons ledger grows a plane and learns to disagree · 🟢

*Source: issues #25 and #24 (charter §5). The eight planes were mapped in phase 26 but the
error plane's rows carried no plane field, and no plane could detect a contradiction.*

- [x] **M** `plane` on every lesson row, at the door and in `--check`, with a deterministic
      migration for the rows already in the ledger. `plane_ids()` reads `system.json →
      memory_planes`, so there is no second taxonomy to drift: `--plane banana` is refused with
      the list of the eight it does accept. `--migrate-planes` previews, `--write` types all 27
      shipped rows additively — nothing deleted, nothing rewritten, idempotent on a second run,
      and `--plane` defaults from `--source` so the field is never a blank the author forgot.
- [x] **M** A measured, stdlib-only definition of a contradiction between two active lessons and
      a gate that refuses an unresolved pair while reporting a `supersedes`-resolved one.
      Measured on the real ledger before the code was written: 325 active pairs, the closest
      same-plane shared-topic pair (both *agreeing*) scores **0.31**, opposite verdicts score
      **0.00 at every threshold** — so the threshold is Jaccard cue-overlap **≥ 0.50** and the
      shipped ledger has **0** contradictions. Nothing was reclassified to make a number look
      good. `--check` now exits 1 on `CONTRADICTION mem-a and mem-b … opposite verdicts`, and
      `--contradictions` prints `overlap=` and `verdicts=` per pair. 27 tests in
      `tests/test_phase40_lesson_planes_and_contradictions.py`.

## Phase 41 — The manager agent and the conversation path · 🟢

*Source: issues #21 and #20 (charter §7, §5/§11). A role the charter names and the registry
does not hold is an unwritten definition; a memory plane with no extraction ritual is a promise.*

- [x] **M** A registered manager-role agent — `AGT-7DE1AB28` in
      `11_CONTROL/agents/AGT-7DE1AB28-structure-manager/`, written through the plan door — that
      creates and classifies projects, tasks, agents and skills. It is a **proposer, not a second
      door**: its `tool_allowlist` has no approve tool, so `15_SYSTEM/scripts/backend/tools_kit.py::Registry.execute`
      refuses its own plan and the human stays the only signer. `skills/first-session/SKILL.md`
      points at it for the moment a stranger cannot tell a project from a task.
- [x] **M** `skills/conversation-memory/SKILL.md` (record `SKL-C48357D5`) and
      `02_WIKI/reference_maps/conversation-memory-path.md`: one row per step naming the command,
      the refusal and the test — `sources.py import FILE --kind conversation --origin
      harness:SESSION` → `rebuild` → `propose --quote` (an invented quote is refused) →
      `evaluate` → `approve --approve`, a flag only a human types since the MCP door ships no
      approve tool. Nothing scans a history folder; the store is `.brain-data/`, gitignored, so a
      fresh clone honestly answers `[]`. Stated in `AGENTS.md` and projected to every host door.
      29 tests in `tests/test_phase41_manager_agent_and_conversation_memory.py`; the tests refuse
      a document that promises a mechanism the shipped doors do not have, or that forgets a
      refusal the doors really enforce.

## Phase 42 — An eval that cannot share examples with training · 🟢

*Source: the remaining checkboxes of phase 36, plus the competitive finding that peers publish
their eval harness (mem0, Khoj) while a claim with no public floor is a rumour.*

- [x] **S** A tracked independent evaluation set (`tests/fixtures/retrieval-independent-eval.json`
      — 6 self-contained cases, provenance stated in the fixture, measured answerable at recall
      and MRR 1.000 on its own corpus) and one gate that refuses it: `sources.py
      dataset-eval-gate DATASET EVAL` exits 1 and prints the 64-hex training id when any eval
      case id appears in the training manifest — an eval that shares examples measures
      memorisation. The shipped fixture against a dataset built from its own sources exits 0.
- [x] **S** Before/after through `compare-benchmarks --claim --margin M`: the verdict is
      `IMPROVEMENT` only when **every** repeat raises **both** recall and MRR by at least a
      positive margin, and the report carries both reports, the margin, the repeats, the base and
      the `python scripts/base.py --recover --stamp …` line inside it. Measured: golden set
      0.5 → 1.0 on both metrics over 2 repeats clears 0.4 and is an improvement; margin 0.9 is
      `NO_IMPROVEMENT` exit 1; base and candidate swapped is `REGRESSION` exit 1 with the way back
      named; with no recorded base the claim is refused **before** any verdict (exit 2).
      **Tightened, and measured first:** plain `compare-benchmarks` on a regression used to exit
      **0** — it printed `regressed` and stayed silent — now it exits 1.
      23 tests in `tests/test_phase42_independent_eval_gate.py`, 5 more in
      `tests/test_phase36_dataset.py`.

## Phase 43 — Design with an elephant, review with a goldfish · 🟢

- [x] 🔵 **M** `skills/elephant-draft` and `skills/goldfish-review`: the six brainstorm lenses
      translated into this repo's real constraints, the five review stages, the semantic split at
      `## Detailed Implementation Plan`, the severity/id scheme, the failed-reviewer rule and the
      clean-round / two-clean-rounds / five-round-cap / churn stop rules.
- [x] 🔵 **S** `11_CONTROL/reviewers/` — the goldfish personae as bounded, read-only definitions
      with their reading lists, so a harness can spawn exactly one.
- [x] 🔵 **M** `scripts/goldfish_check.py`: a review is only valid if every reviewer is recorded
      `run`, no Blocker or Major is left unsettled, and every citation names a file a clone can
      open. An isolation rule with no gate is prose: if a harness has no subagent tool the review
      stops — "a review in the same context is not a Goldfish review".
- [x] ⛔ EGM's plugin manifests, marketplace install and harness-specific frontmatter: this repo
      ships plain files its own gates judge, and a plugin installer is the SuperAGI shape §2
      refuses.

*Measured 2026-11-02: `python scripts/goldfish_check.py --personas` → "OK — 8 goldfish personae";
`--self-test` → "SELF-TEST OK — 12 cases: the honest artifacts pass and every lie is refused";
`python -m unittest discover -s tests -p test_phase43*` → 30 tests OK; the gate is the twelfth
entry of `scripts/health.py` and prints an OK line inside an installed home, where no reviewer set
is installed. Registered through the plan door: `hades.py doctor` → 22 records, `errors: 0`.*

## Phase 44 — Peer practices worth stealing, and the ones worth refusing · 🟡

*Surveyed against mem0, Letta/MemGPT, Khoj, Basic Memory, Graphiti/Zep, SuperAGI and
[Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) (measured 2026-11-02: Apache-2.0,
Python, 140,699 stars, last push 2026-11-01 — the closest peer this repo has, because its stated
rules are "local deterministic parsing, every edge explained, no vector store").*

- [x] 🔵 **S** MCP tool behaviour tags (`read_only` / `destructive` / `idempotent`) on every
      door, cross-checked against the agent `tool_allowlist` (Basic Memory's progressive tool
      discovery, without its AGPL code). `15_SYSTEM/scripts/backend/tools_kit.py` carries the one
      closed vocabulary and `UNDECLARED_TAG = "destructive"`, so a class that declares nothing is
      carried as the worst case instead of read as harmless;
      `python 15_SYSTEM/scripts/mcp_server.py --check-tools` measures the house: 13 door tools
      tagged, 6 engine tools tagged, 3 agent records cross-checked, 0 destructive.
- [x] 🔵 **M** Validity windows on lessons (`verified_at`, `expires`) so an expired claim is a
      gate row rather than a stale certainty (Graphiti's bi-temporal edges, minus the LLM).
      `rules/memory.schema.json` is version 3; `--check` refuses a stale or impossible window,
      `--recall` marks it and the MCP `memory_recall` door appends the same `recall_mark()`, so an
      agent never sees a friendlier answer than a human does. Measured when the row was written
      (`python scripts/memory.py --windows`): no shipped row carried either field, so the counts
      were 0 current / 0 stale / 0 invalid — which is why absent `expires` means evergreen rather
      than "aged by `date`", a claim no row made. The row count is deliberately not quoted here: a
      typed count goes false the next time a lesson lands, and `--windows` prints the live number.
- [x] 🔵 **S** `kb.py --related <note>` — deterministic top-k neighbours from the FTS5 index, so
      "related notes" needs no embedding activation (Smart Connections' value, none of its cost).
      Ranked by cosine of IDF-weighted term vectors, ties on `(-shared, path)`, each line printing
      the terms it stood on and how many notes carry them. Two measurements shaped it: a plain
      overlap ratio and a weighted one both answered "what is near the memory-planes map?" with
      ROADMAP.md, CHANGELOG.md and HANDOFF.md, because a document at the repo root mentions every
      word — so the pool is zone notes only, the answer states how many shelf documents it skipped
      (10 here), naming one is refused, and `search` still returns them.
- [x] 🔵 **S** Confidence on every edge of the link graph — `extracted` (the author wrote the
      wikilink), `inferred` (a gate or the indexer deduced it), `ambiguous` (a row on
      `14_CANDIDATES/`, which is what "uncertain" means here: it waits for a human). Taken from
      graphify's `EXTRACTED | INFERRED | AMBIGUOUS` edge schema (`docs/how-it-works.md`, "Confidence
      tagging"), whose third label is "Uncertain — flagged in the report for manual review": an
      uncertain edge is escalated, not silently kept in the graph.
      `python scripts/link_check.py --confidence` prints the three counts and names every escalated
      edge; the labels are checkable from the source text alone — no model, no embedding, no graph
      library. Two things the labels replaced: the old resolver answered a stem collision by keeping
      whichever path sorted first, so a *guessed* target was recorded as a healthy link, and a
      `14_CANDIDATES/` target was printed as an ordinary edge. Both now escalate, and an ambiguous
      edge is left out of the graph so it cannot buy false reachability.
- [x] 🔵 **S** A link-graph readout in `health.py`: degree-0 notes and bridge notes (one link
      joining two otherwise separate clusters). Degree-0 is a **navigation** defect, not a retrieval
      one — full-text search reaches every indexed note whether or not anything links to it, and the
      first draft of this row claimed otherwise; what an orphan cannot do is be *arrived at* by a
      human or an agent following links out of the vault. Their god-node/Leiden signal, computed
      from the wikilinks already in the vault — no NetworkX, no embeddings, no new dependency.
      `python scripts/link_check.py --readout` is the gate: it prints the denominator ("notes
      scanned", which is what proves the pass was not silence), the components, the degree-0 rows,
      the bridge notes and the max degree, and it refuses while any edge is still escalated — a
      graph it cannot settle is not certified healthy. The default broken-link run prints the same
      shape beside its own verdict, so `OK — 0 broken links` can never again be read as a statement
      about reachability; `health.py` runs both modes as two gates, because they are two claims.
- [x] 🔵 **S** `schema_version` stamped inside every generated JSON file, so a reader can tell
      which contract wrote it and a gate can refuse a stale one instead of mis-parsing it
      (graphify stamps `graph.schema_version` in its `graph.json` "so integrations can detect
      incompatible format changes"). `python scripts/schema_stamp.py --check` is the gate and
      `--stamp --write` is the one migration path; the writer stamps (`scripts/loop.py` calls
      `stamp_payload()` when it appends to the ratchet history) rather than a later pass painting a
      number onto a file it did not author. Every file the walk opens is printed with its contract,
      its state and what to do about it — including the hand-authored ones (`rules/*.schema.json`,
      the curated retrieval fixtures) that are named as authored rather than counted as clean, so
      "0 missing" is a statement about generated output and not about the whole tree.
- [ ] ⛔ graphify's parsing engine itself — ~40 tree-sitter grammars, NetworkX, graspologic,
      optional whisper/yt-dlp, and a Python 3.10+ floor: refused for **absence of evidence**, not
      for complexity. None of the six conditions of `00_START_HERE/CONSTITUTION.md` is met — no
      named problem, no baseline measured on this corpus, and a 3.10 floor that breaks the floor
      `scripts/ci_floor.py` guards. This repo's
      "AST" is the markdown link graph, which is already explicit, so only the schemas above
      transfer. Its own docs also warn that when `root` is omitted, ids "can end up carrying path
      segments from the machine they were extracted on" (`ARCHITECTURE.md`) — the reason every
      citation in this repo stays repo-relative and `clone_readable()` refuses the rest.
      Full adopt/refuse reasoning: `02_WIKI/reference_maps/graphify-to-hades-map.md`.
- [ ] ⛔ Postgres/pgvector, Neo4j, FastAPI+Redis+Celery, Letta's App Server, mem0's cloud and
      any LLM step inside the write path — each is now unlockable *on evidence* by
      `00_START_HERE/CONSTITUTION.md` and none has met its six conditions: no baseline, no
      measured before/after, no cost-and-risk review. What stays unconditional is the blast
      radius: the core keeps working offline without any of them, nothing listens until a human
      presses the approve flag, and no private record leaves the vault.
- [ ] ⛔ A docs site (mkdocs/GitHub Pages): the content is the bottleneck, not the tooling.

## Phase 45 — A plan that cites what is not here is a second truth · 🟢

*Source: the measurement taken while ticking phase 36 by hand on 2026-11-02. `git tag --contains
3cb54da` answered `v0.1.0 v0.2.0` for rows the roadmap still called open, and two of the
corrections I then wrote were themselves wrong until I checked them — a command given flags it does
not take, a function described as returning a list when it returns a verdict dict. A document
nobody re-measures drifts from the filesystem in silence; `scripts/link_check.py` already proved
the answer is a gate, not a habit. This phase is that gate pointed at this file.*

- [x] 🟢 **M** Every path a CLOSED row cites must resolve, by
      `python scripts/roadmap_check.py --check`: measured first over the shipped roadmap — 8 rows
      cited `backend/…` while the repo holds them under `15_SYSTEM/scripts/backend/…`, true as
      names and unopenable from a clone, which is the same law `scripts/common.py::clone_readable`
      enforces on generated artifacts. Those rows now carry the repo-relative path. The counts this
      row used to type (`74 rows`, `80 citations`) are deliberately gone: they were wrong the moment
      this phase's rows were added to the file they measured, which is the law this repo already
      states for every other number — `python scripts/roadmap_check.py --check` prints the live
      ones. The suite is `tests/test_phase45_roadmap_citations.py`; `python scripts/doc_report.py
      --check` prints the test count it holds, because the count this row first typed was stale
      before the commit landed.
- [x] 🔵 **S** The anchored and member forms are judged too: `scripts/base.py:294` has to be a line
      the file actually has, and `15_SYSTEM/scripts/backend/vector.py::Embedder` a symbol it
      defines. Both are refused even in an OPEN row — an anchor states what is, so an intention is
      no excuse for a wrong observation.
- [x] 🔵 **S** An OPEN row may cite a file it has not written yet: the gate calls that `PLANNED` and
      moves on. A plan punished for naming its next artifact would only learn to be vaguer.
- [x] 🔵 **M** What the gate cannot see is named, never counted green. A journal a script declares
      (`14_CANDIDATES/loop/recovery.jsonl`) and a path that belongs to an upstream project are
      printed as `NOTED` lines, and git's own answer is probed on the path exactly as written: on a
      Windows checkout `core.autocrlf` leaves a bare `\r` line in the working copy of `.gitignore`
      (the tracked blob is clean), and git then treats any path probed *as a directory* as ignored —
      which would have laundered an upstream `docs/` path into this repo's machine plane.
- [x] 🔵 **M** Wired as the fifteenth gate in `python scripts/health.py`, keeping the
      one-OK-line-per-gate invariant `tests/test_phase16_host_independence.py` counts. In an
      installed brain home the roadmap is the source repo's plan rather than a promise the home
      made, so the gate names that and exits 0 instead of inventing defects.
- [ ] 🔵 The gate's OK line ends with a count of closed rows that carry no path citation at all, and
      that number is the open work here: those rows were closed on evidence that was never written
      down. Each needs a real witness — a file, a test name, a ledger id — and a citation invented
      to silence a counter is the defect this phase exists to refuse. Read the live count from
      `python scripts/roadmap_check.py --check`; typing it here would make this row the second
      truth it is meant to measure.

## Phase 46 — A home that cannot be upgraded is a home that goes stale · 🟢

*Source: the limitation phase 35 left open, plus the fact that every phase after it shipped engine
files installed homes could not receive. The starting state, measured rather than remembered, on
2026-11-02: re-running the installer against a folder that was already a home ended in*

    $ python scripts/install.py --target ~/brain        # ~/brain already holds a brain
    install.py: error: target ~/brain is not empty — pick a fresh folder

*The advice was sound for a flat copy and unhelpful by the second week: a home accumulates notes,
lessons and runtime state the repo has never seen, so the only way to get the new engine was to
build a second folder and merge by hand — which in practice means nobody upgrades, and the home goes
on running gates written before half of this roadmap existed. Copying over it would have been
worse: an overwrite deletes a person's thinking in order to deliver a script.*

- [x] 🟢 **M** An install now finishes by hashing what it actually laid, into the home, at
      `15_SYSTEM/generated/install.json` (`scripts/install.py::MANIFEST_REL`): one sha256 per shipped path,
      plus the engine's own bytes for those paths, so a document a home re-measures for itself is
      not read back as an endless pending update. The file declares its contract under
      `install-manifest` (`scripts/schema_stamp.py::CONTRACTS`), so the repo's stamp gate judges it and
      `--check` refuses a home record with no version in it.
- [x] 🟢 **M** `python scripts/install.py --upgrade HOME` answers one question per shipped path —
      *are these the bytes we wrote, or the bytes you wrote* — in `scripts/install.py::judge`:
      `UNCHANGED / UPDATED / ABSENT / ADDED / KEPT / PRESENT / YOURS`, each printed with its path.
      The plan it judges is the same list an install lays (`scripts/install.py::ship_plan`),
      so an upgrade cannot be asked about a path the installer never shipped, or refuse one it did.
- [x] 🟢 **M** A path the home edited is `KEPT`: never written, named in the output, and carried
      forward into the new record with both its old and its present digest
      (`scripts/install.py::final_state`) so the next act still knows it from an edit. A path
      the home holds *without* a record of it is `YOURS` — the same refusal, one level stricter: it
      stays byte-identical, is deliberately left out of the new record (recording an unowned file as
      "what the installer wrote" would teach the next act to overwrite it), the rest of the home
      still moves, and the run exits 1 with the list. `tests/test_phase46_installer_upgrade.py`
      pins both: the file survives, the other engine files land, the second act reports `YOURS`
      again rather than silently rewriting it.
- [x] 🟢 **S** The brain's own state is out of the installer's business by name, not by hope:
      `scripts/install.py::PROTECTED_DIRS` lists the runtime, lab, quarantine shelf,
      knowledge index, local data, editor folder, backups and the lesson ledger, and
      `scripts/install.py::plan_refusals` stops the act when the *plan itself* lands a real
      file there — a bug in this script, caught before it writes. The shelf's `README.md` is the one
      exception the installer ships, and it is stated as an exception.
- [x] 🟢 **S** Nothing is deleted and `--dry-run` proves it. A file this engine no longer ships is
      named `ORPHAN` and stays in the home unread, and the closing line counts them; a `--dry-run`
      takes the home's
      `tree_fingerprint` on entry and on exit and fails if they differ, so "nothing was written" is
      a measurement instead of a promise. Every act that writes re-hashes each file from the disk it
      landed on and only then restamps the record, and appends one line to the act journal this
      script names at `scripts/install.py::JOURNAL_REL` — the verdict counts, the refusals and the digest of
      the record that now describes the home.
- [x] 🟢 **S** The bytes an install lays are the bytes the ship plan says it lays — one plan, read
      twice (`scripts/install.py::write_doors` takes the plan, not the repo). The agent doors were
      the exception: reading a door as text and writing it back re-encodes its newlines, so a fresh
      home could hold a door the engine never shipped, while the record — built from those same
      mangled bytes — kept calling it `UNCHANGED`. The upgrade cannot see this, because it compares
      the home against what the *record* claims the engine shipped; the only witness is the record's
      own two maps agreeing for every path nobody edited, which is what
      `tests/test_phase46_installer_upgrade.py::test_a_real_install_lays_the_engines_bytes_at_every_shipped_path`
      demands of a real install.
- [x] 🔵 **S** Two design choices differ from the first draft of this brief, and both were decided
      against it on purpose. A file the record names but the home lost is **restored**, not left
      absent: a home missing `scripts/probe.py` cannot run its own gates, and a deleted gate is not
      a decision an upgrade can honour silently. And a collision **does not abort the act**: the
      first draft stopped everything, which let one unowned file hold a whole brain hostage; it now
      skips that path, still exits non-zero, and still says which file and why. A `--restore` flag
      was rejected as unneeded once restore is the default.
- [x] 🔵 **M** The documents a home re-measures for itself (`doc_report.py`'s `DOCS`, imported here
      rather than restated) are re-measured only when none of them is `KEPT`: this installer will not
      run a number-filler over a document a person edited, and will not ship the source repo's
      measurements into a home whose own it cannot take. Either way it names which, and the command
      that is safe to run by hand.
- [x] 🟢 **M** `tests/test_phase46_installer_upgrade.py` — the count is printed by
      `python -m unittest discover -s tests -p "test_phase46*.py"`, not typed here. It covers the
      plan's refusals, each verdict on its own, the two-map record, the KEPT/YOURS distinction,
      "a second upgrade moves nothing at all", and a real home: install, then the installed
      `health.py`, then the installed suite, then a dry run that moves nothing, then an upgrade with
      a note a person wrote in `01_INBOX/` that survives it with front matter the gates still accept.
- [x] 🔵 **S** The verdict the first act could not reach, closed in the same phase: an upgrade now
      names what it cannot ship. `judge` only asks about paths the plan holds, so a path the engine
      *retired* was invisible — the home kept the file, the record kept its hash, and the act said
      nothing. `scripts/install.py::judge_removed` reads the record the other way round and reports
      `ORPHAN` (this engine no longer ships it, the home still holds it: named, kept in the record so
      the next act reports it again, never deleted) and `GONE` (the home already lost it: reported
      once, dropped). The dry run names them too, and the closing line counts them instead of
      promising. A `--clean-orphans` flag was refused: deleting a file this script no longer ships is
      deleting a note the owner may have moved into it, which is the one thing an installer has no
      licence to do to a brain it did not think.

## Phase 47 — The owner's v4.0 brief becomes the constitution of record · 🟢

*Source: the owner's HADES brief, version 4.0 §1-§3 and §17-§18, written on 2026-11-02. The brief
does not ask for more rules; it asks which rules are fundamental and which are merely today's
engineering choice. This phase separates them, and says plainly which of the fundamental ones the
repo does not yet do.*

- [x] 🔵 **M** `00_START_HERE/CONSTITUTION.md` — the eight immutable principles with where each is
      enforced today, the precedence ladder, the executive-law register (each law with a version,
      owner, arbiter and review path), the definition of what is not evidence, and the honest
      debt table. Source: brief §2, §3, §13, §17.
- [x] 🔵 **S** two registry decisions written through the plan door, in `09_OPERATIONS/decisions/`:
      one adopts the constitution and binds the eight principles to a manual revision path only,
      one converts the "stdlib-only / no app / no network / no port" stack into executive laws
      that unlock layer-by-layer on measured evidence. Nothing about the principles moved without
      the owner's brief and a human pressing approve.
- [x] 🔵 **S** the refusals in this file re-grounded: the header law, the external-parsing-engine
      row, the database-and-app-server row and the HTTP/server row now state *absence of
      evidence* as the reason, each with the condition that would change it. A reason that a
      subsystem is "too complex" is the one argument brief §3 forbids.
- [x] 🔵 **S** stage 0 of that order — and the first thing it found was not a missing capability but a
      measurement that lied. `scripts/base.py --save` copies the tree into a recorded known-good base
      under the snapshot root, and `scripts/link_check.py` walked that copy as if it were the vault:
      every note existed twice in the stem index, so the resolver's collision rule — the rule whose
      entire job is to refuse *guessing* which of two files the author meant — fired on links the
      author had written unambiguously, and the graph the owner drew collapsed to no edges and one
      island per note. Invisible in CI and in `python scripts/health.py`: the plane is gitignored, and
      every vault gate defaults to `vault-template`, so only the machine that had just recorded a base
      could see it. `link_check.py::link_targets` now takes the recorded base out of the target index
      and nothing else out: the test is vault-relative, so a snapshot judged as its own vault still
      resolves its own links, and it is scoped to the snapshot root alone, so two live notes that
      genuinely share a stem are still refused rather than bound to whichever path sorts first.
      Measured by `python scripts/link_check.py --vault . --readout`, which prints the tree it judged
      and the counts, so an empty result says what it looked at. Source: brief §7 (the link graph *is*
      retrieval) and §17 (a fix is a test, not a paragraph).
- [x] 🔵 **S** `tests/test_phase47_link_graph_plane.py` — written red first, on a fixture and on the
      real tree with a base copied into it. Before the change the three regression cases failed naming
      exactly the snapshot path, and the two guard cases (a live stem collision still ambiguous, a
      snapshot opened as its own vault still extracted) passed all along — which is what pins the fix
      to its scope instead of letting it widen into a general silence. Run it with
      `python -m unittest tests.test_phase47_link_graph_plane`; the test count is that command's to
      print, not this file's.
- [x] 🔵 **S** the same class of blind spot, closed — and the row that predicted it was half wrong,
      so the correction belongs in the record rather than being quietly deleted. It named the index:
      `scripts/kb.py` keeps one exclusion list (`NOT_CORPUS`) and the recorded base is not on it, so a
      full-text index built on a machine that had just recorded a base "must" return each note once per
      snapshot. Measured, it does not. `kb.py:56` declares
      `MACHINE_PLANE = ("11_CONTROL/", "12_RUNTIME/", "13_LAB/", "14_CANDIDATES/", "15_SYSTEM/")` and
      the snapshot root lives under `15_SYSTEM/`, so the index drops the whole plane for a reason that
      has nothing to do with the base: `kb.corpus` on the real tree is **58 files, 0 inside a base**.
      The reader that *was* still lying is the nightly loop. `scripts/loop.py::vault_signals` walked the
      tree the unfiltered way and reported **174 orphans, 84 of them copies inside one recorded base** —
      which is the job telling the owner, every night, to file notes they had already filed. Now one
      predicate decides what the live plane is: `common.SNAPSHOT_ROOT` and `common.is_recorded_base(rel)`;
      `scripts/base.py` imports the constant instead of restating the literal, and both
      `link_check.link_targets` and `loop.vault_signals` call the predicate; the index needed no change,
      because the index was never the one lying. After:
      `python scripts/loop.py --readout --vault .` on the tree that holds base `20261102T145801Z` prints
      **189 markdown walked, 89 copies excluded, 100 judged live — 90 orphans, 0 inside a base**, and
      `python scripts/link_check.py --vault . --readout` judges the same 100. Source: brief §2 principle
      three (a claim a measurement disproves is corrected where it stands) and §17 (a fix is a test).
- [x] 🔵 **S** `tests/test_phase48_one_plane_law.py` — written red first, on a fixture with a base copied
      into it, and pinned by the guards that must not loosen with it: the loop's orphan and stale-inbox
      counts stop naming snapshot paths, a recorded base opened as its own vault still reports its own
      notes, and two *live* notes that genuinely share a stem stay ambiguous instead of binding to
      whichever path sorts first. Run it with `python -m unittest tests.test_phase48_one_plane_law`;
      the test count is that command's to print, not this file's.
- [ ] 🔵 **S** the residual the fix exposed, now printed by a command instead of argued. Pointed at this
      repo's own tree, `python scripts/loop.py --readout --vault .` reports **90 live orphans** and
      prints the fence it judged by: `00_Inbox`, `10_Projects`, `20_Notes`, `30_Resources`,
      `90_Agent_Output` — the five keys of `rules/zones.json`. Not one of those five names is a folder
      in this repo: the tree has `01_INBOX` and `03_PROJECTS`, and the readout's histogram puts **79 of
      the 90 in seven top folders the fence never names** (`00_START_HERE` 14, `skills` 14,
      `11_CONTROL` 12, `02_WIKI` 10, `14_CANDIDATES` 10, repo root 10, `15_SYSTEM` 9) with the remaining
      11 spread over `03_PROJECTS` (2) and one each in nine more. Pointed at the shipped default
      `vault-template`, the same rule reports **0**, because the template is the structure the fence was
      written for. So the number is not 90 life notes lost — it is one rule reading a map of a different
      tree, and a second map nobody compares it to: `doc_report.py:68` and `install.py:191` read the
      16-entry `zones` list in `15_SYSTEM/config/system.json` (each entry keyed `dir`/`plane`), and the
      two sets share **no name**. What is missing is one declared home for the project's own plumbing —
      or an orphan rule that reads the map the installer lays — with the readout printing the *life*
      notes left orphaned separately from the machine's, so the nightly advice to the owner means their
      notes and nothing else. Source: brief §4 and §19 stage 1.
- [ ] 🔵 **L** the debt table closed, in the order the owner's brief sets: encrypted backup with a
      real restore test (§8), the per-agent boundary at the door that actually serves reads
      (§8/§9), the record model and entity statuses the personal brain needs (§4/§6), the durable
      queue, router, planner and evaluator with no daemon (§9/§14), and the BenchLab adapters that
      let any of it claim to be better (§11). Each closes with its own gate, not its own prose.

*Measured 2026-11-02: `python 15_SYSTEM/scripts/hades.py doctor` -> "errors: 0 | warnings: 0" with
the two new decision records in the registry. The constitution is honest about the debt it names,
and the door says that debt out loud too: the same doctor run prints the six capability flags that
are documented but not enforced, and this phase turned none of them on.*

---

## Phase 49 — The door that answers agents reads the law, not the prose about it · 🟢

*Source: brief §8 («کنترل دسترسی باید مستقل از مدل AI و در سطح سرویس، فایل، فرآیند و ابزار اجرا شود»
— access control must run at the service/file/process/tool level, independent of the model) and
principle three of `00_START_HERE/CONSTITUTION.md`: a claim a measurement disproves is corrected in
place. This phase ships no new capability. It closes a class of bug found by reading one file
against another: `15_SYSTEM/scripts/backend/access.py` declares what an agent may not read, and
`15_SYSTEM/scripts/mcp_server.py` — the only surface an outside harness actually reaches — read four
of those paths anyway.*

- [x] 🔵 **M** the leak, measured before it was closed. With one run recorded by
      `15_SYSTEM/scripts/runs.py`, `python -m unittest tests.test_phase49_door_reads_its_own_law`
      on the previous commit failed red and printed the answer the door had given: `runs_show`
      returned run id `RUN-F9A34E51`, agent `AGT-CD4E8AA8`, status, step count and goal;
      `runs_list` enumerated the plane and `doctor_status` counted it. `source_search` put the whole
      stored body of a `.brain-data` source on the wire, while `source_import` on the same door had
      always refused that path — the check was the rule and these were exceptions.
- [x] 🔵 **S** one law, two answers: `15_SYSTEM/scripts/backend/access.py::denial` returns the
      *name of the rule* that stopped a path and `readable` is now that function answering `None`,
      so a refusal can quote a real rule instead of a paraphrase, and the tuple of denied planes and
      the secret-filename rule cannot drift from each other. Both the lexical and the resolved form
      of a path are judged, which is what catches a `..` walk that the old single check let through.
- [x] 🔵 **S** the door asks, instead of restating: `15_SYSTEM/scripts/mcp_server.py::tool_runs_list`
      and `tool_runs_show` refuse with the rule name and the human view (`runs.py list`/`show`), and
      `doctor_status` answers `runs.read: false` with the denying rule instead of a run count. The
      tool names did not change, so the registry record
      `11_CONTROL/mcp/MCP-E1807E50-second-brain-bridge.json` still describes the surface it exposes.
- [x] 🔵 **S** §7 minimal context, not §7 as a slogan: `tool_source_search` returns the citation
      (`id`, `kind`, `origin`, `filename`, `imported_at`), the body's length, and a 400-character
      excerpt flagged `excerpt_truncated`. Retrieval answering a query with a copy of the private
      plane was the failure mode the brief names; the byte cap is the boundary the code can enforce
      today.
- [x] 🔵 **S** the phase-22 reversal, recorded rather than quietly bent:
      `tests/test_phase22_harness_bridge.py` asserted `assertFalse(isError)` over `runs_list` — those
      assertions passed, and they were the contract of the leak, not of the design. The test now
      asserts the refusal, names `12_RUNTIME` in it, and requires nothing from inside the plane on
      the wire. The law against editing an assertion to fit new code is what forced this row: the
      assertion was wrong, so it is the code that changed and the reason that is written here.
- [x] 🔵 **S** `tests/test_phase49_door_reads_its_own_law.py` — written red first, and it fails on
      the commit before this one. Two halves: the law answers the same question two ways
      (`readable` ⇔ `denial is None`) over every denied plane and an over-blocking guard, and the
      door refuses each plane's tools with a rule name the law actually declares — a refusal that
      invents its own reason is a second truth and fails. Run it with
      `python -m unittest tests.test_phase49_door_reads_its_own_law`; the test count is that
      command's to print, not this file's.
- [x] 🔵 **S** the second battery that asserted the leak, found by CI rather than by reading:
      `15_SYSTEM/scripts/test_hades.py` — the v3 battery, the one judge that runs only in GitHub
      Actions — failed two of its own checks on `c889ee5` while the local suite and `health.py`
      stayed green. Its harness section asked `runs_list` for the promoted run and required
      `run_id in text`, and asked `doctor_status` for a run count; both passed while the door leaked
      and both were the contract of the leak. Same rule as the phase-22 row above: the assertion was
      wrong, so the code stands and the assertion is reversed in writing. The four checks that
      replaced the two are stricter than what they replaced — they require `isError`, the rule name
      `12_RUNTIME`, the human command in the refusal, and `run_id not in text`, so a closed plane
      that still echoes one id fails. Run it with `python 15_SYSTEM/scripts/test_hades.py`;
      the check count is that command's to print, not this file's.
- [x] 🔵 **M** the gap that let a green-local commit go public-red closed: `scripts/battery_check.py`
      is now a gate of `scripts/health.py`, so the pre-push loop runs the v3 battery and cannot
      pass a tree the door disagrees with; `python scripts/doc_report.py --check` prints how many
      gates the loop has, because that count is a measurement and not this file's to type.
      The gate takes no `--vault` argument — it judges the repo, not the records — and in an
      installed brain home it prints one stated-skip line, the same shape
      `scripts/roadmap_check.py` uses, so `tests/test_phase16_host_independence.py` still counts one
      OK line per gate. A battery that is missing, hangs past `--timeout`, exits without its
      `checks:` summary, or reports a nonzero exit under a zero fail count is `INVALID`, never a
      silent pass: a gate that runs nothing is not a green gate. The loop now has two doors and
      they are not the same claim: `python scripts/health.py` runs every gate, the battery
      included, and is what the pre-push loop and CI run; `python scripts/base.py --save` runs
      `health.py --fast`, which skips the one gate named in `FAST_SKIPS` and prints that skip in
      the skipped gate's own OK line, so saving a dozen bases does not spend a dozen batteries on
      bytes the plain loop already judged. A fast loop is a schedule, not a verdict: it cannot
      silence a gate — `tests/test_phase16_host_independence.py` counts one OK per gate in both
      modes, and `tests/test_phase49_battery_gate_watches_the_battery.py` proves a red gate still
      exits 1 under `--fast` — and a red house is still refused as a base. The battery's own
      seconds are printed by `python scripts/battery_check.py`.
      The gain is that the class of bug the row above records cannot be shipped blind a second time.
      Source: that row, and the law in `scripts/health.py`'s own docstring that a judge nothing runs
      before pushing is a rumour about a gate, not a gate.
- [x] 🔵 **S** the four documents that promised the opposite corrected in the same change:
      `README.md`, `AGENTS.md`, `15_SYSTEM/integrations/README.md` and
      `02_WIKI/reference_maps/superagi-to-hades-map.md` no longer say reads are open — they name the
      boundary and the two tools that refuse — and the task row of
      `02_WIKI/reference_maps/eight-memory-planes.md` points the human view at `runs.py`. What the
      sweep deliberately left alone: the bases this machine recorded under its own backups plane
      (the ledger of those recordings, `14_CANDIDATES/loop/bases.jsonl`, is the clone-readable half;
      the snapshot bytes themselves never ship), the dated candidate rows in `14_CANDIDATES/loop/`,
      and the older `CHANGELOG.md` entries. History is not edited to look better than it was.
- [ ] 🔵 **M** the residual this phase did not close, stated because the flag that would close it is
      still `false`: the denied-plane list is one flat policy for every caller, so `source_search`
      and `vault_search` still *read* inside `.brain-data` and `.kb` to build a citation — the fix
      bounds what crosses the wire, not which plane the engine touches — and `09_OPERATIONS` is
      readable through the registry tools while the config denies it as a zone. Per-actor scope at
      the door (an identity the harness cannot spoof, a read scope per agent, refusal behind an
      evidence gate) is the next phase; `filesystem_acl_enforcement` stays `false` until then,
      because the repo enforces a policy at its own door and has no OS-level boundary to claim.
      Source: brief §8 (least privilege, isolation of agent memory) and §9 (each agent has its own
      permissions and allowed context).

*Measured 2026-11-02: `python -m unittest tests.test_phase49_door_reads_its_own_law
tests.test_phase22_harness_bridge` green on this tree and red on the commit before it, and no read
tool inside a denied plane answers with data from it. Measured the same day on the next commit:
`python 15_SYSTEM/scripts/test_hades.py` red twice before the reversal — `FAIL harness: runs_list
shows the promoted run through the door` and `FAIL harness: doctor_status counts the run and the
record` — and green after it.*

---

## Phase 50 — The defects a reader finds are worth an issue, not a conversation · 🔵

- [ ] 🔵 **L** Twenty-three defects in this tree were read out of the source, reproduced by hand on
      this machine, and filed on the issue ledger as `iAlirezaaa/second-brain-os` #41–#63: three P1,
      thirteen P2, seven P3. Every body names the command that proves it, the file and the line it was
      read from, and the smallest fix the reporter would accept — and none of them was filed on an
      agent's say-so. Four of the nine claims an audit pass returned did not reproduce and were
      dropped, among them the assertion that `scripts/ci_floor.py` claims a doc cross-check it never
      performs: it reads `README.md` and `00_START_HERE/START.md` and does refuse a disagreement (a
      planted `3.11` row prints `INVALID … while pyproject.toml requires 3.9` and exits 1). The three
      P1 rows are the ones that make a green run lie: the nightly report never lands because
      `.github/workflows/loop.yml` pushes straight to a protected `main`; a failed measurement becomes
      a document row that `scripts/doc_report.py --check` then certifies as fresh; and five gates
      answer an empty — or absent — input with the same OK line they use for a clean house, `link_check`
      among them printing `OK — 0 broken links` for a `--vault` path that does not exist. Work them in
      severity order, one issue per slice, and close each with the witness its issue already names
      rather than a rephrasing of it. Where a line number moved because another slice landed first, the
      issue carries a comment with the number as read at `b450cd5`.

*Filed 2026-11-02 against `64bd3f5`; re-checked against `b450cd5` for the five commits that landed in
between, and the four whose citations moved carry a comment rather than a silent edit.*

## Phase 51 — The cipher is built before anything is allowed to claim it protects · 🟢

*Source: brief §8 requires «رمزنگاری معتبر داده‌های حساس در حالت ذخیره» and «بکاپ رمزنگاری‌شده و آزمون
منظم Restore» (sound encryption at rest, plus a backup with a *regular restore test*), and §16 requires a
bootstrap that can create an encrypted private vault. Two numbers were tried for this step and both are
recorded here rather than hidden: the slice plan called it Phase 48 (this file has no Phase 48), and it
was written as Phase 50 while the phase above was still unpublished — the issue ledger landed on the
remote first, so the published numbering stays and this block moved to 51. What ships here is the primitive
and the gates around it, and nothing more: no product surface calls it, no feature flag changes, no
personal byte is sealed yet. An encryption engine nobody has ever pointed at real data is not protection
— so this phase's honest deliverable is a thing that can be tested, and the rows below say what is still
missing for it to be called a backup.*

- [x] 🔵 **M** `15_SYSTEM/scripts/backend/crypto.py` — ChaCha20-Poly1305 as specified by RFC 8439, a
      scrypt/PBKDF2 key derivation layer, and a versioned container format (`SBO1` + kdf id + kdf
      params + salt + header + per-frame nonce/ciphertext/tag + footer digest). Why hand-written: the
      executive law L-01 of `00_START_HERE/CONSTITUTION.md` keeps stdlib as the default, `cryptography`
      is not installed here, and the Python standard library ships no AEAD construction at all — so
      there was no dependency to reach for without first meeting §3's six conditions. `python
      15_SYSTEM/scripts/backend/crypto.py --selftest` prints the known-answer lines and the named
      refusal rules; that command, not this file, is the record of what it checked.
- [x] 🔵 **S** the bug class that reading did not find: `crypto.py::aead_open` first recomputed the tag
      by calling `crypto.py::aead_seal` on the *received* ciphertext. Seal encrypts what it is handed,
      so the MAC covered double-encrypted bytes and every honest container — including the RFC's own
      §2.8.2 vector — was refused as a forgery. Found by a fourteen-line probe that compared the
      primitives against the RFC and then watched seal and open disagree, not by re-reading the code:
      a symmetric bug looks like correct code from both sides. Now the tag is recomputed directly over
      the received ciphertext.
- [x] 🔵 **S** a refusal names the rule that actually stopped it, so the ordering is part of the
      design: `crypto.py::read_header` honours only the authenticated prefix (no frame walk),
      `crypto.py::parse_container` layers the frame map on top as the evidence tool that needs no
      passphrase, and `crypto.py::open_container` compares the manifest's *declared* length only after
      the frame authenticated — the frame's own authenticated length is what the AAD binds. A splice
      therefore trips "tag", the rule that really caught it, rather than a "frame length" or
      "truncated" story the attacker's bytes would have produced. Same law the door learned in Phase
      49: a refusal that invents its reason is a second truth.
- [x] 🔵 **S** no negotiation, no silent fallback, no downgrade: an unsupported kdf id or parameters
      this platform cannot run raises a stated error instead of quietly choosing a weaker one, the
      header must equal the parameters the container was derived with, nonce reuse is its own rule, and
      `crypto.py::OPEN_RULES` is a closed set that `crypto.py::_refuse` asserts against — a rule name
      not declared there cannot be forged at runtime. `crypto.py::frame_aad` binds context, frame
      index, the sha256 of the path and the length, so a file moved, renamed or duplicated inside a
      container fails instead of decrypting into the wrong place.
- [x] 🔵 **S** `tests/test_phase51_chacha20_poly1305.py`, written red-first: the RFC vectors, tamper
      cases refused **by name** (flipped ciphertext byte, flipped header byte, wrong passphrase,
      truncated container, frame moved/repeated/spliced, version 2, reused nonce), two seals of one
      plaintext producing different bytes, and a pin on the module's import set so a future
      dependency in the cipher is a decision someone has to make out loud rather than an `import`
      that lands. Run `python -m unittest tests.test_phase51_chacha20_poly1305`; the count is that
      command's to print.
- [x] 🔵 **S** the cost stated, because §17 makes complexity measurable:
      `python 15_SYSTEM/scripts/backend/crypto.py --bench --bytes 1048576` measured **0.902 MB/s**
      here on 2026-11-02 — pure Python, one core, no C backend. That is fine for the planes this
      repo actually seals (text notes, a few megabytes) and disqualifying for media; the same command
      prints the number on your machine, and the row is honest that a self-written stream cipher is
      the trade made to stay standalone.
- [x] 🔵 **S** `SECURITY.md` gained a cryptographic-primitives section, because it had been silent
      rather than honest: the primitive is self-authored, **not third-party-audited**, and its
      credibility is held by the known-answer and tamper gates running in the suite that
      `.github/workflows/ci.yml` executes on every push — not by this document's adjectives. The
      versioned container font is what lets an audited engine replace it later without migrating the
      bytes.
- [ ] ⛔ A third-party cipher (`age`, `openssl`, a hardware engine) and proof-of-origin (signing a
      container under a separate key) are refused today for **absence of evidence**, not for
      complexity — `00_START_HERE/CONSTITUTION.md` §3 unlocks the dependency on a measured win. The
      condition that would change this row is stated rather than implied: a named problem the
      self-authored primitive cannot solve, a baseline measured against it, and a reviewed cost,
      licence and supply-chain risk. Proof-of-origin stays out of this file because there is no key
      management plane to hold a signing key yet.
- [ ] ⛔ `feature_flags.automated_backup_scheduling` stays `false` here, and that is not a gap in this
      phase: brief §14 requires every Job to carry identity, permission, status, last-run, retry
      policy, resource limit, report and stop method, and no such record exists in this repo. A timer
      wrapped around a cipher is a scheduled unverified restore.
- [ ] 🔵 **M** what this phase deliberately did not do, so nobody reads it as protection yet: the
      primitive now has a caller — `scripts/vault.py` seals and opens the planes named in the
      `private_planes` of `15_SYSTEM/config/system.json`, and Phase 52 is the record of that — but
      there is still no cross-machine restore proof and no verification record under `11_CONTROL/`,
      so `encrypted_private_backup` stays `false` beside `vector_search`, `live_orchestration`,
      `external_ingestion`, `filesystem_acl_enforcement`, `automated_backup_scheduling` and
      `github_autosync`. The debt row D-2 of `00_START_HERE/CONSTITUTION.md` stays written exactly as
      it is until a command seals a plane a human can read back on another machine.

*Measured 2026-11-02: `python 15_SYSTEM/scripts/backend/crypto.py --selftest` green; the phase test
green on this tree and red on the primitive's first draft; `python -m unittest discover -s tests` grew
by the cases in `tests/test_phase51_chacha20_poly1305.py` and `python scripts/doc_report.py --write`
regenerated the measured blocks of `README.md`, `HANDOFF.md` and `00_START_HERE/START.md`, while
`python scripts/health.py` reported the verdict it had already reported — a primitive with no caller
cannot move a gate, and the row above says that is the point.*

---

## Phase 52 — The cipher gets a door, and the door refuses more than it accepts · 🟢

*Source: brief §8 «بکاپ رمزنگاری‌شده و آزمون منظم Restore» and §16, which asks a bootstrap to be able
to create an encrypted private vault. Phase 51 left a primitive with no caller, and a gate cannot
notice that: a gate judges a surface, and there was none. This phase builds the surface over the
planes config names — and stops there. `encrypted_private_backup` stays `false`, because the restore
has been proved between two directories on the machine that sealed the bytes, not on a machine that
never saw them, and a witness written by the machine holding the key is not evidence.*

- [x] 🔵 **L** `15_SYSTEM/scripts/backend/vault.py` — the mechanism behind one seam: `plane_list` (the
      scope is read from `private_planes`, never guessed), `collect` (walk, and refuse a symlink
      rather than seal a pointer that a restore could follow out of the vault), `seal`, `inspect`,
      `verify`, `restore`, `rows`, `status`, `bench` and `gate`. Only Phase 51's `SBO1` container
      holds bytes; every index line lives in the journal beside it, which is inside the gitignored
      backup plane, so a shelf cannot leak the paths it protects.
- [x] 🔵 **M** `scripts/vault.py` — the one command a person types: `--seal`, `--unseal NAME --into
      DIR`, `--verify`, `--list`, `--status`, `--bench`, `--selftest`. A passphrase comes from a
      terminal, asked twice, or from `--passphrase-file` — and a file that resolves inside the
      repository is refused, because a key stored next to the ciphertext it protects would ride the
      clone this feature exists to make safe and would be sealed inside its own container. Never from
      argv, where a process list and a CI log both keep it.
- [x] 🔵 **M** `scripts/vault_check.py`, appended to `GATES` in `scripts/health.py` and to
      `ROOT_ONLY_GATES` — the three-door shape `scripts/vector_check.py` established: flag off, one
      OK line saying plainly that nothing claims the private planes are backed up; flag on, the gate
      demands a witness and judges its **shape**, never its file name; a witness that exists but is
      incomplete is INVALID with each missing key named, exit 1.
- [x] 🔵 **S** `private_planes` in `15_SYSTEM/config/system.json` is the seal scope, and it is
      deliberately **not** a `zones` entry: a zone would widen `denied_prefixes()` for every reader at
      once and rewrite the door that `tests/test_phase36_doors_tell_the_truth.py` measures, for a
      reason that has nothing to do with backups.
- [x] 🔵 **M** the bug class reading did not find — and this time it was a platform, not a cipher. On
      Windows a redirected run answers `sys.stdin.isatty()` with **True** for the NUL device, so an
      `isatty()`-only guard walked straight into `getpass` and waited there for a person who was not
      there: CI would have hung rather than failed. `_passphrase` now requires a console on stdout as
      well and otherwise refuses by name, so an agent gets `REFUSED: … (rule: passphrase source)`.
- [x] 🔵 **S** `safe_rel` moved up from `scripts/base.py` to `scripts/common.py`, and
      `scripts/base.py` imports it, so the installer, the known-good backup and the vault resolve
      `..` and absolute paths under one rule instead of three quietly different ones.
- [x] 🔵 **S** every refusal is a member of the closed tuple `RULES` in
      `15_SYSTEM/scripts/backend/vault.py`, and the phase test walks the module's syntax tree to
      assert that each rule raised somewhere is declared and each declared rule is raised somewhere —
      the list cannot drift into decoration.
- [x] 🔵 **M** what the shelf guarantees, measured rather than assumed: oldest-first rotation, a
      damaged container named on `--list` while the good ones are still listed, a failed open that
      moves nothing and leaves no `.tmp` behind, and a `state_fingerprint` for the restored tree that
      `scripts/common.py` computes the same way before and after.
- [ ] 🔵 **M** what this phase deliberately did not do: no verification record under `11_CONTROL/`, no
      cross-machine restore job, no flag flip, and no seal path inside `scripts/base.py`. Those are
      one change, not four — a witness is only worth its weakest side, so the record, the CI pair and
      the flip land in the same commit or not at all. A shared evidence-gate library stays unmade
      until a second gate needs it rather than being factored around one.

*Measured 2026-11-03: `python scripts/vault.py --selftest` green; `python scripts/vault_check.py`
green with its inert verdict; `python scripts/health.py` prints a vault line where it printed none,
which is exactly the difference Phase 51 could not close; `python -m unittest discover -s tests` green
with the cases of `tests/test_phase52_vault_seals_the_private_plane.py` added, one skipped because it
needs a symlink privilege this Windows host does not grant; `python scripts/doc_report.py --write`
regenerated the measured blocks of `README.md`, `HANDOFF.md` and `00_START_HERE/START.md`.*

---

## Distribution & scale (parked) · ⛔/🔵

- [ ] 🔵 multi-host installer flags (`--host codex|opencode|gemini|claude`) — one skill tree,
      many agents; only after a second harness actually asks for it.
- [ ] ⛔ HTTP/server layer: the port is no longer refused for being complex —
      `00_START_HERE/CONSTITUTION.md` unlocks it on evidence — it is refused because MCP-over-stdio
      already answers every harness that exists, so there is neither a named consumer nor a
      measured win, and a listener without a human-approved activation record is one of the three
      lines the constitution does not unlock at any benchmark score.
- [ ] ⛔ GitHub Pages docs site: content is the bottleneck, not tooling; the README is the site.
