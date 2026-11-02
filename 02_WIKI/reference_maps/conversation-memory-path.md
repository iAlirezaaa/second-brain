---
id: map-conversation-memory-path
type: resource
title: "Conversation memory: one step per row, one refusal per step"
status: evergreen
owner: agent
topics: [memory, conversation, provenance, map]
created: 2026-11-02
updated: 2026-11-02
---

# Conversation memory: the path, step by step

Charter section 11 wants knowledge born in a conversation to survive it. Issue #20's last open
criterion was that this extraction has **a defined path**, not a wish. The path is
`skills/conversation-memory/SKILL.md`; this map is its audit trail. Every row is one step: the
exact command, what that command refuses (quoted from the code, not paraphrased), and the test
that proves the refusal still fires. Where the repo genuinely has no mechanism, the row says
`NO_ROW` and names the law that keeps it absent — an honest `NO_ROW` beats a claim.

Nothing here is new machinery. The store is `15_SYSTEM/scripts/backend/sources.py`, the evidence
chain is `15_SYSTEM/scripts/backend/learning.py`, the single door that drives both is
`15_SYSTEM/scripts/sources.py`, and the harness door is `15_SYSTEM/scripts/mcp_server.py`.
Strings below were measured on 2026-11-02 by running the commands.

## The path

| # | step | command | what it refuses | the test that proves it |
|---|---|---|---|---|
| 1 | name one export | `python 15_SYSTEM/scripts/sources.py import FILE --kind conversation --origin claude:SESSION --format claude-stream-json` | `ERROR: a supported kind and nonempty origin are required`; `ERROR: structured harness source requires conversation kind` | `tests/test_sources.py::test_bad_import_and_failed_rebuild_preserve_index`, `::test_claude_and_cursor_streams_skip_tool_results` |
| 2 | index only the human-facing turns | same command (the `--format` adapter picks what enters the index) | `ERROR: no supported user or assistant messages in JSONL`; `ERROR: invalid JSON on line N`; `ERROR: stream contains more than one session`; tool results, reasoning and system events are never indexed | `tests/test_sources.py::test_codex_projection_keeps_only_user_and_assistant_messages`, `::test_claude_and_cursor_streams_skip_tool_results` |
| 3 | keep the bytes private and verifiable | (no command — `ingest` writes `.brain-data/sources/<id>/{metadata.json,raw.txt}`) | `ERROR: symbolic links are not permitted in source records`; `ERROR: existing source is incomplete; inspect it before retrying`; `ERROR: source already imported with a different format` | `tests/test_sources.py::test_incomplete_record_refuses_rebuild_and_overwrite`, `::test_raw_bytes_preserve_bom_and_windows_newlines` |
| 4 | prove the store never rides Git | `python scripts/health.py` (plane gate) | a `.brain-data` path is not clone-readable and a fresh clone missing it is not a defect | `tests/test_sources.py::test_import_rebuild_search_and_duplicate`, `tests/test_phase26_memory_planes.py` |
| 5 | build the search index | `python 15_SYSTEM/scripts/sources.py rebuild` | `ERROR: invalid source metadata`; a failed rebuild leaves the previous index serving results | `tests/test_sources.py::test_bad_import_and_failed_rebuild_preserve_index` |
| 6 | find the phrase to cite | `python 15_SYSTEM/scripts/sources.py search "the phrase"` | refuses nothing; `[]` and `ERROR: index missing; run rebuild first` are legal empty answers | `tests/test_sources.py::test_cli_roundtrip` |
| 7 | propose with a source id and an exact quote | `python 15_SYSTEM/scripts/sources.py propose --source-id ID --quote "..." --lesson "..." --query "..."` | `ERROR: quote is not present in the source text`; `ERROR: quote, lesson and retrieval query are required`; `ERROR: invalid source id` | `tests/test_learning.py::test_bad_evidence_failed_evaluation_and_changed_record_are_refused` |
| 8 | check provenance, not truth | `python 15_SYSTEM/scripts/sources.py evaluate PROPOSAL_ID` | `ERROR: source identity or checksum mismatch` when the raw file moved; `ERROR: proposal was modified or is invalid`; `passed: false` when the query no longer retrieves the source — and it prints that a passing check does not make the lesson true | `tests/test_learning.py::test_source_to_proposal_evaluation_approval_and_recall`, `::test_bad_evidence_failed_evaluation_and_changed_record_are_refused` |
| 9 | approve — a human, with a flag | `python 15_SYSTEM/scripts/sources.py approve PROPOSAL_ID --approve` | without the flag: `ERROR: explicit human approval is required`; with it but a failed check: `ERROR: proposal did not pass evidence and retrieval checks` | `tests/test_learning.py::test_cli_approval_and_tampered_proposal_refusal` |
| 10 | recall later, re-verified | `python 15_SYSTEM/scripts/sources.py recall "the phrase"` | `ERROR: approval receipt is invalid`; `ERROR: approved lesson evidence no longer matches` — an approved lesson that loses its evidence stops being served | `tests/test_learning.py::test_cli_approval_and_tampered_proposal_refusal` |
| 11 | take it through the harness door | MCP `source_import`, `source_search`, `lesson_propose`, `lesson_recall` | a path outside the brain, in `15_SYSTEM/backups`, or already inside `.brain-data`; a missing `origin`; a refused import leaves no record behind | `tests/test_phase22_harness_bridge.py::test_source_import_refuses_paths_outside_the_brain_and_denied_zones`, `::test_source_import_records_a_selected_file_with_provenance` |
| 12 | move the store between machines | `python 15_SYSTEM/scripts/sources.py transfer SRC DST` (preview) then `--apply` | `ERROR: conflicts found; review preview and explicitly allow conflicts` until `--allow-conflicts`; a missing source directory is not a successful empty transfer; corruption fails before any copy; `verify-copy` reports `verified: false` for missing or changed records | `tests/test_source_sync.py` |
| 13 | promote into the tracked ledger | `python scripts/memory.py --add --plane conversation --id ... --cue ... --lesson ... --evidence skills/conversation-memory/SKILL.md --verdict keep --confidence 0.8` | `REFUSED  a lesson with no evidence is a preference — cite a path, a URL or a probe id`; `REFUSED` when an evidence path does not resolve; `REFUSED  --plane ... is not one of the mapped planes` | tests/test_phase15_repo_memory.py::test_a_lesson_with_no_evidence_is_a_preference, ::test_evidence_that_does_not_open_is_refused_at_the_door, tests/test_phase40_lesson_planes_and_contradictions.py::test_an_unknown_plane_is_refused_and_names_the_vocabulary |
| 14 | keep the plane declared | `python scripts/plane_check.py` | a plane whose store, reader, test or map goes missing; a tracked store that no longer opens | `tests/test_phase26_memory_planes.py` |
| — | scan a harness history folder for sessions | `NO_ROW` | there is no scan, watch or glob: `sources.py` exposes no such subcommand and `ingest_bytes` takes the bytes a caller named | `tests/test_phase41_manager_agent_and_conversation_memory.py` asserts the subcommand list stays read/import/propose-shaped |
| — | fetch a transcript from a URL | `NO_ROW` | the repo ships no network call in this chain; the origin string is a label, not something to open | `AGENTS.md` (no network law), `tests/test_phase19_evidence_survives_a_clone.py` |
| — | let the harness approve its own lesson | `NO_ROW` | `mcp_server.py` exposes 13 tools and none of them is `approve`/`apply`; approval exists only in the CLI a human types | `tests/test_phase22_harness_bridge.py::test_initialize_echoes_protocol_and_lists_tools` |
| — | index conversations into the vector plane | `NO_ROW` | the vector seam is documented as not enforced (`doctor`: `vector_search`); a fresh clone has no embedding store and nothing pretends otherwise | `python 15_SYSTEM/scripts/hades.py doctor`, `scripts/vector_check.py` |

## Reading the table

- Steps 1–3 are one act with one name in it: a person writes the path and the origin. That is
  what "explicitly imported, never auto-scanned" means in this repo, and rows 1 and the first
  `NO_ROW` are its evidence.
- Steps 7–10 are the whole lesson contract: a quote that must be present, a provenance check that
  cannot certify truth, an approval flag only a human types, and a recall that re-verifies.
- `NO_ENTRY` in this plane is `[]` from `search`/`recall` in a clone where nobody imported a
  conversation yet. It is data, not a gap. See `15_SYSTEM/integrations/local-sources.md` for the
  store layout and `02_WIKI/reference_maps/eight-memory-planes.md` for where this plane sits.
- This map is tracked, so a fresh clone reads the path even with an empty private store.
