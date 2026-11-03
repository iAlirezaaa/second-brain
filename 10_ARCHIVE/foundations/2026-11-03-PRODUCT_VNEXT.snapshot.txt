# Second Brain OS — The Cognitive Operating System
## Product vision and engineering charter · vNext proposal (3 November 2026)

> A second brain that remembers accurately, discovers unexpected connections,
> completes useful work, and improves through measurable experience — without
> taking ownership or control away from its human.

**Status:** aspirational product target; no claim that every capability below is shipped.
**Public name:** Second Brain OS. **Engine codename:** HADES.
**Operating mode:** local-first, inspectable, offline-capable, modular, evidence-driven.

**GitHub About:** Your local-first cognitive operating system: memory, knowledge, skills, agents, and verified self-improvement — searchable, executable, portable, and under your control.

## What it does

Traditional knowledge apps store information; agent frameworks execute tasks;
retrieval systems index text. Second Brain OS closes the operational loop:

**Capture → Understand → Relate → Recall → Plan → Simulate → Execute → Verify
→ Handoff → Learn → Re-evaluate.**

It must answer: What did I mean? Where is the source? What should happen
next? Can we reuse an existing skill? Did the last change genuinely help?
Not knowing is an admissible result.

## Non-negotiable contracts

1. **Human sovereignty:** inspect/export/edit/delete, unbundled portable data.
2. **Truth and provenance:** source, observation time, event time, confidence,
   contradiction/supersession and classification; hypotheses never become facts.
3. **No permission by persuasion:** high-risk writes, data sharing, training,
   deployment, new tools and skill promotion require runtime checks and human
   authorization; prompts cannot grant permission.
4. **Reversible evolution:** before/after benchmarks, backup, migration preview,
   rollback and independent validation on structural changes.
5. **Graceful degradation:** a CPU-only offline laptop can capture, search,
   manage tasks and skills, and produce handoffs. No paid service prerequisite.
6. **Measurable efficiency:** optimize task success, correctness, latency,
   resource usage, privacy and maintainability together.
7. **No invisible activity:** sessions, denials, attempted actions, run costs,
   open tasks, proposals, blockers and experiments remain inspectable.
8. **Swappable components:** the data contract survives model, graph store,
   harness, UI, index and programming-language changes.
9. **Prune as well as grow:** expire stale memory, retire unused plugins,
   consolidate duplicate skills, rebuild indexes and challenge graph schemas.

## Cognitive services

| Layer | Promise | Proposed mechanism |
| --- | --- | --- |
| Capture | Quick collection from notes, links, chat, files and devices | Ingestion adapters, idempotency, explicit provenance and consent |
| Memory | Episodic, semantic, procedural, project, agent, preference and task memory | SQLite/Markdown canonical records; scopes, expiry, contradiction |
| Retrieval | Search what matters, not merely matching words | FTS5/BM25 + optional semantic/entity/temporal/graph signals |
| Context | Keep model context lean | L0 directory abstracts, L1 overviews, L2 cited source passages |
| Graph | Relations survive changing facts | Bi-temporal claims, schema versions and reviewed migrations |
| Planner | Every run has explicit intent | Pre-work to-do, dependencies, success checks, resource budgets |
| Runtime | Agents are accountable | Durable checkpoints, permissions, audit events, retry/cancel |
| Skills | Reuse, combine and improve procedures | Progressive disclosure, typed contracts, compositional DAGs |
| ADHD | Creative cross-domain retrieval | Evidence-backed weak ties and hypothesis scoring |
| Twin World | Simulate-before-apply | In-memory twin → copy-on-write sandbox → isolated workers |
| Learning | Evolve without self-deception | Proposals, independent evals, user review, canary, rollback |
| Interface | Actually usable, not only folders | Unified CLI, MCP, optional GUI/browser/mobile |
| Governance | No surprises | Least privilege, recovery drill, consent, auditable boundaries |

### Data contracts instead of folder lock-in

Each canonical item may carry identity, kind, content/source references,
actor and owner scope, sensitivity, occurred/observed time, valid interval,
confidence, content hash, relations, version and status. These are typed and
schema-versioned, with a non-destructive migration path.

A personal memory can be a film to watch, a film already watched, an address,
a website, a book, a quote, a conversation, a preference, a plan or an anecdote.
The user should not need to pick a directory or ontology before capture.
Many retrieval views may point to one source without multiplying its data.

## Agent operating contract

Every session, regardless of harness:

1. Discover existing skills from metadata; inspect the relevant skill before
   reimplementing any procedure.
2. Create a persistent to-do list before taking a work action. Declare success
   criteria, actor identity, permissions, resource budget and risks.
3. Execute one bounded step and record tool name, evidence, duration, cost
   and decision. Prevent tools from running across unapproved boundaries.
4. Add newly discovered tasks immediately, and visibly reprioritize.
5. Reconsider assumptions and the plan after each milestone.
6. Simulate risky actions in Twin World before modifying real state.
7. Verify results with independent evidence, not the generating model alone.
8. Always produce a handoff, including failures and unresolved tasks.
9. Produce a **skill proposal after every session**. A skill is promoted or
   updated only if reusable, evaluated and confirmed successful by the user.
10. When scripting, batching or a plugin would reduce recurrent agent work,
    propose that capability via a visible queue, including risk and benchmark.

Runtime APIs and gates must enforce the contract. Natural-language agent
instructions alone do not establish enforcement.

## Agent identity and permissions

Each agent has a stable ID, a role identity, task domain, memory scope,
read/write boundaries, approved tools, maximum spending/compute budget,
model/harness adapter and review policy. A manager plans; a researcher
collects evidence; a builder makes changes; a critic independently evaluates;
a memory keeper distills; a skills architect composes; a simulator predicts;
a security guardian vets risk; an ADHD explorer proposes distant connections.
No agent can approve its own privilege escalation or sign its own evaluation.

Details: see AGENT_TEAM_VNEXT.md.

## ADHD — Associative Discovery across Heterogeneous Domains

ADHD deliberately explores weak ties across different knowledge domains rather
than relying only on hierarchical nearest-neighbor search. Candidates can be
based on shared constraints, sparse entities, alternative analogies, temporal
coincidence and non-obvious graph paths. Every bridge has a reason, original
citations and an explicit uncertainty label. User feedback controls novelty
versus precision.

The first CLI implementation is **lexical, cross-zone and read-only**.
It is a baseline for later semantic and graph versions, not a reasoning model
or a statement about a person's medical condition.

## Skill algebra

A skill has versioned inputs, outputs, constraints, permissions, side-effects,
dependencies, evidence, fixtures, owner and success rate. Composite skills are
DAGs, for example:

- research + source verification + synthesis = cited brief
- capture + entity linking + temporal retrieval = memory assistant
- change proposal + Twin World + CI + approval = safe upgrade

The compiler must detect permission escalation, cycles, hidden side effects,
schema incompatibility and conflicting writers before a composite runs.
Generated skills are quarantined until the human approves.

## Twin World progression

- **Twin 0, implemented in this proposal:** deterministic task transitions in
  memory, with no tool executions or disk writes.
- **Twin 1, planned:** full isolated copy-on-write workspace, mock connectors,
  reproducible fixtures and before/after filesystem diffs.
- **Twin 2, planned:** container/VM sandbox, restricted network/filesystem,
  resource budgets, checkpoint/resume and rollback proof.
- **Twin 3, research:** calibrated counterfactual planning for multi-agent
  schedules, costs and long-horizon actions.

A simulated green result is never proof of real success.

## Four operating profiles

| Profile | Resources | Mandatory capability |
| --- | --- | --- |
| Tiny | CPU-only, no network | Capture, FTS5, deterministic tasks, skills, handoff |
| Local | CPU + optional small LLM | Local agent, retrieval, optional embeddings |
| Studio | Local GPU(s) | Reranking, sandboxes, controlled model experiments |
| Hybrid | Multiple hosts / approved cloud | Durable remote workers and device sync |

All profiles share portable canonical records. The optional integrations
cannot change the low-resource fallback contract.

## Proposed SLOs — targets, NOT current measured results

Use a frozen dataset of at least 10,000 notes and 1,000 labelled search
queries plus multilingual/Persian fixtures. Publish hardware specs and
repeated runs. Initial reference-CPU targets:

- CLI cold startup p95 under 500 ms, with no ML SDK import.
- Indexed keyword retrieval p95 under 150 ms on 10k notes.
- Small-note capture p95 under 250 ms excluding remote fetch.
- Local task transition p95 under 50 ms with SQLite WAL.
- Zero unapproved writes or scope leaks in adversarial tests.
- Recoverable crash-injection success at least 95% in a defined test suite.
- Hybrid retrieval must beat frozen BM25 on both Recall@10 and MRR, with
  acceptable latency and no privacy regression.
- Each successful agent run has a to-do, evidence, independent verdict,
  user confirmation and handoff; abandoned jobs are detected.

Additional measurements: false links, hallucinated facts, user corrections,
time-to-task completion, memory size, GPU minutes and maintenance costs.
No target above should be marketed as achieved until a reproducible report
exists.

## Architectural choice

**Keep the portable Markdown + Python/SQLite core for now.** Do not rewrite
because another project's architecture seems attractive. Split into
core, memory, retrieval, agent runtime, skills, twin, evaluation, connectors,
security and interfaces. Move measured hot paths to Rust, Go or native
extensions only with reproducible performance gains and a fallback.

Adopt optional, license-checked patterns from OpenViking (context levels),
Graphiti (bi-temporal claims), Mem0 (hybrid search), Letta (memory editing),
LangGraph (durable execution) and Laya (typed fast decisions). They are
references or potential adapters, not implied installed dependencies.

## Rollout order

**P0:** repair red gates; unified CLI; skill-first start; pre-work to-do;
dynamic tasks; handoff; user-approved completion; skill draft; Twin 0; in-memory file-overlay Twin 1a;
ADHD lexical bridge; tests and examples.

**P1:** fast capture; personal memory types; validated ingestion;
time-aware, entity-aware retrieval; encrypted backup and cross-host restore.

**P2:** durable agent checkpoints; queue/schedule; kill switch; per-actor
capabilities; budget/observability; real-time progress and failure replay.

**P3:** optional semantic/graph memory with hybrid evaluation; progressive
context; verified Persian/multilingual benchmarks; incremental indexing.

**P4:** skill composition and controlled promotion; Twin 1/2; independent
benchmark harnesses; supervised fine-tuning; schema evolution, canaries,
regression-triggered rollback.

**P5:** portable app distribution, mobile/browser capture, optional dashboard,
multi-device sync and collaboration.

## Definition of done

Someone can capture information now, recover it correctly months later,
launch a bounded agent task, see progress and cost, verify a result, teach
a reusable skill only with approval, and recover safely from failure — on
an ordinary offline computer.

Passing unit tests is not, by itself, proof of this product definition.
