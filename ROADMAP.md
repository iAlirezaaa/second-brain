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
- [ ] Quarantine→promote promote-command (proposal JSON exists; promote helper pending)

## Phase 4 — Keyword knowledge base (local, no vector DB) · ☐
- [ ] scripts/kb.py — SQLite BM25-ish index of vault + agent session notes
- [ ] skills/kb-search SKILL.md (semantic-first: search before reading AND before creating a note — dedupe check, from obsidian-mind)
- [ ] Gap register (from manent): log every failed search to JSONL → self-driving backlog
- [ ] Retrieval eval gate: golden set fixture + recall@1 check baked into tests
- [ ] test: ingest fixture files, search returns expected rank #1, eval gate passes

## Phase 5 — Rituals · ☐
- [ ] skills/weekly (synthesis), skills/lint (health check), skills/session-log
- [ ] 90_Agent_Output/Postmortems.md pattern
- [ ] test: weekly/lint generate their artifacts deterministically

## Phase 6 — Packaging & CI · ☐
- [ ] GitHub Actions: run full test suite on push
- [ ] install script (copies vault-template + skills into $HOME/brain)
- [ ] .claude-plugin manifest for one-command install

## Phase 7 — Scale (future, only when needed) · ☐
- [ ] optional GBrain-style retrieval bridge / memory layer with identity scoping
