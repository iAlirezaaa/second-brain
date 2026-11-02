# Brain CLI — Operator Quickstart
## vNext prototype · Python 3.9+ · standard library · no model download

Run all commands from the repository root. This command-line interface is a
real working prototype for **private task sessions**, not yet a replacement for
the existing HADES, KB, memory or orchestration CLIs.

### Check the system
    python scripts/health.py
    python -m unittest discover -s tests
    python scripts/brain.py --help

### Find existing skills before doing work
    python scripts/brain.py skills --query "research sources"

Only skill names/descriptions load in this step. Read the matching SKILL.md
before acting; the CLI does not run skill instructions.

### Begin a task; the to-do list exists immediately
    python scripts/brain.py start --goal "Prepare a source-backed technical brief" --actor human

Copy the generated SES-... ID from the output. Existing registered AGT-XXXXXXXX
agents can also be named in --actor. Unregistered actors are refused.

### Inspect and dynamically update the plan
    python scripts/brain.py status SES-XXXXXXXXXXXX
    python scripts/brain.py add SES-XXXXXXXXXXXX --task "Verify external claims"
    python scripts/brain.py add SES-XXXXXXXXXXXX --task "Compare retrieval baselines"

The initial five tasks include skill review, plan, bounded work, verification
and handoff. New tasks are persisted as the work evolves. The task ID appears
in the status output. It is **not** always 1–5.

### Complete a task with evidence
    python scripts/brain.py done SES-XXXXXXXXXXXX TASK_ID --evidence README.md

Replace TASK_ID with the actual number. The evidence must point to a real
file inside the brain and must not be a private runtime/database path.
Complete skills and plan prerequisites before work or verification.
**This only records the evidence path; it does not independently prove that
the file establishes the claimed result.** The human/evaluator must check.

### ADHD associative discovery
    python scripts/brain.py adhd --query "animation storyboard"

Outputs cross-zone pairs sharing observable terms and source paths.
It does not invent an association when there is insufficient evidence.
This v0 is lexical, not a semantic graph model.

### Twin World 0 — no real execution
Place a JSON file OUTSIDE the repository, for example in the system temp
directory, containing:

    [
      {"op": "add_task", "summary": "Check a possible memory-index upgrade"},
      {"op": "add_task", "summary": "Benchmark the old and new search"}
    ]

Then run:

    python scripts/brain.py twin SES-XXXXXXXXXXXX --plan /path/to/twin-plan.json

The simulator loads the session task state read-only, applies only allowed
task transitions in memory and reports the expected differences. It executes
zero tools and makes zero file writes. It is **not** yet a full app or VM twin.
Allowed operations are add_task and complete_task; no shell/tool operation.

### Handoff is mandatory, even for blocked sessions
    python scripts/brain.py handoff SES-XXXXXXXXXXXX --summary "What changed and what was verified" --next "Verify the pending benchmark" --risks "One source remains unverified"

A Markdown handoff is written to a local, gitignored directory:
.brain-data/operator/handoffs/SES-....md.
Record unfinished work explicitly. This is personal session data, not tracked
project evidence; export it separately if a different machine must resume it.

### Close the session
    python scripts/brain.py close SES-XXXXXXXXXXXX --outcome partial

A successful close is refused until ALL tasks are done, the handoff exists
and the person explicitly approves:

    python scripts/brain.py close SES-XXXXXXXXXXXX --outcome success --owner-approved

Each closed session creates an **unreviewed skill proposal** in:
.brain-data/operator/skill-proposals/SES-....md.

It is not executable, registered, automatically installed or loaded into
future agent contexts. A human must judge whether this was a reusable
procedure. Actual skill composition/promotion is a later gated milestone.

## Operational invariants

- Source of truth for these sessions: private SQLite journal under .brain-data.
- SQLite foreign keys and event rows preserve a trace of normal transitions.
- Use a registered actor. Do not trust free-form role claims.
- Skill review and planning precede work. Every new task is visible.
- A close without a handoff is refused, regardless of outcome.
- Success is not self-certified: --owner-approved represents a local human act.
- No command invokes LLMs, shells, plugins or remote services automatically.
- Never put credentials, personal session data or model weights in Git.
- A CLI flag cannot verify who physically typed it; real multi-user auth,
  per-agent OS isolation and signed approval receipts are future work.
- The CLI does not automatically capture chats or detect when an external chat
  ends. Harness adapters must explicitly invoke start/handoff/close events.
- For canonical repository handoff, continue using scripts/handoff.py.
- For the established knowledge index, use scripts/kb.py ingest/search.
- For the existing memory and governance tools, see AGENTS.md.

## Suggested integration contract for harness authors

1. At session_begin: call skills inventory; start a session.
2. Before any write tool: load current tasks, confirm skill review/plan gates.
3. On task_started/task_discovered: record or add a task.
4. After each milestone: update tasks and run tests; consider Twin World.
5. At chat_end and session_end: write handoff and generate a draft skill.
6. Only a trusted user UI can send a success confirmation and later authorize
   skill promotion.

The current Python CLI does NOT intercept external model tool calls; a
connector/harness must enforce this ordering. Do not claim universal policy
enforcement until integration tests verify the actual tool boundary.

## What to build next

A packaged executable entry point, better Windows command wrapper,
cross-platform JSON events, fast capture/search commands, agent event hooks,
credentialed approvals, durable queues, skill composition and Twin 1 isolation.
