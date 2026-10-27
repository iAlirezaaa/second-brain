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
| `AgentExecution` (RUNNING/COMPLETED/…) + steps + feed | per-run DB rows + feed events | **adopt** — the one thing genuinely missing here | `12_RUNTIME/agent_runs/<RUN-*>/run.json` + `steps.jsonl` via `15_SYSTEM/scripts/runs.py` |
| Toolkits / Tools | Python tool bundles installed from a marketplace | **already modeled** — `skill`/`command`/`hook` records + `approved_for_harness_ids`; a marketplace is network + trust debt | `11_CONTROL/skills`, `11_CONTROL/commands` |
| Vector memory (Pinecone/Chroma/Qdrant + LlamaIndex) | embeddings behind a paid/remote DB | **defer behind the flag** — `vector_search: false`; keyword FTS5/BM25 is the honest floor today; embeddings are an adapter away, never a dependency | `scripts/kb.py` (FTS5), `scripts/memory.py` (recall) |
| Knowledge indexing / Resource manager | ingest docs for the agent to read | **adopt later** — same search seam, `kb.py` gains a repo-corpus ingest | phase 2 |
| Schedules / cron | DB rows + a scheduler worker | **already modeled** — `loop` kind with schedule; nightly loop writes the gap register | `11_CONTROL/loops`, `scripts/loop.py` |
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

## Doctor law learned from this

`check_entrypoints` now also fires for `kind == "mcp"`: an `endpoint_or_command` that ends
in `.py` is a file pointer, and the file must exist. A server definition whose body is
missing is a rumour, not a capability.

## Final folder structure — answer

The `00`–`15` zone ordering is **kept unchanged**; it is the system's identity and nothing
in SuperAGI's model justifies renumbering it. Every new piece lands *inside* an existing
zone:

```
00_START_HERE … 10_ARCHIVE      human plane — untouched
11_CONTROL/                     + mcp/ (registry record MCP-*, created through the door)
12_RUNTIME/                     + agent_runs/ (disposable run ledger; absent in a fresh clone)
13_LAB/ 14_CANDIDATES/          untouched (shelf gained the harness-bridge row)
15_SYSTEM/scripts/              + mcp_server.py, runs.py
15_SYSTEM/integrations/         + README.md + client config examples (was empty by design)
02_WIKI/reference_maps/         + this map
```

Machine plane stays disposable except `11_CONTROL`; no new top-level zone; nothing moved.

## Phase 2 roadmap (next increments, in order of value)

1. **Corpus for the KB** — `kb.py` gains a repo ingest (index the brain itself, not only
   `vault-template`), and `vault_search` reuses it instead of its in-memory pass.
2. **Vector embeddings behind the flag** — `vector_search: true` flips on an optional
   adapter (e.g. `fastembed` + `sqlite-vec`, both local & offline-capable); keyword stays
   the zero-dependency fallback. Interface first, dependency optional.
3. **HTTP layer, only if wanted** — a thin stdlib `http.server` wrapping the same tool
   functions for browser/remote clients; MCP over stdio remains the primary door.
4. **Run → shelf promotion** — `runs.py finish --promote` drafts a candidate row from the
   run's feed, so a run that learned something leaves the disposable plane.
5. **Workflows** — SuperAGI's `AgentWorkflow` steps as declarative `loop` records the
   runtime can execute step-by-step (deterministic steps only; LLM steps stay human-gated).
