# Technical research and adoption ledger — November 2026

The goal is to outperform relevant baselines for a user's tasks, not to copy
all of another project's dependencies. Code reuse must pass license review,
security review, performance profiling and integration tests.

| Project | Reusable idea | What should change in Second Brain OS | Adoption status |
| --- | --- | --- | --- |
| OpenViking — https://github.com/volcengine/OpenViking | Virtual filesystem, resource/memory/skills context, L0/L1/L2 progressive loading, scoped retrieval | Abstracts and topic-scoped recall | Research only |
| Graphiti — https://github.com/getzep/graphiti | Episode/entity/fact graph and bi-temporal validity | Contradiction, time-sensitive memory and history | Research only |
| Mem0 — https://github.com/mem0ai/mem0 | Hybrid retrieval using semantics + BM25 + entity matching | Run a measured hybrid retriever against FTS5 baseline | Research only |
| Letta Code — https://github.com/letta-ai/letta-code | Editable memory and separate reflection/memory workers | Distinguish identity memory, task memory, procedures and execution control | Research only |
| LangGraph — https://github.com/langchain-ai/langgraph | Checkpointed agent execution, human interrupts, resume and long-term stores | Durable agent state machine and review checkpoints | Research only |
| Agent Skills — https://github.com/agentskills/agentskills | SKILL.md metadata-first progressive disclosure | Avoid reading every skill body; enforce skill I/O and versions | Partial existing skills; new lifecycle prototype |
| Laya — https://github.com/NandhaKishorM/laya | Typed fast choice/score/noul models and routing | Cheap optional intent, risk and task routing with confidence gates | Separate PR #65; NOT in main |
| Temporal Python — https://github.com/temporalio/sdk-python | Durable workflows, activities, retries and timeouts | Evaluate if local queue recovery is insufficient | Research only |

## Candidate-by-candidate decision gate

Before importing or copying code:
1. Name one user-visible problem and the failing baseline.
2. Record original license, compatible obligations, transitive dependencies,
   security footprint, minimum Python version and offline operation.
3. Freeze a public benchmark corpus; add Persian and long-context cases.
4. Profile current candidate and proposed alternative on the SAME machine.
5. Compare task success, precision/recall/MRR, p50/p95, peak RAM, disk, startup
   and operations burden. Report at least three repeats and error bars.
6. Test privacy boundaries, incorrect confidence, dangerous tool execution,
   data corruption, crash recovery and false success claims.
7. If the improvement is meaningful, implement behind a feature flag, with
   a fallback, migration, owner decision record and roll-back method.
8. If it is not meaningfully better, document the negative result and keep
   the lighter implementation.

## Immediate design conclusions

- **Keep Markdown as a human-editable export/source**, not the only index.
  FTS5 already exists; add incremental hashing, per-scope indexing and
  profiling before importing a heavyweight graph DB.
- **Use SQLite for small durable events and task state.** WAL and explicit
  transactions are available with Python's standard library and need no
  server. Never commit private database contents.
- **Do not adopt a heavy framework for orchestration before jobs need it.**
  First create a stable event/tool contract; only then benchmark LangGraph
  and Temporal as interchangeable optional engines.
- **Keep graph claims temporal and reversible.** Build graph views from
  canonical facts; evaluate schema revisions inside an isolated Twin World.
- **Separate associative novelty from factual retrieval.** ADHD proposals
  must show their original paths and expose false-positive rates.
- **Avoid a fully automatic self-training loop.** Training needs an approved
  dataset, consent, holdout, leakage audit, reference baseline and rollback.
- **Do not merge PR #65 solely because it added code.** Real Laya inference
  still needs package/model installation and end-to-end benchmarks.

## Initial reproducible experiment backlog

1. Retrieval: FTS5/BM25 vs hybrid on 1k and 10k notes, including Persian.
2. Memory: recall across restarts, contradicted facts, stale claims and erasure.
3. Task runtime: crash injection during event write, handoff, close, recovery.
4. Skill reuse: time/cost saved by metadata-first discovery vs naive all-skills load.
5. ADHD: cross-domain relevance and useful-novelty feedback, with cited reasons.
6. Twin: no writes to real data, deterministic output, failed-action replay.
7. Security: prompt injection, symlink traversal, cross-user scopes, privilege escalation.
8. Resource profiles: cold start, idle RAM and latency on CPU-only and GPU hosts.

These experiments are required evidence, not claims of completed benchmark runs.
