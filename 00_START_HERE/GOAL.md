# Project GOAL — the durable north star

**Status:** Owner-defined project goal. This is not a feature checklist or an automatically mutable agent task.
**Owner:** Human. **Scope:** Entire Second Brain OS, all harnesses, sessions and improvement loops.

## North-star GOAL

Build a portable, independent, self-organizing second brain that serves **both a human and AI agents**: information can be captured from many sources, stored once, understood, browsed in a clear physical folder hierarchy, linked, searched and retrieved reliably with provenance. The system learns from verified experiences, advances toward better outcomes through evidence-driven improvement, and adapts its architecture to real workloads without losing information, identity, simplicity or human control.

**Success means:** the user and an agent can both locate and understand the same information; retrieval remains relevant; the repository itself is navigable; upgrades measurably improve outcomes without destructive lock-in; the owner can inspect, approve, reverse and recover every consequential change.

## Non-negotiable identity (never silently trade away)

1. **Human + agent, equal first-class clients.** Clear folders, readable Markdown, discoverable indexes and documented entrypoints matter as much as APIs, MCP and automation.
2. **Capture, classify, find and remember.** Books, links, addresses, quotes, watched/to-watch films, conversations, projects and experiences are knowledge; every item has a home, stable identity and retrievable source.
3. **One canonical fact, multiple views.** Readable canonical files and portable structured records; databases, embeddings, caches and graph projections are derived, reconstructible and replaceable.
4. **No mandatory model, harness, cloud or app.** Core works offline on modest hardware; adapters are optional.
5. **Special ideas are an asset, not technical debt.** Preserve the founding concepts including associative/ADHD discovery, evidence-led memory, governed self-improvement, agent skills, simulations and Maturity Engineering. Optimize implementations, not erase the ideas.
6. **Human sovereignty and safe evolution.** No secret promotions, dangerous writes or silent changes to mission, archives, permissions or data semantics. Preserve rollback and source traceability.
7. **Repository structure is product functionality.** Human browsing of this GitHub repository must be useful now, not only after installation. Keep root limited to entrypoints and required compatibility files; organize other material under existing owned zones without breaking links/imports.
8. **Maturity Engineering is adaptive, not a forced tech stack.** Profile each subsystem independently. Use the simplest backend, language, index and database that pass real quality, latency, cost, portability and reliability benchmarks; upgrade or downgrade with evidence and authorization.

## GOAL-driven improvement loop

For each candidate cycle:
1. Recall this GOAL and the frozen founding archive before planning.
2. Measure distance to GOAL (search quality, findability, structure, human usability, agent task success, runtime cost, reliability, privacy and reversibility); explicitly mark missing benchmarks **unverified**.
3. Identify the highest-impact bottleneck, not just the easiest new feature.
4. Compare a minimal change, alternative technologies and doing nothing. Run independent tests and representative benchmarks.
5. For changes affecting identity, founding ideas, folder ownership, canonical data, public interfaces or architecture, **STOP AND ASK** the owner *before* mutation. Show: **FROM → TO**, files/data affected, why, evidence, gains, costs, risks, alternatives, migration steps and rollback. No reply is not approval.
6. Implement bounded changes on a review branch only after the applicable approval, verify and measure again. If worse, revert to known good.
7. Keep an inspectable goal scorecard, decisions, rejected ideas and improvement evidence; never present a self-generated score as proof.

The permanent GOAL is distinct from `scripts/brain.py start --goal "a bounded task"`. A session goal must contribute to this project's GOAL and must not override it.

## Founding-idea preservation

Frozen primary-source snapshots live under [`10_ARCHIVE/foundations/`](../10_ARCHIVE/foundations/README.md). Never edit or delete snapshots; add a new version with owner-reviewed rationale. See [change governance](CHANGE_GOVERNANCE.md). The original source documents remain authoritative for their existing laws; a newer goal does not cancel them.

## Acceptance criteria for this GOAL

- Humans can find a topic from the GitHub tree and `00_START_HERE` entrypoints; agents can retrieve the same canonical item via declared APIs.
- New source formats and languages have tested import/search paths and reversible deletion/migration.
- Every improvement cycle reports measured progress or an honest blocker; no automatic changes to protected identity.
- Major architecture upgrades are proposed with before/after metrics and a tested fallback.
- Never sacrifice data integrity, security or comprehensibility for a cosmetic repository cleanup.
