# ROADMAP — iAlirezaaa/second-brain

An AI-augmented second brain: a plain-markdown vault shared by a human (curator) and AI agents (workers).
Inspired by: karpathy/llm-wiki gist, undefined-ui/second-brain-os, FlamingPanda101/second-brain-kit,
AgriciDaniel/claude-obsidian, MrLesk/Backlog.md, garrytan/gbrain.

Golden rules:
1. Zero broken links — verify `[[target]]` exists before writing it.
2. Fenced zones — agent writes freely only where it is allowed; permission rules > AI obedience.
3. Nothing is ingested until it is linked.
4. Contradictions are recorded, never silently overwritten.
5. Every feature ships with a test before the next feature starts.

## Phase 0 — Repo skeleton · ✅
- [x] README, LICENSE (MIT), .gitignore, ROADMAP
- [x] git init + first commit

## Phase 1 — Vault template + contract layer · ✅
- [x] Fenced zone structure: 00_Inbox / 10_Projects / 20_Notes / 30_Resources / 90_Agent_Output
- [x] AGENTS.md (the contract: zones, rules, tasks) + CLAUDE.md thin shim
- [x] index.md ground map for both audiences
- [x] Frontmatter schema (rules/schema.json) + templates folder
- [x] test: structure validator (all required files exist)

## Phase 2 — Integrity toolchain (Python, stdlib-only, py3.9+) · ✅
- [x] scripts/link_check.py — zero-broken-links enforcer
- [x] scripts/frontmatter_check.py — validates required fields + ISO date format
- [x] scripts/vault_stats.py — counts, zones, states (human or --json)
- [x] tests with unittest + sample fixtures — 13 tests green

## Phase 3 — Inbox triage + permission rules · ✅
- [x] skills/inbox-triage SKILL.md (propose placement + one-line why; never edit human zones)
- [x] rules/zones.json is already machine-readable; enforced by zone_check.py
- [x] scripts/zone_check.py — rejects human-zone moves without `approved: true`
- [x] scripts/write_gate.py — blocks injections, zero-width chars, leaked secrets
- [x] Quarantine→promote: scripts/promote.py (approved-only, frontmatter patch, audit trail)

## Phase 4 — Keyword knowledge base (local, no vector DB) · ✅
- [x] scripts/kb.py — SQLite FTS5 index of the vault (LIKE fallback if FTS5 missing)
- [x] skills/kb-search SKILL.md — search before reading AND before creating notes
- [x] Gap register: failed searches log themselves (`kb.py gaps` = self-driving backlog)
- [x] Retrieval eval gate: golden set with rank-1 asserts inside the test suite

## Phase 5 — Rituals · ✅
- [x] skills/weekly (agent preps synthesis → human decides), skills/health, skills/promote
- [x] promotions.md audit trail; script link-check guarded commands
- [x] test: promotion/refusal/audit + health composite (5 cases)

## Phase 6 — Packaging & CI · ✅
- [x] GitHub Actions: ubuntu+windows × py3.9+3.12 — health, unittest, write-gate smoke
- [x] scripts/install.py — vault + rules + skills into a fresh target, .claude/.opencode wiring
- [x] ~~claude-plugin manifest~~ (deferred: keep skill tree canonical via installer instead)

## Phase 7 — Scale (future, only when needed) · ☐
- [ ] optional GBrain-style retrieval bridge / memory layer with identity scoping
