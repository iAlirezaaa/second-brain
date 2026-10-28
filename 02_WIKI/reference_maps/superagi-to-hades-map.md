---
id: map-superagi-to-hades
type: resource
title: "SuperAGI → HADES: what to adopt, what to refuse, and why"
status: evergreen
owner: agent
topics: [architecture, agents, reverse-engineering, harness, mcp]
created: 2026-10-28
updated: 2026-10-28
---

# SuperAGI → HADES map

Reverse-engineering note for [SuperAGI](https://github.com/TransformerOptimus/SuperAGI)
(MIT, ~17.7k stars; backend `superagi/` = FastAPI + SQLAlchemy/Alembic + Postgres, Celery
workers on Redis, Next.js GUI in `gui/`). Facts below are grounded in its own sources:
`superagi/models/agent.py` (`Agent`, `agent_workflow_id`, `project_id` → `Project` →
`Organisation`) and `superagi/models/agent_execution.py` (`AgentExecution`: status
CREATED/RUNNING/PAUSED/COMPLETED/TERMINATED, `num_of_calls`, `num_of_tokens`,
`current_agent_step_id`, feed groups).

## The verdict in one sentence

SuperAGI built a **server farm that agents log into**; HADES wants a **brain that harnesses
call** — so borrow its runtime model, refuse its infrastructure, and the harness door is the
protocol harnesses already speak (MCP over stdio), not a FastAPI service.

## Adoption table

| SuperAGI concept | What it actually is there | Verdict in HADES | Where it lands here |
|---|---|---|---|
| FastAPI + Postgres + Alembic backend | a service you run, patch, back up | **refuse** — local-first, stdlib-only, offline | — (the law: `AGENTS.md` independence section) |
| Celery + Redis workers | queues for long agent jobs | **refuse** — no daemon; the nightly `loop` + GitHub Actions are the scheduler | `loop` kind (already modeled) |
| Next.js GUI | dashboard over the DB | **refuse** — the human plane *is* the dashboard (markdown + generated catalog) | `00`–`10` + `15_SYSTEM/generated/catalog.json` |
| `Agent` + `AgentConfiguration` | DB row: goal, tools, model, constraints, max_iterations | **already modeled, better** — registry records with evidence, owner, provenance, immutability | `11_CONTROL/agents` (AGT-*) |
| `AgentExecution` (RUNNING/COMPLETED/…) + steps + feed | per-run DB rows + feed events | **adopted** — phase 1: the disposable run ledger; phase 2: the engine itself (`backend/engine.py` walks declarative steps through the toolkit) | `12_RUNTIME/agent_runs/<RUN-*>/` via `runs.py`; `15_SYSTEM/scripts/backend/engine.py` |
| Toolkits / Tools | Python tool bundles installed from a marketplace | **adopted (the contract, not the marketplace)** — `backend/tools_kit.py`: BaseTool tuple, registry, and the AgentConfig `tools` list as the actor's real `tool_allowlist` (double write-gate: `--approve` AND the list) | `15_SYSTEM/scripts/backend/tools_kit.py` |
| Vector memory (Pinecone/Chroma/Qdrant + LlamaIndex) | embeddings behind a paid/remote DB | **logic adopted, vectors deferred** — `backend/ltm.py` keeps the LTM store/fetch seam over SQLite FTS5; embeddings stay behind `vector_search: false` (an owner decision, never a silent dependency) | `15_SYSTEM/scripts/backend/ltm.py`, `scripts/kb.py`, `scripts/memory.py` |
| Knowledge indexing / Resource manager | ingest docs for the agent to read | **adopt later** — same search seam, `kb.py` gains a repo-corpus ingest | phase 2 |
| Schedules / cron | DB rows + a scheduler worker | **logic adopted** — the nightly `loop` remains the scheduler; `backend/schedules.py` ports the due-math (`every_minutes` / `daily_at`) as pure functions | `11_CONTROL/loops`, `scripts/loop.py`, `15_SYSTEM/scripts/backend/schedules.py` |
| Marketplace (toolkits/knowledge packs) | install third-party bundles | **refuse** — the shelf + probes are the internal exchange; no network | `14_CANDIDATES/loop` |
| Telemetry / analytics | LLM-call/token events in a DB | **already here in its strongest form** — measured numbers re-derived by `doc_report.py`, quoted in docs, gated in CI | `scripts/doc_report.py` |
| Organisation → Project → Agent | multi-tenant SaaS scoping | **refuse** — the zones are the workspace; one owner, no tenancy | `00`–`15` zones |
| MCP-related hooks | (none — SuperAGI predates MCP going mainstream) | **the actual frontier** — SuperAGI's REST API for a GUI is the wrong client; today's harness speaks MCP | `15_SYSTEM/scripts/mcp_server.py` |

## The harness door (phase 1, implemented)

`15_SYSTEM/scripts/mcp_server.py` — Model Context Protocol over stdio, stdlib-only,
newline-delimited JSON-RPC 2.0. `initialize`, `ping`, `tools/list`, `tools/call`,
`resources/list`, `resources/read`; batches accepted; protocol version echoed; logs to
stderr only. Tools:

- read, open: `vault_search` (BM25 over the brain's prose, rebuilt per call — an index that
  can go stale is worse than one that costs 100 ms; unicode tokenizer, so Persian matches),
  `memory_recall` (the repo's own lessons), `registry_list`, `registry_show`,
  `doctor_status` (facts only; the gate itself is `scripts/health.py`).
- write, exactly one: `candidate_propose` — files a **registered** row on the quarantine
  shelf (`14_CANDIDATES/loop`), which is where an agent's writes belong. Agents propose;
  humans decide. (`candidate_check.register` prints, so its stdout is captured — a tool
  print must never land on the protocol channel.)

Resources: `AGENTS.md`, `HANDOFF.md`, `README.md`, `ROADMAP.md`, `00_START_HERE/SYSTEM_MAP.md`,
`15_SYSTEM/generated/catalog.json` — existing files only, traversal-guarded.

Client registration examples live in `15_SYSTEM/integrations/` (OpenCode, Claude Desktop).

## Agent runs (phase 1, implemented)

`15_SYSTEM/scripts/runs.py` — SuperAGI's execution model at git scale:
`start` (refuses an actor the registry has never heard of — an unaccounted actor is how a
registry starts lying), `step` (append-only feed; refuses a finished run), `finish`
(completed|failed, once), `list`, `show`. Runs live in `12_RUNTIME`, so they die at the git
boundary **by design**: the registry keeps who the actor is, the runtime keeps what it did,
and evidence that matters is promoted to the shelf or the human plane — never stranded in
machine state.

## The backend package (phase 2, implemented)

`15_SYSTEM/scripts/backend/` — SuperAGI's backend *logic* as a stdlib package, dropping the
farm and keeping the patterns:

- `engine.py` — the AgentExecution state machine (`created/running/paused/completed/failed/
  terminated`, guarded transitions) and the step loop: declarative steps walked through a
  tool registry, `max_steps` guard, `done`/`fail` steps, feed events to the caller.
- `tools_kit.py` — the BaseTool contract (`name`/`description`/`args_schema`/`writes`/`run`),
  a registry, `Context` (actor + approval), and the core toolkit: `core.fs_read`
  (traversal-guarded), `core.vault_search` (the shared search index), `core.registry_list`,
  `core.registry_show`, `core.ltm_fetch`, `core.ltm_store` (writes).
- `workflows.py` — the AgentWorkflow/AgentWorkflowStep model declarative: `validate` is the
  single gate; step types cut to what a deterministic engine can execute (`tool_call`,
  `done`, `fail`) — a model step is NOT a type: it is a human decision.
- `schedules.py` — pure due-math (`every_minutes`, `daily_at`, UTC), no daemon.
- `ltm.py` — the LTM store/fetch seam over SQLite FTS5 in `.kb/ltm.sqlite` (disposable).
- `search.py` — the BM25 index moved out of `mcp_server.py`: one source for the door and
  the toolkit.

Driver: `15_SYSTEM/scripts/orchestrator.py` (`workflow validate|run`, `tool list|call`,
`schedule due`, `ltm store|fetch`). A workflow run opens a run in the disposable ledger,
feeds every engine event into its append-only transcript, and closes it completed|failed.
Demo: the `workflow` record `WFL-6ACDE232` ("standup scan") whose `body_path` points at
`steps.json` beside it — record through the door, executable body beside the record.

## Doctor law learned from this

`check_entrypoints` now also fires for `kind == "mcp"`: an `endpoint_or_command` that ends
in `.py` is a file pointer, and the file must exist. A server definition whose body is
missing is a rumour, not a capability.

## Final folder structure — answer

The `00`–`15` zone ordering is **kept unchanged**; it is the system's identity and nothing
in SuperAGI's model justifies renumbering it. Every new piece lands *inside* an existing
zone:

```
00_START_HERE … 10_ARCHIVE      human plane — untouched (05_WORKS gained the demo workflow record)
11_CONTROL/                     + mcp/ (registry record MCP-*, created through the door)
12_RUNTIME/                     + agent_runs/ (disposable run ledger; absent in a fresh clone)
13_LAB/ 14_CANDIDATES/          untouched (shelf gained the harness-bridge row)
15_SYSTEM/scripts/              + mcp_server.py, runs.py, orchestrator.py, backend/ (package)
15_SYSTEM/integrations/         + README.md + client config examples (was empty by design)
02_WIKI/reference_maps/         + this map
```

Machine plane stays disposable except `11_CONTROL`; no new top-level zone; nothing moved.
Inside `scripts/` the arrangement is now two-layered: flat one-shot CLIs (`hades.py`,
`runs.py`, `orchestrator.py`, `mcp_server.py`, `test_hades.py`, …) over an importable
package (`backend/`) that holds the engine logic — the tests import the package in-process,
the battery copies `scripts/` wholesale, so both worlds see the same code.

## Phase 2 roadmap (next increments, in order of value)

Done already: the engine, toolkits with allowlists, declarative workflows, schedule math
and the LTM seam (see "The backend package"); run → shelf promotion (`runs.py promote`).
Remaining:

1. **Corpus for the KB** — `kb.py` gains a repo ingest (index the brain itself, not only
   `vault-template`), and `vault_search` reuses it instead of its in-memory pass.
2. **Vector embeddings behind the flag** — `vector_search: true` flips on an optional
   adapter (e.g. `fastembed` + `sqlite-vec`, both local & offline-capable); keyword stays
   the zero-dependency fallback. Interface first, dependency optional.
3. **HTTP layer, only if wanted** — a thin stdlib `http.server` wrapping the same tool
   functions for browser/remote clients; MCP over stdio remains the primary door.
4. **Scheduler seam** — wire `loop.py` to `backend/schedules.is_due` so a loop record's
   schedule decides "run now?" with the same math the orchestrator reports.
