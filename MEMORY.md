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
| `mem-doors-must-point-at-real-rooms` | a generated instruction file names a path that no longer exists | every host door is generated from AGENTS.md, so a stale path in the canon is republished to five agents at once; lint the backticked paths in the body and refuse the render, do not review the prose by eye | `helped` | 0.9 | `scripts/sync_hosts.py`, `skills/first-session/SKILL.md`, `tests/test_phase16_host_independence.py` |
| `mem-dot-prefix-stripping` | evidence pointed at a path starting with a dot, like .kb/kb.sqlite | strip a leading './' as a prefix, never with lstrip('./'): the character class eats the dot and the gate reports a real file as a fabrication | `helped` | 0.9 | `scripts/candidate_check.py`, `tests/test_phase13_candidate_contract.py` |
| `mem-edit-is-not-create` | an agent wanted to change a note a human wrote | agents create in 00_Inbox and never edit human zones; write a proposal and let the human merge -- action: edit into agent_edit_never is refused even when approved | `helped` | 0.9 | `rules/zones.json`, `scripts/zone_check.py` |
| `mem-fence-validates-itself` | rules/zones.json named a zone nobody had created and no code read agent_edit_never | validate the fence before trusting it: zone_check.check_zones_config judges rules/zones.json itself and promote refuses to run while it is broken | `helped` | 0.9 | `scripts/zone_check.py`, `scripts/promote.py`, `tests/test_phase3.py` |
| `mem-frontmatter-block-lists` | frontmatter has a bare key followed by '- item' block lines | coerce None and a prior scalar into a list before appending -- parse_frontmatter is shared by every gate and a crashing gate is a silent gate | `helped` | 0.9 | `scripts/common.py`, `tests/test_toolchain.py` |
| `mem-gates-that-pass-locally-are-not-green` | every gate is green on my machine and CI is red on a fresh clone | a gate run on the writing machine proves only that the writing machine is consistent: local-only state (.kb/, 12_RUNTIME/, 13_LAB/, gitignored caches) exists there and nowhere else, so reproduce CI first by copying exactly what git ls-files reports into an empty folder and running the gate there, and refuse any evidence path that lives behind the documented boundary | `helped` | 0.9 | `scripts/common.py`, `scripts/candidate_check.py`, `tests/test_phase19_evidence_survives_a_clone.py`, `AGENTS.md` |
| `mem-generated-bodies-obey-the-schema` | generated record bodies turn the vault gates red | whatever a script writes into the vault must satisfy the vault schema itself: a generated OVERVIEW.md without frontmatter made the frontmatter gate fail on files no human ever opened | `helped` | 0.9 | `15_SYSTEM/scripts/hades.py`, `rules/schema.json`, `tests/test_phase17_control_plane.py` |
| `mem-hygiene-gate-finds-what-the-eye-misses` | AI-looking Persian text passes review and still contains an Arabic letter | an Arabic ta marbuta (U+0629) leaked into generated Persian prose again and only the byte-level hygiene gate saw it: scan the bytes of every generated Persian line, never the rendered glyphs, and treat a hygiene warning as a red gate | `helped` | 0.9 | `15_SYSTEM/scripts/hades.py`, `00_START_HERE/START.md`, `scripts/candidate_check.py` |
| `mem-numbers-are-generated` | a document quotes a test count that no longer matches the suite | a number typed into a document rots silently and gets repeated as fact; the measured block between two markers is written by a script and staleness itself is a failing health gate, so CI reads the number instead of trusting the prose | `helped` | 0.9 | `scripts/doc_report.py`, `README.md`, `HANDOFF.md`, `00_START_HERE/START.md`, `tests/test_phase18_measured_docs.py` |
| `mem-proposed-is-not-measured` | the loop named a change nobody had run | verdict: proposed is legal on the shelf and never promotable; count the shelf as proposed == adopt + revise + drop + keep_base + open so no row disappears quietly | `helped` | 0.9 | `scripts/loop.py`, `14_CANDIDATES/loop/ledger.jsonl`, `tests/test_phase14_typed_candidates.py` |
| `mem-prose-is-not-a-note` | a validator counts a README as if it were a note | documentation is not a note: one shared prose predicate in common.py keeps link and frontmatter gates in agreement, while a per-gate exclude list drifts the moment either gate changes | `helped` | 0.9 | `scripts/common.py`, `scripts/link_check.py`, `scripts/frontmatter_check.py`, `scripts/vault_stats.py` |
| `mem-a-fallback-is-bytes-plus-a-fingerprint` | someone proposes falling back to the last known good state | last known good is only real if the bytes are on disk and a fingerprint proves those bytes are the state the record describes: measure the base by running the gates before saving it, keep the folder holding the snapshots outside the identity they record (paperwork), and refuse a journal entry whose bytes are gone rather than reporting a successful recovery | `helped` | 0.85 | `scripts/base.py`, `tests/test_phase20_known_good_base.py`, `scripts/common.py`, `AGENTS.md` |
| `mem-refusal-must-print` | a gate returned 1 and printed nothing | every refusal names the row and the reason, and returns from inside the branch that found the problem -- a silent gate gets switched off because nobody can tell it from a clean one | `helped` | 0.85 | `scripts/promote.py`, `scripts/candidate_check.py` |
| `mem-validate-at-the-door` | a bad value was accepted at write time and only rejected by the later check | validation belongs at the door: --add refuses an unknown verdict or a confidence outside 0..1 before the row exists, because a refusal that arrives after the write becomes a cleanup task instead of a gate | `helped` | 0.85 | `scripts/memory.py`, `tests/test_phase15_repo_memory.py`, `rules/memory.schema.json` |
| `mem-keep-base-is-an-output` | a cycle found nothing better than the current state | write keep_base instead of inventing a change; measuring and deciding to change nothing needs no run and is a legitimate result | `keep_base` | 0.8 | `rules/candidate.schema.json`, `skills/loop/SKILL.md` |

## How a lesson gets here

A lesson is a candidate row that was measured: see
`rules/candidate.schema.json` and `skills/loop/SKILL.md`. The verdict column is
what the measurement said, not what the author hoped.
