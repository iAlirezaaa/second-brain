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

### Changed
- `scripts/loop.py` exports the unanswered-search register it read from the local
  SQLite index as a tracked snapshot (`14_CANDIDATES/loop/gaps.jsonl`) and cites the
  snapshot, not the index, in the candidate it raises.
- `scripts/health.py` grew from two gates to six and exposes `GATES` as the measure
  that `doc_report.py` counts rather than a number someone remembers.
- README no longer asserts an app-dependent workflow; the "empty skeleton" claim
  was replaced by what is actually in the folder.

### Fixed
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
