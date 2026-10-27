---
id: mem-index
type: index
title: Repo memory
status: raw
owner: agent
topics: [memory, lessons, evidence]
created: 2026-10-27
updated: 2026-10-27
generated_by: scripts/memory.py --render
---

# MEMORY — what this repo learned, and what it is allowed to claim

**This file is generated.** The catalog is `15_SYSTEM/memory/lessons.jsonl`; edit that
with `python scripts/memory.py --add ...` and re-render. A hand-edit here is a claim
the ledger cannot back, and `scripts/memory.py --check` (which `health.py` runs) says so.

Read it at the start of a session: `python scripts/memory.py --recall "<what you hit>"`.
An empty answer is legal and honest -- that is `NO_ENTRY`, and it is data, not a gap.

| id | cue | lesson | verdict | conf | evidence |
| --- | --- | --- | --- | --- | --- |
| `mem-child-output-encoding` | a gate's child printed em dashes or Persian on a Windows console | read subprocess output through common.run_utf8 (encoding='utf-8'); text=True alone inherits the code page and the parent dies looking like a gate that said nothing | `helped` | 0.95 | `scripts/common.py`, `tests/test_toolchain.py` |
| `mem-measurement-freshness` | a verdict cited a probe that ran before the last edit | a fresh measurement matches the current state fingerprint AND the candidate digest; paperwork (14_CANDIDATES, 12_RUNTIME, the proposal sink) stays outside the fingerprint so filing never invalidates an honest run | `helped` | 0.95 | `scripts/probe.py`, `scripts/common.py`, `tests/test_phase12_probe.py` |
| `mem-dot-prefix-stripping` | evidence pointed at a path starting with a dot, like .kb/kb.sqlite | strip a leading './' as a prefix, never with lstrip('./'): the character class eats the dot and the gate reports a real file as a fabrication | `helped` | 0.9 | `scripts/candidate_check.py`, `tests/test_phase13_candidate_contract.py` |
| `mem-edit-is-not-create` | an agent wanted to change a note a human wrote | agents create in 00_Inbox and never edit human zones; write a proposal and let the human merge -- action: edit into agent_edit_never is refused even when approved | `helped` | 0.9 | `rules/zones.json`, `scripts/zone_check.py` |
| `mem-fence-validates-itself` | rules/zones.json named a zone nobody had created and no code read agent_edit_never | validate the fence before trusting it: zone_check.check_zones_config judges rules/zones.json itself and promote refuses to run while it is broken | `helped` | 0.9 | `scripts/zone_check.py`, `scripts/promote.py`, `tests/test_phase3.py` |
| `mem-frontmatter-block-lists` | frontmatter has a bare key followed by '- item' block lines | coerce None and a prior scalar into a list before appending -- parse_frontmatter is shared by every gate and a crashing gate is a silent gate | `helped` | 0.9 | `scripts/common.py`, `tests/test_toolchain.py` |
| `mem-proposed-is-not-measured` | the loop named a change nobody had run | verdict: proposed is legal on the shelf and never promotable; count the shelf as proposed == adopt + revise + drop + keep_base + open so no row disappears quietly | `helped` | 0.9 | `scripts/loop.py`, `14_CANDIDATES/loop/ledger.jsonl`, `tests/test_phase14_typed_candidates.py` |
| `mem-refusal-must-print` | a gate returned 1 and printed nothing | every refusal names the row and the reason, and returns from inside the branch that found the problem -- a silent gate gets switched off because nobody can tell it from a clean one | `helped` | 0.85 | `scripts/promote.py`, `scripts/candidate_check.py` |
| `mem-keep-base-is-an-output` | a cycle found nothing better than the current state | write keep_base instead of inventing a change; measuring and deciding to change nothing needs no run and is a legitimate result | `keep_base` | 0.8 | `rules/candidate.schema.json`, `skills/loop/SKILL.md` |

## How a lesson gets here

A lesson is a candidate row that was measured: see
`rules/candidate.schema.json` and `skills/loop/SKILL.md`. The verdict column is
what the measurement said, not what the author hoped.
