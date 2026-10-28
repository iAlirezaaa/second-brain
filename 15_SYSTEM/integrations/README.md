# Harness integrations

The harness door is `15_SYSTEM/scripts/mcp_server.py` — a Model Context Protocol server
over stdio (stdlib-only, no port, no keys). It serves **this repo** (it resolves its own
root from the file's location, so the working directory of the client does not matter).

Register it in whatever harness you use; the only value that changes per client is the
config shape. Registry record: `MCP-E1807E50` (`11_CONTROL/mcp/`).

## Tools exposed

| tool | write? | what it does |
|---|---|---|
| `vault_search` | read | BM25 keyword search over permitted brain prose; unicode tokenizer, Persian works |
| `source_search` | read | search explicitly imported private sources; exposes matching content to the client |
| `lesson_propose` | **write** | propose a private source-backed lesson for human review |
| `lesson_recall` | read | retrieve approved private lessons with evidence |
| `capabilities` | read | list registry capabilities and suggest matches for a task |
| `memory_recall` | read | the repo's own lessons (cue / lesson / evidence / confidence) |
| `registry_list` | read | registry records, optionally by kind, with the active/superseded split |
| `registry_show` | read | one record by id |
| `doctor_status` | read | a facts-only status readout (records, zones, lessons, runs) |
| `candidate_propose` | **write** | files a **registered** row on the quarantine shelf (`14_CANDIDATES/loop`) — agents propose, humans decide |
| `runs_list`, `runs_show` | read | inspect the run ledger |

## Files

- `opencode.example.json` — merge the `mcp` block into your `opencode.json`.
- `claude-desktop.example.json` — merge the `mcpServers` block into
  `claude_desktop_config.json` (Claude Desktop → Settings → Developer → Edit Config).

Nothing here is loaded by scripts or tests; these are copies to paste from. They are
deliberately **not** named like a registry manifest (`mcp.json`), or `doctor` would try to
read them as records.

## Capability inventory

`python 15_SYSTEM/scripts/capabilities.py` lists active registry skills, plugins, MCP
records, extensions and built-in tools. Use `--task "search knowledge"` for keyword
suggestions and `--harness-id HAR-ID` to check explicitly recorded approvals. A draft,
unknown compatibility, unspecified permissions or unknown installation state are reported
as such. Registry records and local descriptions are untrusted data; inspect them before
use. This is a recommendation and inventory only: it does not install packages, alter a
host configuration, grant tool permissions or prove that a capability works.

The default filesystem tools refuse known protected paths, `.env` files, common key and
credential filenames, Git internals and `secrets` directories. This is a path-based guard,
not OS access control or a guarantee that ordinary files do not contain secrets.

## Installing one approved skill

Installation is a plan → review → apply decision, never a copy-in-place:

```text
python 15_SYSTEM/scripts/install_skill.py plan --skill-id SKL-XXXXXXXX \
  --harness-id HAR-XXXXXXXX --destination path/to/host/skills
python 15_SYSTEM/scripts/install_skill.py apply PLAN.json --approve
```

The plan binds the skill, harness, destination, every file digest and a `plan_id`. `apply`
refuses `--approve`-less invocation, a stale or edited plan, a missing approval for that
harness, an existing destination (no replacement) and any symlink inside the skill. A partial
write leaves `.install-incomplete` in the new directory so the failure stays visible; delete
or inspect it, then plan again. There is no package download and no network call.

Private source data is documented in [local-sources.md](local-sources.md): explicit import,
rebuildable index, provenance, evidence-backed lessons, retrieval measurement and folder
transfer with conflicts. That data is not encrypted, not backed up automatically and not
synchronised by this repo.
