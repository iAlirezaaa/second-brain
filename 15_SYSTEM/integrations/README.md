# Harness integrations

The harness door is `15_SYSTEM/scripts/mcp_server.py` — a Model Context Protocol server
over stdio (stdlib-only, no port, no keys). It serves **this repo** (it resolves its own
root from the file's location, so the working directory of the client does not matter).

Register it in whatever harness you use; the only value that changes per client is the
config shape. Registry record: `MCP-E1807E50` (`11_CONTROL/mcp/`).

## Tools exposed

| tool | write? | what it does |
|---|---|---|
| `vault_search` | read | BM25 keyword search over the brain's prose (zones, wiki, skills, shelf, root docs); unicode tokenizer, Persian works |
| `memory_recall` | read | the repo's own lessons (cue / lesson / evidence / confidence) |
| `registry_list` | read | registry records, optionally by kind, with the active/superseded split |
| `registry_show` | read | one record by id |
| `doctor_status` | read | a facts-only status readout (records, zones, lessons, runs) |
| `candidate_propose` | **write** | files a **registered** row on the quarantine shelf (`14_CANDIDATES/loop`) — agents propose, humans decide |

## Files

- `opencode.example.json` — merge the `mcp` block into your `opencode.json`.
- `claude-desktop.example.json` — merge the `mcpServers` block into
  `claude_desktop_config.json` (Claude Desktop → Settings → Developer → Edit Config).

Nothing here is loaded by scripts or tests; these are copies to paste from. They are
deliberately **not** named like a registry manifest (`mcp.json`), or `doctor` would try to
read them as records.
