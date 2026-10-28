# Local source ingestion (initial implementation)

Import a file only after selecting it and choosing an origin. The source must be UTF-8 text.

```text
python 15_SYSTEM/scripts/sources.py import path/to/file.txt --kind conversation --origin codex:session-id
python 15_SYSTEM/scripts/sources.py import path/to/rollout.jsonl --kind conversation --origin codex:session-id --format codex-jsonl
python 15_SYSTEM/scripts/sources.py import path/to/claude.jsonl --kind conversation --origin claude:session-id --format claude-stream-json
python 15_SYSTEM/scripts/sources.py import path/to/cursor.jsonl --kind conversation --origin cursor:session-id --format cursor-stream-json
python 15_SYSTEM/scripts/sources.py rebuild
python 15_SYSTEM/scripts/sources.py search retrieval
```

Kinds are `document`, `research`, `conversation`, and `generated`. The raw text and metadata
are stored under `.brain-data/sources/`, ignored by Git. Importing the same bytes, origin,
and kind twice returns the existing record. Changed content creates a separate record.
`rebuild` replaces the disposable SQLite index only after every record validates. The
rebuild refuses incomplete source directories and leaves the previous index in place;
re-import also refuses an incomplete existing record instead of overwriting its bytes.
Inspect and recover the incomplete directory before retrying. The
`source_search` MCP tool returns matching imported text with its origin and timestamp to
the connected client: connect only clients trusted to receive that data. Search uses a
local BM25-style word ranking, permits partial-word matches and normalizes Arabic/Persian
variants of yeh and kaf. All query terms must occur; this is not semantic search. Rebuilding
creates word-frequency tables; older indexes remain readable using a slower text scan until
rebuilt. Partial-word queries scan the indexed vocabulary, so latency and storage still need
measurement on large real stores. Punctuation-only queries have no matches. This is not
automatic learning.

## Evidence-backed private lessons

After importing and rebuilding, an agent or person can propose a lesson using an exact
quote, source ID, lesson text and a retrieval query:

```text
python 15_SYSTEM/scripts/sources.py propose --source-id SOURCE_ID --quote "exact quote" --lesson "proposed lesson" --query "search phrase"
python 15_SYSTEM/scripts/sources.py evaluate PROPOSAL_ID
python 15_SYSTEM/scripts/sources.py approve PROPOSAL_ID --approve
python 15_SYSTEM/scripts/sources.py recall "search phrase"
```

`lesson_propose` and `lesson_recall` are also exposed through MCP; approval is local CLI
only. Evaluation checks the source checksum, exact quote, and whether the chosen query
retrieves the source. It does not establish that the interpretation is true, useful, or
improves performance. A human must review the proposal and explicitly approve it. Pending
and approved records stay in `.brain-data/learning`, not the tracked public memory ledger.
They require secure backup outside Git.

`sources.py benchmark CASES.json` measures mean recall and mean reciprocal rank on a
separately curated JSON array such as `[{"query":"restore", "expected_ids":["SOURCE_ID"]}]`.
Save the report before and after a retrieval change and compare the same cases and limit;
`sources.py compare-benchmarks BASELINE.json CANDIDATE.json` rejects reports with different
cases, result limits or indexed corpus, and reports metric deltas. A regression in either
metric fails the comparison verdict. The reports are local unsigned evidence, not a security
boundary; do not treat a candidate's own query as an independent quality evaluation or a
successful comparison as approval to apply a change.

Structured adapters retain the selected raw JSONL (which may include sensitive tool output)
but index only user/assistant text messages. They exclude tool results, reasoning and
system events. `claude-stream-json` accepts Claude Code SDK stream output, while
`cursor-stream-json` accepts Cursor CLI stream output and joins assistant text deltas.
They are not parsers for undocumented local history databases. Multiple session IDs in
one stream, unsupported or empty formats are refused. For a Cursor Markdown export use
the `text` format. No adapter scans for sessions automatically.

This directory is local and is not automatically encrypted, backed up, or synchronized.
Use an encrypted, access-controlled backup; do not copy its index between devices as a
sync mechanism. Do not import credentials or data without authorization. No harness is
automatically scanned and no external URL is fetched by this command.

## Explicit batch imports

Create a UTF-8 JSON manifest outside Git with one entry per selected file. Relative paths
are resolved against the manifest directory; each entry needs `path`, `kind`, and `origin`,
and may specify `format`:

```json
[{"path": "notes/research.txt", "kind": "research", "origin": "manual:research"}]
```

Run `python 15_SYSTEM/scripts/sources.py batch MANIFEST.json` to preview and receive a
content-bound `plan_id`. Run the same command with `--apply --plan-id PLAN_ID` to import
the reviewed byte snapshots and rebuild the index. A changed manifest, source path or file
content invalidates the plan. The command never scans folders for new source files; rebuilding
reads the existing imported records.
It validates all entries before writing, but disk failures can still leave a partial import;
the JSON report names completed source IDs, the command returns nonzero, and it does not
rebuild the index. Correct the failure and preview again before retrying.

For an explicit additive transfer between two data directories, first preview with:

```text
python 15_SYSTEM/scripts/sources.py transfer SOURCE_DATA_DIR DESTINATION_DATA_DIR
```

Add `--apply` to copy validated sources and proposals; rebuild the destination index
afterwards. The preview includes approval receipts, but importing them also requires
`--include-approvals`: this explicitly trusts decisions from the selected source directory.
The receipts are not cryptographically authenticated; do not import them from an
untrusted device or transport. Different contents with the same kind
and origin are reported as conflicts. They are copied only with the separate
`--allow-conflicts` flag and both versions remain available. The transfer is plaintext,
does not delete or reconcile records, and is not a backup or an automatic sync service.
Use an encrypted transport and independently tested backups. A failed or interrupted copy
may leave an incomplete record that must be inspected and removed before retrying.
`sources.py verify-copy SOURCE_DATA_DIR DESTINATION_DATA_DIR` validates the records and
compares all source records, proposals, and approvals, returning a nonzero status for a
missing or different record. It permits extras and does not verify encryption or replace
an actual restore exercise.
