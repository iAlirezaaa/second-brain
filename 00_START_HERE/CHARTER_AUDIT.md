# Charter Audit — the yardstick measured

*The owner's brief (`00_START_HERE/PROJECT_CHARTER.md`) claims 15 sections of law. This file is
the first honest reading of what this repo honours today, section by section, with the command
that shows it — run by any reader after a fresh `git clone`, nothing cited from behind the git
boundary. Written 2026-10-28, on main at the merge of PR #19. A verdict is one of
**honoured** (a gate or test proves it), **partial** (true, with a named gap), or **gap**
(nothing in the tree answers it). Every gap names the issue or roadmap phase that closes it;
per the charter's own §8, an issue exists before the fix.*

## The audit table

| § | The charter asks | Verdict | Evidence (run it yourself) | Gap → closes by |
| --- | --- | --- | --- | --- |
| 1 | A standalone, self-improving Agentic OS that learns from its own history | partial | `python scripts/health.py` → 6/6; `python -m unittest discover -s tests` → 297 green; `15_SYSTEM/memory/lessons.jsonl` → 26 lessons with evidence; `14_CANDIDATES/loop/report-2026-10-27.md` → the loop's own report | "smarter over time" is real but its cadence is a cron habit, not a governed definition → phase 28 (scheduler seam) |
| 2 | Standalone; no mandatory dependency on any app or model | **honoured** | `git grep -E "^\s*(import\|from)\s+(requests\|fastapi\|numpy\|...)"` → none; `tests/test_phase16_host_independence.py`; CI green on 3.9+3.12, ubuntu+windows | — |
| 3 | Study the reference repos, extract useful logic, adapt — no blind copying | partial | `02_WIKI/reference_maps/superagi-to-hades-map.md` (adopt/refuse table) + `15_SYSTEM/scripts/backend/` (the SuperAGI port); harness2's keep-base logic ships as `scripts/base.py`; claude-obsidian's audit shipped as phase 8 | only SuperAGI has a standing map file → issue (see gaps) |
| 4 | One standard structure, stable unique IDs, no scattered files; agents obey it too | **honoured** | `python 15_SYSTEM/scripts/hades.py doctor` → `errors: 0 \| warnings: 0`, duplicate-id gate, zone gates; `catalog.json` enumerates 13 records; the plan → `apply --approve` door is the only write path | — |
| 5 | Persistent memory: eight planes (project, repository, agent, task, error, decision, knowledge, conversation), structured, searchable, contradiction-aware | **gap** | existing stores: errors → `lessons.jsonl`, decisions → `02_WIKI/decisions/`, agents → `11_CONTROL/agents/`, tasks/runs → `runs.py`; but **no mapping document**, conversation memory has **no reader surface**, and `kb.py` indexes `vault-template` only, not this repo's own prose | → issue filed; phases 26–27 |
| 6 | Continuous self-improvement: observe → analyse → improve, learning from errors | partial | `scripts/loop.py` one-cycle ratchet + prev-run compare + `P1` exit; `14_CANDIDATES/loop/gaps.jsonl` self-driving backlog | the loop's cadence is not a registry definition; two clocks (cron + backend schedules) → phase 28 |
| 7 | Agent & skill management: register roles/abilities, sub-agents, a manager agent, no duplicated work | partial | `hades.py list --kind agent` → `AGT-78188303 repo-auditor`, `AGT-B746F5DE loop-runner`; 10 skills in `skills/`; backend `engine.py` runs actors with per-actor `tool_allowlist` | the charter's **manager agent** is not a registered definition → issue filed |
| 8 | Standard repo workflow: independent re-discovery → audit → issues → test-first fix → PR | **honoured** | `skills/first-session/SKILL.md` + `skills/self-audit/SKILL.md`; issues #3–#14 filed *before* their fixes (order documented in HANDOFF §2); 3 open issues (#15–#17) are the live §8 backlog | — |
| 9 | Per-repository memory that grows with the repo, referenced to commits/issues | **honoured** | `HANDOFF.md` (machine-fresh §1, freshness-gated), `CHANGELOG.md`, `lessons.jsonl` evidence fields cite files + issues + chat sources | — |
| 10 | Never merge a PR without review, tests, and compatibility assurance | **honoured** | `gh api repos/.../branches/main/protection` → 4 required `test (...)` contexts, force-push blocked; PR #18/#19 merged only after 8/8 contexts green + two explicit compatibility merges | — |
| 11 | Knowledge from conversations becomes durable, reviewed, classified knowledge | partial | `lessons.jsonl` rows carry `"source": "chat 2026-10-27"`; the charter itself is a chat-born law now tracked; decisions record chat-born laws (`WIK-B7ED0084`) | extraction is manual with no gate → folded into the §5 issue (phase 26) |
| 12 | Professional English docs that describe what *exists*, not what is planned | **honoured** | README/AGENTS/ROADMAP/CHANGELOG/SYSTEM_MAP are English; Persian belongs in content and `qc` gates its byte hygiene; measured blocks are regenerated, not typed | — |
| 13 | Fourteen laws, and "the rules must apply to the agent that wrote them" | **honoured** | each law maps to a gate/test: architecture-first (plan door), standalone (import scan), memory-first (`--recall` first move), verify-before-trust (probe + evidence gates), no-duplication (doctor), recoverability (`base.py --recover`), security (zone_check + allowlists) — the suite is the proof | — |
| 14 | Expected outcome: a standalone, self-organizing, memory-keeping, improvable system | partial | everything above, measured; the §8 *process* is documented and gated, but its executor is the agent following the skill, not a bundled CLI | the automation boundary is honest and deliberate (agents are the executors by charter §8) → no phase |
| 15 | Build in the stated order, keep what exists, record state per stage | **honoured** | `ROADMAP.md` phases 25–30 implement exactly this order; every phase above was shipped test-first with its state recorded in CHANGELOG/HANDOFF | — |

## Verdict

**11 of 15 sections honoured, 3 partial, 1 gap.** The structural laws (independence, structure,
workflow, PR discipline, per-repo memory, documentation, the fourteen laws) are gate-proven.
The gaps cluster in one place: **memory as the charter means it** (§5, §11) — the stores exist
but the eight-plane map, the conversation-memory reader, and self-corpus search do not; plus
two registration gaps (§3 map files for the other reference repos, §7 manager agent). These are
phases 26–27 of the roadmap and the issues filed below.

## Gaps filed as issues (issue-then-fix, per §8)

- #20 — *Eight memory planes: no mapping document, no reader for conversation memory, kb.py
  covers the template not the repo corpus* (§5, §11) — closes with roadmap phases 26–27.
- #21 — *The manager agent named in §7 is not a registered definition* (§7) — closes by
  registering the agent record with its role scope through the plan door.
- #22 — *Only the SuperAGI reference has a standing map file; harness2 and claude-obsidian
  extractions live in prose history without one* (§3) — closes with two short map files.
- Open §8 backlog already in the tracker: #15 (memory --supersedes validates late),
  #16 (zone denial wording), #17 (state fingerprint ages on regenerated files) — these were
  filed after the handoff snapshot; they are the next fixes, not forgotten ones.
