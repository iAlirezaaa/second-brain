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
