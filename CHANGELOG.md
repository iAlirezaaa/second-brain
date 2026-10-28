# Changelog — second-brain

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning: SemVer. Nightly-loop activity lives in `14_CANDIDATES/loop/` and is
**not** listed per commit — only shipped, human-promoted changes appear here.

## [Unreleased]

### Added
- Phase 7 — continuous improvement loop: `scripts/loop.py` (one-cycle ratchet:
  integrity/test/inbox/gap/hygiene signals → candidate report → prev-run compare;
  REGRESSED verdicts are loud, P1 exits non-zero), `skills/loop`, and a nightly
  GitHub Actions workflow committing candidate reports to `14_CANDIDATES/loop/`.
- Phase 8 — public project standard: community files (SECURITY / CONTRIBUTING /
  CODE_OF_CONDUCT / issue + PR templates / Actions dependabot), README badges,
  Keep-a-Changelog changelog, GitHub topics + Release for the existing tag, and
  the **HANDOFF standard**: `scripts/handoff.py` (machine-written §1 State
  Snapshot + frozen §8 Rules; model-owned §2–§6 refresh in place) — a formal,
  test-gated work-resume artifact any agent or human can trust.
- **Repo memory** (issue #7) — `scripts/memory.py` + `rules/memory.schema.json`:
  an append-only `15_SYSTEM/memory/lessons.jsonl` ledger with verdict, evidence,
  cue and confidence, a generated root `MEMORY.md` table, `--recall` retrieval that
  answers `NO_ENTRY` instead of inventing a lesson, `--supersedes` retirement, and a
  health gate that fails when the document drifts from the ledger.
- **One law, every host** (issue #8) — `AGENTS.md` is the canon and
  `scripts/sync_hosts.py` renders it into `CLAUDE.md`, `GEMINI.md`,
  `.github/copilot-instructions.md`, `.cursor/rules/agents.mdc` and
  `.windsurf/rules/agents.md`; `--lint` refuses a door that points at a file that
  does not exist, `--check` fails on drift, and hosts that read `AGENTS.md`
  natively get no duplicate file. Nothing in the pack requires an app: the prose
  gates (`common.is_prose`) keep README/SKILL/rules out of the note counts, so an
  installed brain (`scripts/install.py`) is green standalone with no editor, no
  network and no plugin.
- **Typed, counted candidates** (issue #9) — `rules/candidate.schema.json` plus
  `scripts/candidate_check.py`: every shelf row is `invariant` or `domain`, carries
  the real execution that probed it, and the ledger's count identity
  (`proposed == adopt + revise + drop + keep_base + open`) is checked against the
  folder, so a missing row cannot be papered over. A `verdict: proposed` row is
  legal on the shelf and never promotable.
- **Measured documents** (issues #4, #10) — `scripts/doc_report.py` writes and owns
  the block between two markers in `README.md`, `HANDOFF.md` §1 and
  `00_START_HERE/START.md`; `--check` is the sixth health gate, so a stale number
  fails CI instead of becoming project lore.
- **Control plane populated** — `11_CONTROL/skills/SKL-*` and `11_CONTROL/agents/AGT-*`
  registry records for the skills and agents this pack actually ships, created only
  through `plan → apply --approve`; a record whose body cannot be found is now a
  doctor error (`entrypoint` must resolve), and `hades.py sync` follows the pointer
  instead of keeping a copy that can drift.
- Cold-start procedures as skills: `skills/first-session` (what to do when all you
  were given is the repo URL), `skills/memory`, `skills/self-audit`.
- **Evidence portability law** — `common.clone_readable()` names the documented git
  boundary (`.kb/`, `12_RUNTIME/`, `13_LAB/`, most of `14_CANDIDATES/`, caches, key
  material, databases) with the one exception the shelf keeps (`14_CANDIDATES/loop/`),
  `candidate_check.py` refuses a row whose evidence sits behind it, and the law is
  written in `AGENTS.md` so every host projection carries it.
- **The way back as a mechanism** — `scripts/base.py`: `--save` records the last known
  good state only when every health gate is green, `--status` compares base to current
  by fingerprint, and `--recover` restores those bytes, re-proves the fingerprint and
  writes `fell_back: true` to the tracked journal `14_CANDIDATES/loop/recovery.jsonl`.
  A snapshot covers the same inventory as `state_fingerprint` — `15_SYSTEM/backups/` is
  now paperwork, so recording a base cannot invalidate the state it just recorded —
  and recovery reverts the brain, never the shelf. This is the `keep_base` piece of the
  harness2 spine: falling back is an output, not a failure.
- **Registry amendments and a real `supersedes`** (issue #12) — `hades.py edit` plans an
  amendment through the same plan → review → `apply --approve` door as creation, with an
  audit diff (`mode: amend`, `changes: {field: {old, new}}`) and `updated_at`; identity
  fields (`id`, `kind`, `created_at`, `promoted_from`) are immutable by edit, unknown
  fields are refused at the plan (a typo would be a second truth), and an amendment that
  would fail the record's own contract writes nothing. `supersedes` now does what
  `system.json` declares: the superseded record leaves the active index
  (`catalog.json`: `active: false`, `superseded_by`), `status` and `index` count it as
  retired, and `doctor` names the retirement instead of staying quiet.
- **Enumeration on content** (issue #13) — markdown-layout kinds (`news`, `wiki_note`)
  are enumerated by frontmatter (a registry-shaped `id` plus a declared `kind`), not by
  the filename `apply` happens to write: a `<ID>-<slug>.md` record can no longer be
  created by the sanctioned path and then be invisible to `show`, `list`, `link`, `index`
  and `doctor`. Markdown files round-trip without dropping fields, so `link` and
  amendments on a markdown record keep kind, edges and values.
- **The harness door** (SuperAGI reverse-engineering, phase 22) — the backend agents call
  is the protocol harnesses already speak: `15_SYSTEM/scripts/mcp_server.py`, a Model
  Context Protocol server over stdio, stdlib-only (newline-delimited JSON-RPC 2.0;
  initialize / ping / tools / resources / batches / JSON-RPC errors). Read tools open —
  `vault_search` (BM25 over the brain's prose, rebuilt per call, unicode tokenizer so
  Persian matches), `memory_recall`, `registry_list`, `registry_show`, `doctor_status` —
  and exactly one write tool, `candidate_propose`, which files a **registered** row on the
  quarantine shelf: agents propose, humans decide. Client registration examples live in
  `15_SYSTEM/integrations/` and the first real record `MCP-E1807E50` was created and
  amended through the sanctioned door itself. `doctor` now refuses an `mcp` record whose
  `.py` endpoint does not exist — a server definition whose body is missing is a rumour.
- **The backend package: SuperAGI's logic, stdlib-ported** — `15_SYSTEM/scripts/backend/`
  (`engine`, `tools_kit`, `workflows`, `schedules`, `ltm`, `search`) driven by the thin
  `orchestrator.py` CLI: the AgentExecution state machine and step loop, the BaseTool
  contract with per-actor `tool_allowlist` gating (a write tool needs `--approve` AND the
  list; empty list = zero write tools), declarative workflows validated before they walk,
  pure schedule math, an FTS5 long-term memory, and the BM25 index moved out of
  `mcp_server.py` into a single source. The first `workflow` record (`WFL-6ACDE232`,
  "standup scan") was created through the door, its `body_path` amended to the executable
  `steps.json` beside it, and run for real (`RUN-F89C1143`, COMPLETED). Tests 235 → 254,
  battery 116 → 120.
- **Runs promote to evidence; the door sees the runs** — `15_SYSTEM/scripts/runs.py promote`
  exports a finished run's append-only feed into a **registered** shelf row: the feed is
  embedded because the run directory lives behind the git boundary — evidence is exported,
  never cited across it (a run still running, an empty feed, and a second promotion of the
  same run are all refused). The harness door grew two read tools, `runs_list` and
  `runs_show` (eight tools total; `MCP-E1807E50` amended through the plan door again), so
  a harness can see what its actors did without leaving the protocol.
- **Agent runs in the disposable plane** — `15_SYSTEM/scripts/runs.py` borrows SuperAGI's
  `AgentExecution` model at git scale: `12_RUNTIME/agent_runs/<RUN-*/>` with `run.json`
  plus an append-only `steps.jsonl` feed, `start` (refuses actors the registry has never
  heard of), `step` (refuses a finished feed), `finish` (completed|failed, once),
  `list`, `show`. The registry keeps who the actor is; the runtime keeps what it did; both
  die at the git boundary — evidence that matters is promoted, never stranded. The full
  reverse-engineering map (what was adopted, what was refused, why, and the phase-2
  roadmap) is `02_WIKI/reference_maps/superagi-to-hades-map.md`.

### Changed
- `scripts/loop.py` exports the unanswered-search register it read from the local
  SQLite index as a tracked snapshot (`14_CANDIDATES/loop/gaps.jsonl`) and cites the
  snapshot, not the index, in the candidate it raises.
- `scripts/health.py` grew from two gates to six and exposes `GATES` as the measure
  that `doc_report.py` counts rather than a number someone remembers.
- README no longer asserts an app-dependent workflow; the "empty skeleton" claim
  was replaced by what is actually in the folder.

### Fixed
- CI was red on all four matrices while every local gate printed OK. The shelf row
  `cand-2026-10-27-c3-01` blamed a gap count held in `.kb/kb.sqlite`, a file that is
  gitignored by design: it existed on the machine that wrote the claim and nowhere
  else, so the evidence gate correctly refused it in a fresh clone. The row now cites
  the exported snapshot, the loop cannot write such a row again, and a test rebuilds
  the clone from `git ls-files` and runs the gate there.
- The zone/git-boundary law: `12_RUNTIME` and `13_LAB` are declared but gitignored,
  and the toolchain now says so at the boundary instead of reporting a missing zone
  as damage.
- A Persian-text regression class the hygiene gate now catches mechanically: an
  Arabic lookalike inside generated Persian prose.

## [0.0.3] - 2026-10-27

### Added
- Bilingual README (EN/FA) and bilingual engine addendum; version surfaced in
  `VERSION` + `pyproject.toml`, consistency test-gated.
- Engine v0.0.3 shipped alongside the HADES OS v3 plane skeleton (merged, not
  replaced): fenced zones 00_Inbox…90_Agent_Output, `vault-template/AGENTS.md`
  contract, rules (`rules/schema.json`, `rules/zones.json`).
- Integrity toolchain: `link_check.py`, `frontmatter_check.py`, `vault_stats.py`.
- Zone fence + write gate: `zone_check.py`, `write_gate.py`, quarantine→promote
  (`promote.py`) with audit trail.
- Local knowledge base: `kb.py` (SQLite FTS5, LIKE fallback), kb-search skill,
  gap register (unanswered searches = self-driving backlog), golden-set eval gate.
- Composite health check, weekly-ritual skills, installer (`install.py`).
- GitHub Actions CI: ubuntu+windows × py3.9+3.12, health + tests + write-gate smoke.

### Fixed
- CI write-gate smoke test made cross-shell safe (pwsh has no `test` builtin).
