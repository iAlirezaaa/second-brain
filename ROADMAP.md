# ROADMAP — iAlirezaaa/second-brain

An AI-augmented second brain: a plain-markdown vault shared by a human (curator) and AI agents (workers).
**This file is a public promise:** every idea lands here with a size estimate, gets built test-first,
and is ticked continuously by the repo's own engineers (human + agents + nightly loop).

**Status chips:** 🟢 done · 🟡 in progress · 🔵 planned
**Sizes:** S = one script, M = script + skill/report surface, L = subsystem
**Sources:** each phase cites the repos/research it came from (competitive insight, not cargo-cult).

Golden rules (tested, not aspirational):
1. Zero broken links — verify `[[target]]` exists before writing it.
2. Fenced zones — agent writes freely only where it is allowed; permission rules > AI obedience.
3. Nothing is ingested until it is linked.
4. Contradictions are recorded, never silently overwritten.
5. Every feature ships with a test before the next feature starts.

---

## Phase 0 — Repo skeleton · 🟢
- [x] README, LICENSE (MIT), .gitignore, ROADMAP · git init + first commit

## Phase 1 — Vault template + contract layer · 🟢
- [x] Fenced zone structure: 00_Inbox / 10_Projects / 20_Notes / 30_Resources / 90_Agent_Output
- [x] AGENTS.md contract + CLAUDE.md shim · index.md ground map
- [x] Frontmatter schema (rules/schema.json) + templates · structure validator test

## Phase 2 — Integrity toolchain · 🟢
- [x] link_check.py (zero-broken-links) · frontmatter_check.py (schema + ISO dates) · vault_stats.py
- [x] stdlib-only, py3.9+; unittest fixtures

## Phase 3 — Inbox triage + permission rules · 🟢
- [x] inbox-triage skill (propose placement + one-line why) · zone_check.py gate
- [x] write_gate.py (injections / zero-width chars / secrets) · promote.py quarantine→promote + audit trail

## Phase 4 — Keyword knowledge base · 🟢
- [x] kb.py — SQLite FTS5 (LIKE fallback) · kb-search skill · search-gap register (self-driving backlog)
- [x] golden-set retrieval eval gate inside the test suite

## Phase 5 — Rituals · 🟢
- [x] weekly / health / promote skills · promotions.md audit trail · composite health check

## Phase 6 — Packaging & CI · 🟢
- [x] GitHub Actions: ubuntu+windows × py3.9+3.12 (health + tests + write-gate smoke) · installer
- [x] deferred: plugin manifest (canonical skill tree via installer instead)

## Phase 7 — Continuous improvement loop · 🟢
- [x] scripts/loop.py — one-cycle ratchet: signals → candidate report → prev-run compare
      (`improved / stable / REGRESSED`); P1 exits non-zero
- [x] skills/loop — bounded protocol (≤3 cycles, stop at zero P1/P2, 2×REGRESSED = escalate)
- [x] nightly cron committing candidate reports to `14_CANDIDATES/loop/` (human promotes)

## Phase 8 — Public project standard + formal handoff · 🟡
Built from the community-hygiene audit (Community-standards checklist said: CoC, contributing,
security, templates all missing) and the agent-handoff research (AGENTS.md has no session-state
standard; the ecosystem converges on a root `HANDOFF.md`, machine-state + refresh-in-place).

- [x] SECURITY.md (scope + private advisory channel) · CONTRIBUTING.md (golden rules as PR gates)
- [x] CODE_OF_CONDUCT.md (Contributor Covenant 2.1) · issue templates + PR template · dependabot for Actions
- [x] README badges (CI / loop / version / license) + public-roadmap link — the hand-typed
      "tests: 39 green" badge was deleted, not refreshed: see Phase 12 and issues #4/#10
- [x] CHANGELOG.md — Keep a Changelog; nightly loop commits stay out of it (noise discipline)
- [x] **HANDOFF standard** — `scripts/handoff.py` + `skills/handoff`:
      machine-written §1 State Snapshot (head/dirty/tests/loop), model-owned §2–§6
      (in-flight / decisions / blockers / next-actions / pointers) refreshed in place,
      frozen §8 rules; freshness = head-match, not clock age — all test-gated.

## Phase 9 — Vault growth & decay mechanics · 🔵
*The audited gap: everything shipped so far is integrity; these are growth/decay —
the half that makes a vault a living system, not a filing cabinet. All stdlib-compatible.*

- [ ] **S** freshness/decay lint — timeless vs snapshot vs pointer claims; illegal unstated present-tense facts
- [ ] **S** orphan adoption engine — not just counting: rank candidate `[[links]]` via FTS5 overlap, agent proposes, human approves
- [ ] **S** graph audit — centrality + co-citation report (Brandes betweenness, ~60 lines): "these 3 links collapse the diameter"
- [ ] **S** title-as-claim lint — evergreen titles as APIs (Matuschak); rename flow with alias preservation
- [ ] **S** review queue — deterministically resurfaced notes weighted by age/orphan/decay, reusable daily
- [ ] **S** stale-projects archiver — `status: active` + 30d silence → archive candidate (PARA fold)
- [ ] **M** contradiction detection + reconcile flow — two-stage: FTS5 candidate pairs → agent verdict → `superseded_by` edge, never overwrite
- [ ] **M** auto-MOC — derived hub notes regenerated nightly between protected markers
- [ ] **M** near-duplicate merge with redirect stubs — merged note becomes `# merged into [[B]]`, never deleted
- [ ] **M** emergence/synthesis pass — clusters of ≥3 notes sharing an unnamed pattern → candidate synthesis page

## Phase 10 — Trust & transactional core · 🔵
*From the competitive audit (claude-obsidian's transaction spec, gbrain's open loops, the kit's secret hygiene).*

- [ ] **M** transactional write core — fingerprint-check every target file, journaled apply, `recover`
      for interrupted writes, halt on human-collision. No branches needed.
- [ ] **M** content-addressed raw capture + claim-level provenance — every claim links the source that supports it
- [ ] **S** secret masking + secret-refusing commits — backup/commit step refuses secret-looking diffs
- [ ] **S** open-loops ("waiting-for") engine — X owes Y by date; stale loops surface in the weekly/nightly ritual
- [ ] **S** postmortem ledger — every failure the loop catches yields a recorded mechanism, not just a note
- [ ] **S** ingest-completeness gate — promote may not finish until the promoted page has ≥1 inbound link
- [ ] **S** graph export — wikilink graph → JSON/GraphML for offline analysis
- [ ] **M** markdown-native task + decision ledger (Backlog.md pattern: acceptance criteria, DoD, stable IDs)
- [ ] **M** skillopt loop — LLM-judged edits to skill prompts, accepted only if they beat the current version

## Phase 11 — Distribution & scale · 🔵
- [ ] **S** BM25 recency boost + rank fusion in kb search
- [ ] **S** multi-host installer (`--host codex|opencode|gemini|claude`) — one skill tree, many agents
- [ ] **S/M** GitHub Pages from `wiki.py` output (docs site without a second docs stack; mkdocs deliberately deferred — content, not tooling, is the bottleneck)
- [ ] **S** OpenSSF Scorecard badge once Phases 8–10 land
- [ ] **L**, only with eval evidence: semantic (embedding) layer for the KB — stays refused while keyword + gap register suffice

---

## Phase 12 — A system that gets smarter: memory, probes, one law · 🟡
*Triggered by re-reading the repo from scratch, filing every finding as an issue (#3–#10), and
by the logic of `google-research/harness2` (Propose → Probe → Compose, typed dimensions,
keep-base fallback). The rows are in build order; every checked row has a test.*

- [x] **S** zone/git-boundary law corrected — the machine plane's disposable folders are
      declared and ignored, and the toolchain reports them as a boundary, not as damage
- [x] **M** evidence schema + probe with real execution — `rules/candidate.schema.json`,
      `scripts/probe.py`, `dimension: invariant|domain`, one execution per behaviour claim,
      and `verdict: proposed` legal on the shelf yet never promotable (#3, #9)
- [x] **S** ledger count identity — `proposed == adopt + revise + drop + keep_base + open`,
      checked against the folder by `scripts/candidate_check.py`
- [x] **S** SHA-1 state fingerprint + freshness — paperwork (quarantine, runtime, proposals)
      stays out of the identity, so ordinary filing never invalidates a measurement
- [x] **M** repo memory (#7) — `scripts/memory.py`: lesson ledger, generated `MEMORY.md`,
      `--recall` with a legal `NO_ENTRY`, retirement by `--supersedes`, a gate on drift
- [x] **L** independence from any app, one law per host (#8) — `AGENTS.md` is the canon,
      `scripts/sync_hosts.py` projects it with `--lint`/`--check`, prose is separated from
      notes, and the installer produces a brain that is green with no editor or network
- [x] **M** control plane populated — registry records for the pack's own skills and agents,
      create-only-through-plan, entrypoint resolution enforced by doctor
- [x] **S** measured documents (#4, #10) — `scripts/doc_report.py` owns the block between the
      markers in README / HANDOFF / START; a stale number is a failing health gate
- [x] **S** evidence that survives a clone — `common.clone_readable()` names the git boundary,
      `candidate_check` refuses a row citing behind it, the loop exports the gap register as a
      tracked snapshot, and the law is written in `AGENTS.md` so every host inherits it
      (found as red CI on all four matrices, not as a local failure)
- [x] **M** `keep_base` + `--recover` — `scripts/base.py` records a base only from a green
      house, restores those bytes on request, re-proves the fingerprint, and writes
      `fell_back: true` to `14_CANDIDATES/loop/recovery.jsonl`; `keep_base` keeps its cue closed
      so the ratchet does not re-propose what was measured worse
- [ ] **S** recovery on the probe's own initiative — today a `hurt` verdict tells the agent to
      fall back; `scripts/probe.py` does not run `base.py --recover` for it, because reverting a
      tree from an unattended measurement is a bigger permission than naming one
- [ ] **S** `hades.py edit`/`set` — the registry is create-only today, so a record can be
      filed and never amended
- [x] **S** the Python 3.9 floor as a CI fact, not a hand-measured habit — `.github/workflows/ci.yml`
      runs the six gates plus the full suite on `3.9` and `3.12` across ubuntu and windows, and
      run `40558517318` closed 4/4 green on `33522ec`

---

## Ideas consciously rejected

- **Ingestion funnels / daemons** (24/7 email/voice/Telegram connectors) — trust surface too big; a curated vault stays curated.
- **Multi-user brains / RBAC / hosted org mounts** — single-owner model by design.
- **Full vector RAG infrastructure now** — revisit only when the gap register shows keyword misses.
- **Persona / identity machinery** — theatrical complexity, no integrity benefit.
- **release-please bots** — nightly loop commits would violate conventional-commit semantics; a curated CHANGELOG is sturdier.

## How to read our progress (transparency)

- Green checkmarks = tests exist for it (search `tests/`).
- The nightly `loop` workflow files candidate reports in `14_CANDIDATES/loop/` — the raw
  next-improvement queue, promoted by the human.
- `HANDOFF.md` at repo root always answers "what's in flight right now".
