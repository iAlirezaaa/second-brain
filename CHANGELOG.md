# Changelog — second-brain

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning: SemVer. Nightly-loop activity lives in `14_CANDIDATES/loop/` and is
**not** listed per commit — only shipped, human-promoted changes appear here.

## [Unreleased]

### Added
- Phases 31–34 — **private source memory**: `15_SYSTEM/scripts/sources.py` imports one
  explicitly selected UTF-8 file (or a reviewed manifest) into `.brain-data/sources/<id>/`
  as authoritative raw bytes plus metadata (kind, origin, filename, import time, format,
  checksum); the id is content-addressed, so re-import is idempotent and changed content is a
  new record. `rebuild` validates every record and atomically replaces a disposable SQLite
  index; `search` is BM25-style with a legacy scan path and returns provenance with each hit.
  Conversation adapters read Codex JSONL, Claude Code stream JSON and Cursor stream JSON,
  indexing user/assistant text only and refusing mixed sessions.
- **Evidence-backed private lessons** — `backend/learning.py` accepts a proposal only with an
  exact quote present in an imported source, evaluates source checksum + quote + whether the
  query retrieves that source, and writes a receipt only after explicit `--approve`; `recall`
  returns approved lessons with their origin. The evaluation says what it does not prove.
- **Retrieval measurement** — `backend/retrieval_eval.py` reports mean recall and MRR on an
  independently curated case set and refuses to compare reports with different cases, limits
  or corpus hash; any regression fails the verdict.
- **Transfer between devices** — `backend/source_sync.py` previews an explicit folder copy,
  names conflicts (same kind + origin, different content; copied only with
  `--allow-conflicts`), keeps both versions, previews approval receipts but imports them only
  with `--include-approvals`, and `verify-copy` compares every record byte-for-byte.
- **Capability catalogue and install gate** — `15_SYSTEM/scripts/capabilities.py` inventories
  active registry skills/plugins/MCP records/extensions and built-in tools with origin,
  permissions, harness approvals and installation state; `backend/install_skill.py` plans by
  file digest and applies only with `--approve`, never replacing a directory.
- **Default read boundary** — `backend/access.py` refuses `.env`, key/credential filenames,
  `.git`, `secrets`, the runtime/lab/candidate/backup zones and client metadata in file reads,
  search and MCP resources; MCP resources now serve only the advertised list. This is a
  tool-level path guard, not OS access control or a secret scanner.
- MCP door grows from 8 to 12 tools: `source_search`, `lesson_propose`, `lesson_recall`,
  `capabilities`. Write tools remain proposal-only; approval stays local.
- **The eight memory planes, mapped and gated** (phase 26, charter §5) — `system.json` →
  `memory_planes` declares per plane the tracked store a clone must open, the disposable store
  that may be absent by design, the reader, the proving test and the map row;
  `02_WIKI/reference_maps/eight-memory-planes.md` is the human map with a measured inventory of
  what the clone can open today; `scripts/plane_check.py` is the seventh health gate and refuses
  a dropped plane, a missing tracked store, an empty folder without `.gitkeep`, or a
  reader/test/map that no longer exists. Disposable stores (`12_RUNTIME/`, `.brain-data/`,
  `.kb/`) are reported, never required. Gaps filed as #24 (no contradiction detection), #25
  (lessons carry no plane field); #20 keeps the conversation-extraction path and `kb.py` open.
- **`kb.py` searches this brain's own prose** (phase 27, charter §1) — `ingest` now indexes the
  tracked, clone-readable human plane instead of `vault-template`: the machine plane
  (`11_CONTROL/`–`15_SYSTEM/`), the template, dot-folders and rendered agent doors are excluded
  by the same boundary `common.clone_readable()` declares. Frontmatter is stripped before
  indexing, so a snippet opens on the first sentence instead of on `id:`/`topics:`; matching
  folds case and NFKC and maps Arabic `ي`/`ك` to Persian `ی`/`ک`, while displayed text keeps
  its original bytes. Every hit carries its zone and title; a missing index prints one line
  instead of answering, and an index built by an older corpus rule is refused until
  re-ingested. Measured here: 43 notes into a 1.4 MB index, ingest 81 ms, median query
  3.8 ms over 40 runs (max 5.9 ms); an installed home indexes its own 28 notes. The phase-4 golden gate is repointed at
  repo paths and `tests/test_phase27_repo_corpus.py` adds ten tests (boundary, installed home,
  shared golden fixture).
- **Retirement is visible where a record is read** (phase 27 item 2) — measured before the
  change in a scratch vault: `list` showed 4 rows, 1 retired, 0 markers; `search --query
  provider` returned 5 hits, 1 of them the retired record's file, 0 markers. Now `list` prints
  `records: N (active A, retired R)` and appends `[retired by ID]` to the retired row;
  `search` appends the same marker to the retired record's own file and names the count in its
  summary; `show` prints `# retired by: ID`; the MCP door (`registry_list`, `registry_show`)
  carries `superseded_by` / `retired by`. Nothing is deleted or hidden — retirement stays a
  verdict, not a delete. Four tests cover the three CLI surfaces and the MCP door.
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
- **Amendments** (issue #12) — `hades.py set --id --field --value [--approve]`: an applied
  registry record can now be corrected instead of duplicated. It goes through the same
  plan → `apply --approve` gate as a creation, `id` / `kind` / `created_at` are immutable,
  an amendment that breaks the record's own contract or strands its `entrypoint` is refused
  before a byte moves, a plan whose record moved since it was written is refused as stale,
  and every accepted amendment appends `field, from, to, when, plan` to the record's own
  `amendments` trail. A field neither the record nor its kind's schema has ever heard of is
  refused at the plan — a typo would silently add a second truth.
  `tests/test_phase22_amend_a_record.py` is red without it.
- **Retirement that the index honours** (issue #12) — `supersedes` was declared in
  `15_SYSTEM/config/system.json` as "replaces a record; superseded leaves the active index"
  and `link` accepted it, while `index` listed both records and `doctor` printed `errors: 0`
  (measured: 12 before the link, 12 after). Now `cmd_index` moves a superseded record into a
  `superseded` block that names who retired it, `cmd_doctor` counts active records, prints the
  retirements and errors when a record supersedes itself, and `cmd_status` reports the split.
  Nothing is deleted — `list` still enumerates every record on disk; retirement is a verdict,
  not a shredder. `tests/test_phase23_superseded_leaves_the_index.py` is red without it.
- `02_WIKI/decisions/` has its first inhabitant: *Gates enforce laws or they are comments*
  (`WIK-B7ED0084`), written through `plan` → `apply --approve` and amended through `set` for its
  own provenance — the instruction in `AGENTS.md` to "record decisions in `02_WIKI/decisions`"
  finally carried out, with the lesson of the same pass that built the tools it describes.
  `doctor` counts it (`registry records: 13`, `errors: 0`, `by kind: {"wiki_note": 1}`); the
  generated index it also lands in stays local paperwork, outside the git boundary.
- **The owner's charter is a tracked file** — `00_START_HERE/PROJECT_CHARTER.md`: the
  project brief (15 sections — vision, app-independence, the reference repos, the
  folder/ID law, the eight memory planes, the improvement cycle, agent and skill
  management, the repository workflow, per-repo memory, PR review, conversation
  knowledge, English docs, fourteen laws, the expected outcome, the order of work)
  existed only in a chat, where no future agent could read it. It is now read-before-acting
  item (2) in `AGENTS.md`, with the law that **the charter outranks the task**: a conflict
  is filed on the shelf with its section number, not resolved silently by the last editor.
  Text is verbatim except seventeen ZWNJ insertions the Persian hygiene gate requires
  (`Skillها` → `Skill‌ها`); `qc` measures clean across 36 files and `doctor` at
  `errors: 0 | warnings: 0`.
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
  `steps.json` beside it, and run for real against the live repo (COMPLETED, 2 steps).
  Tests 235 → 254, battery 116 → 120.
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
- **The golden retrieval gate's cases are decidable, not coin flips** (the phase-4 gate,
  found while measuring phase 27 item 3) — four of the five cases sat within 0.14 BM25 units
  of their runner-up, and `plan apply approve` lost `START.md` to `GUIDE_FA_EN.md` by 0.0006
  after ordinary documentation growth shifted the index's global average length. Both documents
  genuinely discuss the pipeline, so the case was asking the ranker to break a tie it had no
  evidence to break. The five cases were re-picked by measured margin (1.23–3.74) and a new
  test holds a 0.5 floor, so a case that becomes ambiguous later fails as a *case* defect
  instead of flipping silently. Corpus, tokenizer and ranker are unchanged.
- **No recency ranker in the prose search** (phase 27 item 3) — the roadmap allowed a BM25
  recency boost only behind a measured win, so it was measured first and refused. 3 of 43
  corpus notes declare `updated:`; the other 40 fall back to mtime, which in a clone is a
  single checkout day (measured: one distinct fallback date). A recency-aware re-rank over
  the shared golden set moved recall@1 and MRR by 0.000 at every weight from 0.05 to 1.0.
  `tests/test_phase27_repo_corpus.py` pins the contract that mattered: a six-year-old exact
  match still outranks a fresh weak one. Revisit only when every note carries a true date and
  labeled cases exist where freshness, not relevance, decides the order.
- `scripts/loop.py` exports the unanswered-search register it read from the local
  SQLite index as a tracked snapshot (`14_CANDIDATES/loop/gaps.jsonl`) and cites the
  snapshot, not the index, in the candidate it raises.
- `scripts/health.py` grew from two gates to six and exposes `GATES` as the measure
  that `doc_report.py` counts rather than a number someone remembers.
- README no longer asserts an app-dependent workflow; the "empty skeleton" claim
  was replaced by what is actually in the folder.

### Fixed
- A registry record in a human zone was judged as a broken note (issue #14). `apply` writes a `wiki_note` as
  markdown into `02_WIKI`, and an installed brain scans its own root (`health.py --vault .`), so
  the first decision record this repo filed came back `INVALID: missing field: type … invalid
  status: 'draft'` — the note contract and the registry contract both claiming one file. The
  tempting fix (write a `title`, a `type` and a note `status` next to `name`, `kind` and a registry
  `status`) would have given one field two truths nobody keeps in step, so the gate now picks the
  contract from the file's content using the recognizer the registry already uses, and reads the
  record's required fields and status vocabulary from `15_SYSTEM/config/system.json` and
  `15_SYSTEM/schemas/manifest.schema.json` instead of retyping them. It bites harder, not softer: a
  record with a status its kind disallows, or missing its identity, is refused, and a file that
  claims a registry `kind` with an id the registry cannot enumerate is named as an orphan.
  `tests/test_phase24_a_record_is_not_a_note.py` (13 tests) is red without it.
- Amending or linking a markdown record deleted its prose — found by dogfooding `set` the moment
  it shipped. The body was *rendered from* `notes`/`claim`, but the reader parsed only the
  frontmatter, so the next write-back re-rendered the file from fields that no longer held the
  paragraph. Those fields now round-trip, and
  `test_an_amendment_does_not_lose_the_prose_of_a_markdown_record` is red without the fix.
- A markdown record was created invisible (issue #13): `news` and `wiki_note` land as
  `<ID>-<slug>.md`, while `iter_records` admitted a markdown record only when its stem was
  exactly `note`. `apply` wrote the record, then `show`, `list`, `index` and `doctor` answered
  that nothing existed — and `doctor` printed `errors: 0`, which is a silent gate, not a clean
  house. Enumeration is now by content (a registry-shaped `id` **and** a declared `kind`), a
  body (`OVERVIEW.md`, `SKILL.md`) stays a body, and `link` round-trips relations through the
  markdown writer instead of dropping them on the floor.
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
