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
Current floor, measured at the time of writing: **297 unittests, a 120-check HADES battery,
6 health gates, CI on ubuntu+windows × 3.9/3.12, 26 recorded lessons.**

---

## Phase 25 — The charter audit: the yardstick measured · 🟡 (next)

*Source: the charter itself (§15: the order of work) and the handoff's own admission that the
charter "has not been audited against the repo yet". A charter nobody has measured against is
decoration.*

- [ ] **S** Walk `00_START_HERE/PROJECT_CHARTER.md` §1–§15 section by section; for each, run or
      name the command that shows whether the repo honours it today. Output: an audit table on
      the shelf or in `02_WIKI`, every row carrying evidence (command + output), `NO_ENTRY`
      where a section is unimplemented.
- [ ] **S** File every gap as a GitHub issue with the section number and the proving command —
      issue-then-fix, the repo's own §8 workflow.
- [ ] **S** Amend this roadmap from the audit's verdicts: a phase that the charter refuses is
      moved to ⛔ with the section number; a charter section with no phase gets one.

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

## Distribution & scale (parked) · ⛔/🔵

- [ ] 🔵 multi-host installer flags (`--host codex|opencode|gemini|claude`) — one skill tree,
      many agents; only after a second harness actually asks for it.
- [ ] ⛔ HTTP/server layer: refused while MCP-over-stdio answers every harness that exists —
      a port, a daemon and a key surface are the SuperAGI stack this repo exists to not need
      (charter §2). Revisit only with a named consumer.
- [ ] ⛔ GitHub Pages docs site: content is the bottleneck, not tooling; the README is the site.
