# Harness integrations

The harness door is `15_SYSTEM/scripts/mcp_server.py` — a Model Context Protocol server
over stdio (stdlib-only, no port, no keys). It serves **this repo** (it resolves its own
root from the file's location, so the working directory of the client does not matter).

Register it in whatever harness you use; the only value that changes per client is the
config shape. Registry record: `MCP-E1807E50` (`11_CONTROL/mcp/`).

## Generate a relocatable local host config

From the cloned repository, generate **one** config snippet for the host on
**this machine** (Python 3.9+; use `python3` on Unix or `py -3` on Windows
if `python` is unavailable):

```sh
python scripts/mcp_config.py --client claude-desktop
python scripts/mcp_config.py --client opencode
python scripts/mcp_config.py --client codex
```

The first two print JSON; **Codex CLI prints TOML** for
`[mcp_servers.second-brain]` with absolute `command` and `args`, and
`enabled = false` by default. The CLI does not edit any app's settings. It uses
the absolute path to this checkout's `mcp_server.py` and the interpreter that
ran the CLI, so it works when the host launches from another working directory
and when paths contain spaces or non-ASCII characters. Re-run it if the checkout
or Python environment moves. The `*.example.json` files are **templates with
placeholders**, not copy-paste-ready configurations.

For Codex, review the snippet before manually merging it into
`~/.codex/config.toml` (or another approved Codex config scope), preserving
other servers. Only set `enabled = true` after reviewing the server's
write-capable tools, the local data boundary and Codex's approval settings.
This is based on the [Codex configuration reference](https://developers.openai.com/codex/config-reference)
checked on 2026-11-14; **no installed Codex client or handshake was verified**.

Back up your existing host configuration, then manually merge only the generated
`mcpServers.second-brain` entry (Claude Desktop) or the
`mcp.servers.second-brain` entry (OpenCode **V2**) into it. Preserve your other
servers. The OpenCode entry is deliberately `disabled: true`; **only after**
reviewing the server's write tools and host permission policy, change it to
`disabled: false` and restart the host. V2 also accepts **supported V1 MCP
configuration** for migration, but this generator deliberately outputs native
V2 syntax. Confirm the installed host version first; this generator has not
been tested against an installed client. Schema and migration behavior checked
against the [OpenCode MCP documentation](https://opencode.ai/docs/mcp-servers)
and [V1 migration guide](https://opencode.ai/docs/migrate-v1) on 2026-11-13.
The generator neither installs a package nor connects a host nor changes
permissions. It does not demonstrate a successful MCP handshake; the host still
needs a compatible MCP client implementation.

**Access warning:** the MCP server has read tools **and** proposal/import write
tools; generating a config does not put it into read-only mode. Review host tool
approvals and the access boundary before enabling it. A model-backed host may
send excerpts returned by read tools to its model provider; do not connect a
private vault to an untrusted host. Strict session checks are separately
opt-in (`SBO_REQUIRE_SESSION=1`) and are not an OS-enforced sandbox.

## Verify the local MCP wire before configuring a host

```sh
python scripts/mcp_smoke.py
```

The diagnostic launches the **shipped** server over stdio with one temporary,
synthetic Markdown note. It verifies the JSON-RPC initialize exchange,
`tools/list`, a `vault_search` result citing that note, and a refused
`candidate_propose` in a second process with `SBO_REQUIRE_SESSION=1`
but no session credentials. It checks that the candidate shelf was not
created, prints a JSON result and exits nonzero on failure. Both processes
run only against a disposable root and are bounded by a timeout; existing
host configurations and private brain data are never read by this probe.

This is a local transport and strict-gate smoke test, **not** a verification
that any specific version of Claude Desktop, Claude Code, Codex, or OpenCode
connects, nor an OS-level sandbox or a blanket read-only guarantee. Outside
strict session mode, the actual MCP server still exposes write tools.

## Tools exposed

| tool | write? | what it does |
|---|---|---|
| `vault_search` | read | BM25 keyword search over permitted brain prose; unicode tokenizer, Persian works |
| `source_search` | read | search explicitly imported private sources; exposes matching content to the client |
| `source_import` | **write** | record one explicitly named file from inside the brain as a private source (raw bytes kept, provenance recorded, index rebuilt); refuses paths outside the brain or in denied zones |
| `lesson_propose` | **write** | propose a private source-backed lesson for human review |
| `lesson_recall` | read | retrieve approved private lessons with evidence |
| `capabilities` | read | list registry capabilities and suggest matches for a task |
| `memory_recall` | read | the repo's own lessons (cue / lesson / evidence / confidence) |
| `registry_list` | read | registry records, optionally by kind, with the active/superseded split |
| `registry_show` | read | one record by id |
| `doctor_status` | read | a facts-only status readout (records, zones, lessons, and which rule closes the run plane — it does not open it) |
| `candidate_propose` | **write** | files a **registered** row on the quarantine shelf (`14_CANDIDATES/loop`) — agents propose, humans decide |
| `runs_list`, `runs_show` | **refused** | `12_RUNTIME` is denied to agents by `15_SYSTEM/scripts/backend/access.py`, so the door names the rule and returns nothing from inside it; the human view is `15_SYSTEM/scripts/runs.py` |

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
transfer with conflicts. A person can seal the planes it lives in with `python scripts/vault.py
--seal`, but nothing happens by itself: `encrypted_private_backup` is off, no scheduler runs that
command, and no restore has been proved on a machine that never held the bytes.

## Optional System-1 model

`core.laya_decide` is an opt-in read-only orchestration-toolkit decision proposal, **not** a native MCP tool or an automatically executing route. See [Laya installation and contract](laya.md). It is disabled unless `SBO_LAYA_ENABLED=1` and the Laya package is installed in Python 3.10+.
