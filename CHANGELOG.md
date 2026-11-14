# Changelog — Second Brain OS

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning: SemVer. Nightly-loop activity lives in `14_CANDIDATES/loop/` and is
**not** listed per commit — only shipped, human-promoted changes appear here.

## [Unreleased]

### Fixed (nightly loop merge identity, issue #41; CI pending)
- GitHub Actions run [#43577040140](https://github.com/iAlirezaaa/second-brain-os/actions/runs/43577040140) failed before the nightly report cycle: refreshing `loop/nightly` against `main` may create a merge commit, but the workflow set `user.name` and `user.email` only in its later publish step. The checkout step now configures the existing bot identity locally **before** merging. The existing CI governance test checks this ordering. A synthetic two-branch Git reproduction failed without an identity (exit 128) and succeeded after it was set (exit 0). This does not resolve the separate Actions PR-creation permission issue (#41 / PR #81), certify a successful live scheduled run, or change branch protection.


### Fixed (issue #102; PR #103 review; CI recheck pending)
- The Codex TOML path regression now decodes emitted string literals before
  comparing their values. CI run #43537155432 found its JSON-lowercase-escape
  assertion rejected valid TOML uppercase hexadecimal Unicode escapes across
  Windows and Ubuntu. Python 3.9 uses the standard-library `ast` parser for the
  two string/list fields; Python 3.11+ also checks the full TOML with `tomllib`.
  No generator, host settings, runtime permission or stored user data changed.

### Added (issue #102; Codex CLI snippet; CI pending)
- `scripts/mcp_config.py --client codex` can print machine-local Codex TOML
  `[mcp_servers.second-brain]` with absolute Python/server paths and
  `enabled = false` pending human approval. Standard library only; supplementary
  Unicode and Windows paths use TOML-valid escapes. Existing host-config tests
  now check Codex schema, nonmutation, missing/symlinked server refusal and
  preserve the existing JSON output shapes. English/Persian quickstarts and
  integration docs explain manual merge and limitations. No installed Codex
  handshake, actual host permission test, or user settings mutation claimed.

### Changed (issue #100; native OpenCode V2 config; PR #101 merged, 7 CI jobs passed in #43522910025)
- `scripts/mcp_config.py --client opencode` now prints
  `mcp.servers.second-brain` with a local absolute command instead of
  the legacy V1 `mcp.second-brain` layout. The native V2 entry uses
  `disabled` instead of `enabled`, starting `disabled: true` until a person reviews
  write-tool permissions. The checked-in placeholder template, docs and
  existing host-config regression test and Persian START guide enforce the
  same shape. No client
  settings are touched; actual OpenCode V2 connection remains unverified.
  V2 still accepts supported V1 configurations for migration; the previous
  snippet was **not** independently shown to fail. References:
  https://opencode.ai/docs/mcp-servers and
  https://opencode.ai/docs/migrate-v1 (checked 2026-11-13).

### Added (issue #98; merged PR #99; seven CI jobs green in run #43507137025)
- An offline `python scripts/mcp_smoke.py` diagnostic starts the actual
  MCP stdio server twice against one disposable, synthetic note. It checks
  JSON-RPC initialization, tool tags, a source-cited `vault_search` result,
  and refusal of a valid `candidate_propose` call when strict session mode
  has no session metadata. It also checks that no proposal shelf was created.
  Reports JSON with elapsed time or a nonzero failure exit. Two tests exercise
  the live door and missing-server refusal. No host settings, private data,
  permission defaults, or network services are touched. This is not a real
  Claude/Codex/OpenCode client certification or an OS security guarantee.

### Fixed (PR #97 merged; seven CI jobs passed in run #43486609444)
- The MCP registration regression tests now compare the *canonical* server
  location rather than the textual name returned by a temporary directory.
  Windows CI #283 exposed `RUNNER~1` 8.3 path aliases while `--root` resolved to
  the same directory under its long path. Both host-schema assertions now
  reflect the intended contract, without changing runtime configuration,
  permissions, server behavior or introducing dependencies.

### Added (issue #96; merged PR #97)
- A portable, standard-library-only `scripts/mcp_config.py` prints a
  host-specific JSON registration snippet for Claude Desktop or OpenCode with
  absolute paths to the running interpreter and local MCP server. It refuses
  absent or symlinked server files and never edits either host configuration.
  `tests/test_mcp_host_config.py` exercises five isolated scenarios including
  Unicode/space paths, both host schemas, missing/symlink refusal and no host
  settings mutation. Integration documentation now explains manual merge,
  nonportable templates and the MCP door's existing write-tool exposure.
  This is **not** an end-to-end host handshake, read-only enforcement or a
  new permission boundary.

### Fixed (CI #280 green; merged PR #95)
- Public onboarding commands no longer require the Windows-only
  `py -3.10` launcher pin. The first-session instructions, Persian START
  walkthrough, canonical AGENTS instructions, five rendered host projections
  and self-audit skill now use verified Python 3.9+ commands instead.
  `tests/test_portable_python_entrypoints.py` prevents regression for those
  entrypoints. This is a bounded correction for #46; historical docs remain
  to be inventoried separately.

### Added (CI #277 green; merged PR #94)
- Reproducible local first-recall smoke probe: `scripts/first_success.py`
  runs the real keyword KB ingest + search CLI against only disposable,
  synthetic notes, verifies the resulting source path and local index, then
  reports JSON success rate and wall-clock timings across bounded trials.
  `tests/test_first_success_probe.py` covers success, failure, bounds and
  structured output. It does **not** time Git clone, installation, semantic
  retrieval or real-user workloads (issue #93).

### Fixed (verified by CI #275; merged PR #91)
- KB corpus no longer follows aliased Markdown files or symlinked parent folders,
  including links that resolve outside the brain root, nor crashes on broken
  links. `kb.py ingest` rebuilds its derived search index without those aliases.
  This is an index hygiene boundary, not a race-free filesystem sandbox;
  synthetic regression coverage: `tests/test_kb_corpus_symlink_boundary.py`.
  Tracked by #90; all seven Windows/Linux CI jobs passed before merge.

### Fixed
- In the Phase 44 validity-window test fixture, compute relative expiration and
  verification dates from the runner's current date, not the historical
  2026-11-02 test-writing day. This avoids date-driven red CI on valid
  behavior and preserves the production stale-claim refusal. Tracked in #88;
  no production runtime, persisted user data or permissions are changed.

### Added
- **The pre-push loop can now see the v3 battery.** `scripts/battery_check.py` joins `GATES` in
  `scripts/health.py`: it runs `15_SYSTEM/scripts/test_hades.py`, reads the `checks:` summary that
  battery prints, and calls the tree undeliverable when the count is red, when the script is
  missing, when it hangs past `--timeout`, or when it exits without printing a summary at all. A
  gate that runs nothing is not a pass. In an installed brain home it prints one stated-skip line
  like the other repo-only judges, so `tests/test_phase16_host_independence.py` still counts exactly
  one OK per gate. `tests/test_phase49_battery_gate_watches_the_battery.py` drives it with synthetic
  batteries — green, red, silent, missing, hanging past the timeout, and a nonzero exit under a zero
  fail count — so all six verdicts are measured in milliseconds while the real battery's own seconds
  are spent only once, by `health.py`. The loop keeps two doors and says which it opened:
  `python scripts/health.py` runs every gate including the battery, and `python scripts/base.py
  --save` runs `health.py --fast`, which skips that one gate and prints the skip in the skipped
  gate's own OK line — a fast loop is a schedule, not a verdict, and it still refuses a red house
  as a base. This exists because `c889ee5` went public-red under the battery
  while the local suite and the health loop stayed green: the judge that catches what the loop
  cannot see was the one judge the loop did not run.
- **Phase 52, the cipher gets a door, and the door refuses more than it accepts.**
  `15_SYSTEM/scripts/backend/vault.py` and `scripts/vault.py` put the SBO1 container over the
  planes `private_planes` names in `15_SYSTEM/config/system.json`: seal, inspect, verify,
  restore, status and bench. A passphrase comes from a terminal, asked twice, or from a file
  that must resolve outside the repository — never from argv, where a process list keeps it.
  `scripts/vault_check.py` joins `GATES` in `scripts/health.py` and judges a witness by its
  shape, so the flag `encrypted_private_backup` cannot be turned on by naming a file; until a
  cross-machine restore is proved, the gate's honest line is that nothing claims the private
  planes are backed up. Refusals are a closed tuple, and a test walks the module's syntax tree
  to prove every rule is both declared and raised. Found by testing rather than reading: on
  Windows a redirected stdin answers `isatty()` with True for the NUL device, so an
  `isatty()`-only guard would have hung CI in `getpass` instead of refusing it. `safe_rel`
  moved from `scripts/base.py` up to `scripts/common.py`, so the installer, the known-good
  backup and the vault resolve paths under one rule. Symlinks inside the scope are refused
  rather than sealed, a damaged container is named without hiding the good ones, and a failed
  open moves no bytes and leaves no temporary file.
- **Phase 51, the cipher exists before anything is allowed to say it protects.**
  `15_SYSTEM/scripts/backend/crypto.py` implements ChaCha20-Poly1305 (RFC 8439) with a
  scrypt/PBKDF2 derivation layer and a versioned container — `SBO1`, kdf id, kdf params, salt, a
  header authenticated as additional data, one nonce/ciphertext/tag per file, a footer digest — in
  pure Python, because the standard library ships no AEAD construction and the executive law L-01
  keeps stdlib as the default. Its credibility is a test rather than a sentence:
  `python 15_SYSTEM/scripts/backend/crypto.py --selftest` re-checks the RFC's known-answer vectors
  and every tamper case on any machine, and `tests/test_phase51_chacha20_poly1305.py` — written
  red-first — runs in the suite CI executes on each push, so a change that breaks a vector fails the
  build. Refusals name the rule that stopped them (a closed set the code asserts against, so an
  invented reason cannot be forged), the ordering is built so a splice trips "tag" instead of
  describing the attacker's bytes, and there is no negotiation and no fallback: a kdf this build
  cannot run is refused out loud rather than replaced with a weaker one. `SECURITY.md` says plainly
  that the primitive is self-authored and **not third-party-audited**. The cost is measured, not
  claimed — `--bench --bytes 1048576` printed 0.902 MB/s on this machine on 2026-11-02, fine for the
  text planes and disqualifying for media. What this phase does *not* do is written in the same
  place: nothing real is sealed, there is no seal command over the private planes, no cross-machine
  restore proof, and all six capability flags are still `false`.

- **Phase 47, the owner's brief v4.0 became the constitution of record.**
  `00_START_HERE/CONSTITUTION.md` now holds the eight immutable principles with a pointer to the
  code that enforces each one today, the precedence ladder (constitution, then the owner's brief
  `00_START_HERE/PROJECT_CHARTER.md`, then the executive-law register, then `ROADMAP.md` and the
  code), the executive-law register L-01..L-10 with a version, a reason, an owner, an arbiter, an
  enforcement scope and a review path per law, a section that defines what does *not* count as
  evidence, and a debt table D-1..D-10 that names in the same file the promises this brain does
  not yet keep. Two decisions were written through the registry door and nowhere else:
  `09_OPERATIONS/decisions/DEC-3E9C1EE0-constitution-4-0-eight-princ.json` binds the eight
  principles to a manual revision path — the owner's explicit approval, a version record, a
  security audit — and says plainly that no automated cycle, this repo's nightly loop included,
  may amend them; `09_OPERATIONS/decisions/DEC-6F15207B-executive-laws-unlock-with-e.json`
  converts "stdlib-only, no app, no network, no port" from an eternal law into a revisable
  executive law that unlocks layer by layer, and only when six things are present at once: a named
  problem, a baseline measured on this corpus, a before/after win with its repeat counts, a cost
  and risk review, a bounded blast radius with a stdlib fallback and the flag still false, and a
  decision record. Three lines stay shut at any benchmark score: the core keeps working offline,
  nothing listens until a human presses approve, and no private record leaves the vault. This
  phase turned on none of the six capability flags and shipped no new engine — it moved the law
  from the top of a plan file into a document with an amendment procedure.

- **Phase 46, an installed brain can now be upgraded.** `python scripts/install.py --upgrade HOME`
  judges every path this engine ships against the record an install leaves inside the home
  (`15_SYSTEM/generated/install.json`, one sha256 per shipped path plus the engine's bytes for it,
  stamped under the new `install-manifest` contract), and prints one verdict per path: `UPDATED`
  where the engine moved and the home still holds what the installer wrote, `ADDED` for a path this
  version ships and the record never mentions, `ABSENT` for a file the home lost, `KEPT` for one a
  person edited here — and a `KEPT` file keeps both its old and its present digest in the next
  record, so the act after this one still knows it from an edit. `YOURS` is the stricter refusal:
  a file at a shipped path with no record of it stays byte-identical, is deliberately *not* written
  into the new record, the rest of the home still moves, and the run exits 1 with the list. Nothing
  is deleted, including what this engine stopped shipping: a recorded path the plan no longer holds
  is read the other way round (`judge_removed`) and named `ORPHAN` while the home still holds it —
  kept in the record so the next act reports it again — or `GONE` once it does not. A
  `--clean-orphans` flag was refused. The brain's own state is out of bounds by name (`PROTECTED_DIRS`) and a ship plan that
  lands a real file there stops the act — that is a bug in the installer, not in the home. A
  `--dry-run` proves its own innocence by comparing the home's tree fingerprint on entry and exit,
  every write is re-hashed from the disk it landed on, and each act appends one line to
  `15_SYSTEM/logs/install.jsonl`. This closes the limitation phase 35 left open: upgrading was a
  fresh folder plus a manual merge, so in practice homes did not upgrade.
  Suite: `tests/test_phase46_installer_upgrade.py`, including a real home installed, health-checked,
  upgraded, and re-checked with a note in `01_INBOX/` that survived it.
- **Phase 45, the roadmap judged by a script** — `scripts/roadmap_check.py --check` is the
  fifteenth health gate: every path a closed row cites must resolve, `file.py:123` must be a line
  the file has and `file.py::symbol` a symbol it defines (refused even in an open row, because an
  anchor states what is rather than what is planned), and an open row may still name a file it has
  not written. What the gate cannot see is named instead of counted green: a journal a script
  declares, and a path belonging to an upstream project, arrive as `NOTED` lines. In an installed
  brain home the roadmap is the source repo's plan rather than a promise the home made, so the gate
  says so and exits 0. Suite: `tests/test_phase45_roadmap_citations.py`.

### Changed
- **The refusals in `ROADMAP.md` are reasons about evidence now, not about size.** The header law
  and the three refusal rows that had cited "the unnecessary dependency charter forbids" — the
  external parsing engine, the database-and-app-server stack, and the HTTP/server layer — state
  instead which of the constitution's six conditions is missing, and each names the measurement
  that would change the answer. Calling a subsystem too complex is the one argument the brief's
  section on revisable executive laws forbids, and it was the argument this repo had been making. The precedence ladder in the
  header now points at `00_START_HERE/CONSTITUTION.md` rather than at itself, so a conflict is
  filed against the constitution with its section number instead of being resolved silently by
  whoever last read the plan.

### Fixed
- **The v3 battery now judges the closed run plane, and it was CI that noticed.**
  `15_SYSTEM/scripts/test_hades.py` — the battery only GitHub Actions runs — failed two of its own
  checks on `c889ee5` while `scripts/health.py` and the unittest suite stayed green locally. Both
  checks had been written while the door leaked: one asked `runs_list` for the promoted run's id on
  the wire, the other asked `doctor_status` to count `12_RUNTIME/agent_runs`. Phase 49 closed that
  plane, so the assertions were the contract of the leak. The two checks are replaced by four
  stricter ones: `isError`, the rule name `12_RUNTIME` in the refusal, the human command
  `runs.py list` in it, `doctor_status` answering `"read": false` with `"denied_by"`, and
  `run_id not in text` — a closed plane that still echoes one id fails. `ROADMAP.md` records the
  reversal and names the remaining gap: the pre-push loop cannot see this battery.
- **The MCP door stopped reading the planes its own access law denies.**
  `15_SYSTEM/scripts/backend/access.py` had denied `12_RUNTIME`, `.brain-data`, `.kb`,
  `15_SYSTEM/generated`, `15_SYSTEM/backups`, `13_LAB`, `14_CANDIDATES` and
  `09_OPERATIONS/clients_metadata_only` to agents since phase 21, and `mcp_server.py` — the one
  surface an outside harness actually calls — read four of those paths anyway. Measured on this
  tree before the change, with one run recorded by `15_SYSTEM/scripts/runs.py`: `runs_show`
  answered `{"run_id": "RUN-F9A34E51", "agent": "AGT-CD4E8AA8", "status": "completed", "steps": 1,
  "goal": "feed the door"}` and `runs_list`/`doctor_status` enumerated the same plane;
  `source_search` returned the whole stored body of a private `.brain-data` source, not a citation.
  Now the door asks the law instead of restating it: `access.denial(root, path)` answers
  `None` or the *name of the rule* that said no, `access.readable()` is that same function
  (`readable ⇔ denial is None`, so one law has two answers and no second list to drift), and a
  refused read puts the rule name and the human view on the wire and nothing from inside the plane.
  `source_search` answers with source id, kind, origin, filename, `imported_at`, the body's byte
  length and a 400-character excerpt flagged `excerpt_truncated` — the §7 minimal-context rule, and
  consistent with `source_import`, which had always refused those paths. `doctor_status` reports
  `runs.read: false` with `denied_by: "12_RUNTIME"` rather than a run count. Phase 22's passing
  assertions (`assertFalse(isError)` over `runs_list`) were the contract of this leak, not of the
  design; that test now asserts the refusal, and `ROADMAP.md` records the reversal. Pinned by
  `tests/test_phase49_door_reads_its_own_law.py`, written red first — it fails on `4a71da4` with
  the leaked run id in the text and the refusal naming no declared rule.
- **A recorded known-good base no longer redraws the link graph as a pile of islands.**
  `python scripts/base.py --save` copies the tree into `15_SYSTEM/backups/known-good/<stamp>/`, and
  `scripts/link_check.py::classify_links` built its stem index over that copy as if it were the
  vault: every note appeared twice, so the resolver's collision rule — the rule whose whole job is
  to refuse guessing which of two files the author meant — fired on links written unambiguously.
  Measured on this tree with a base on disk, before the change: the 7 exact wikilinks in
  `02_WIKI/indexes/reference-maps.md` came back `ambiguous`, the readout reported 22 degree-0 notes
  and no hub; after it, the same command reports 22 notes with 7 edges, 0 ambiguous, 0 broken and
  `02_WIKI/indexes/reference-maps.md` as the hub. `link_targets` takes the recorded base out of the
  target index and nothing else out: the test is vault-relative, so a snapshot opened as its own
  vault still resolves its own links, and it is scoped to the snapshot root alone, so two live notes
  that genuinely share a stem are still refused instead of bound to whichever path sorts first.
  Invisible in CI and in `python scripts/health.py`, because that plane is gitignored and every
  vault gate defaults to `vault-template` — only the machine that had just recorded a base could see
  it. Pinned by `tests/test_phase47_link_graph_plane.py`, written red first.
- Eight roadmap rows cited `backend/…` while the repo holds those files under
  `15_SYSTEM/scripts/backend/…` — true as names, unopenable from a clone. They now carry
  repo-relative paths, the law `scripts/common.py::clone_readable` already enforces on generated
  artifacts.
- The phase-36 rows for the independent eval, the before/after claim and the recovery path still
  read `- [ ]` after the code they describe had shipped and been released: `git tag --contains
  3cb54da` answers `v0.1.0 v0.2.0`. Ticked against the tree with the command, symbol and test each
  claim lives in — and the check caught two wrong claims in the draft of the correction itself.
- The new gate found two false greens in its own first draft: a bare folder name resolved to an
  empty basename, which every tracked file "declares", and a directory's last word was accepted as
  a declared witness. Both are pinned by tests now.
- Four defects the phase-46 installer showed before it could ship, each now refused by a test. The
  first record was written with text-mode writes, which on Windows puts `\r\n` on the disk and left
  the manifest disagreeing with the bytes it had just hashed — the install printed "record did not
  read back" and the whole upgrade path was unreachable; every byte the installer lays is written
  and re-hashed in binary now. Second: a home's re-measured documents could never agree with the
  repo's copy, so *every* upgrade reported `README.md`, `HANDOFF.md` and `00_START_HERE/START.md` as
  pending; the record holds the engine's own bytes beside the home's, and
  `tests/test_phase46_installer_upgrade.py::test_a_second_upgrade_moves_nothing_at_all` is the witness. Third: the first draft of `YOURS`
  recorded the colliding
  file's bytes as "what the installer wrote", which would have made the next upgrade overwrite a
  person's note — an unowned file is now left out of the record on purpose, and the same row keeps
  its `UNCHANGED`-stopping power by exiting 1. Fourth: the agent doors were the last text write
  left, and reading a door as *text* re-encoded its newlines too, so a fresh home held a door whose
  bytes were not the engine's — invisible to an upgrade, which compares the home against what the
  *record* said the engine shipped, and the record had just learned the mangled bytes. `write_doors`
  now lays the ship plan's own candidate bytes, and
  `tests/test_phase46_installer_upgrade.py::test_a_real_install_lays_the_engines_bytes_at_every_shipped_path`
  fails on the old code (`.cursor/rules/agents.mdc`, checked by reverting the line and re-running).

## [0.2.0] - 2026-11-02

The release where the gates stopped describing the repo and started judging its own shapes: the
link graph labels every edge and refuses an edge it had to guess at, every generated JSON file
carries the contract that wrote it, and the registry can finally fill the `repo` block its own
zone law demands — which is how this repo registered itself. The number is derived, not chosen: 4
commits after `v0.1.0`, the highest level in their subjects is `feat`, so
`python scripts/version.py --bump auto` wrote `0.2.0` into `VERSION` and `pyproject.toml`; the
live test, gate and record counts are the measured block in `README.md`, refreshed by
`python scripts/doc_report.py --write`, not numbers remembered here.

### Added
- **The link graph is measured, printed and gated.** `scripts/link_check.py` now labels every
  edge the way graphify's schema does — `extracted` (the author's text names exactly one file),
  `inferred` (the resolver normalised to reach it), `ambiguous` (the text cannot answer "which
  file?") — and the old resolver's habit of keeping whichever colliding path sorted first is gone:
  a colliding stem escalates, with every matching file named. `--readout` reports the navigation
  shape (components, degree-0 notes, bridges, the god-node) with the path behind every number, and
  the default link gate prints the counts next to its verdict so `OK — 0 broken links` can never
  be read as "reachable by links". `health.py` runs the readout as a gate of its own and
  **refuses** while an ambiguous edge is open, because a graph the tool had to guess at is not a
  healthy graph.
  degree-0 stays a readout, not a defect: `scripts/kb.py` full-text search reaches those notes —
  what an orphan cannot do is be *arrived at* by a reader following links. Proven by
  `tests/test_phase44_edge_confidence.py`, `tests/test_phase44_link_graph_readout.py` and
  `tests/test_phase44_readout_is_a_gate.py`.
- **The registry can fill the `repo` block its own zone law demands.** `03_PROJECTS/README.md`
  says code does not live in the brain and that a manifest carries `repo.path`, `repo.remote` and
  `repo.branch`; `hades.py` created that block with three empty strings, `set` refused every
  dotted field name, and `new --code-repo` was a flag no line of code ever read. The schema now
  declares the keys inside the object (`object_keys`) for `project` and `app`, `set --field
  repo.remote` amends one key through the same plan/approve audit trail as a flat field, an
  undeclared key is refused by naming the declared ones, `doctor` catches a key hand-written
  inside `repo`, and `--code-repo PATH` reads the address out of that folder's own git — refusing
  to plan anything when the folder has no git instead of inventing an address, and recording `.`
  when the code is the brain's own folder so a self-record stays true on every clone. Proven by
  `tests/test_phase44_registry_fills_its_repo_block.py`.
- **Second Brain OS is registered in its own brain.** `03_PROJECTS/active/PRJ-0E1F18BD-second-brain-os/project.json`
  is a `public` project record whose `repo` block came from `git` on this tree, whose evidence
  paths are the files that implement it, and which is the `parent_ids` target of every skill,
  agent, schedule, MCP door and workflow the repo ships — before this the registry was a flat list
  of unconnected records, which is the same isolation the link readout measures for prose.
  `python 15_SYSTEM/scripts/hades.py graph` prints the nodes and typed edges it found, and
  `hades.py doctor` judges every record with `errors: 0 | warnings: 0`; neither number is typed
  into this document.
- **Every generated JSON file says which contract wrote it.** `scripts/schema_stamp.py` stamps
  `schema_version` at write time (the table in that file names each writer, its file and the fields
  that prove the file is what it claims) and `--check` refuses a stamp that is missing, stale or
  claimed by no contract instead of letting a reader mis-parse quietly and print green. The
  migration ran once, from this gate's own `--stamp --write`, and `scripts/loop.py` now stamps the
  ratchet history it appends rather than leaving a later pass to paint a number on it. Hand-authored
  JSON is not silently exempt: the check prints those files as `AUTHORED`, each with the reason it
  is not generated output. Wired into `health.py`; proven by `tests/test_phase44_schema_version.py`.

### Changed
- **Two documents stopped typing a number they could not keep.** The memory-plane map and
  `ROADMAP.md` phase 44 both stated the lesson ledger's size as measured ("27 row(s), 27
  evergreen"); the 28th lesson — added for the CI defect below — made both sentences false on the
  day they were written, and turned a true rule into a failing assertion. The count now comes from
  `python scripts/memory.py --windows` wherever it is needed, the docs point at that command
  instead of quoting its output, and a test refuses the map if it ever freezes a count again. A
  measurement that has to be re-typed by hand is not a measurement.
- **Issue #20 closed, and the last row that was not.** The charter §5/§11 issue had carried a
  `partial` note since phase 41 saying the conversation-memory criterion was unmet. Re-audited
  against its own four acceptance criteria, each one is met and each is proved by a command run on
  this tree: the plane map table, `scripts/plane_check.py` as a health gate with four refusal tests,
  `kb.py search` returning only tracked repo prose with the golden set green, and the eleven-step
  path in `02_WIKI/reference_maps/conversation-memory-path.md` — import, adapter projection,
  propose, evaluate, human `--approve`, recall, MCP doors — with the refusal and the test named per
  step. What is *not* shipped is now stated as a refusal rather than a gap: no door reads a live
  session by itself, because "No automatic session discovery" (phase 26) and charter §2 forbid a
  scanner in the write path. `python scripts/issues.py --fetch` reports the ledger and GitHub in
  agreement: 22 issues, 0 open.

### Fixed
- **The workflows now clone what the version gate judges.** Cutting `v0.1.0` produced two CI runs
  of the same tree with opposite verdicts: the tag-event run was green, and the branch run 1m
  later — on the very next commit — died in `scripts/health.py` with
  `VERSION 0.1.0 is not tagged and CHANGELOG.md's [Unreleased] declares nothing`. Neither answer
  was wrong. `actions/checkout@v7` clones at depth 1, and a depth-1 clone of a commit that is not
  the tagged one carries **no tags at all**, so from the first commit after any release the gate is
  handed a history with its own release missing and refuses a version that *is* published. Both
  workflows now pass `fetch-depth: 0`, and
  `tests/test_phase44_ci_reads_its_tags.py` reproduces the whole thing in three throwaway local
  repos: the shallow clone cannot `git describe` the tag and the gate refuses it for a reason that
  is not true of the repo, while the full clone of the same commit passes. One test reads the
  workflow text, so the fix cannot rot back into a depth-1 clone unnoticed.

## [0.1.0] - 2026-11-02

The first release that answers the whole brief: the repo keeps its own version, tells a stranger
how to work in it, judges its own designs with reviewers that share no context with the author,
and borrows only the schemas peers proved. 696 tests, 12 gates, 0 open issues. The number is
derived, not chosen: 137 commits after `v0.0.3`, the highest level in their subjects is `feat`, so
`python scripts/version.py --bump minor` wrote `0.1.0` into `VERSION` and `pyproject.toml`.

### Added
- **Phase 44, three of six rows: peer practices that cost no dependency** —
  `15_SYSTEM/scripts/backend/tools_kit.py` now carries one closed behaviour vocabulary
  (`read_only` / `idempotent` / `destructive`) and a class that declares nothing is carried as
  `destructive`, the worst case, rather than read as harmless;
  `python 15_SYSTEM/scripts/mcp_server.py --check-tools` audits 13 door tools, 6 engine tools and
  3 agent records against the actor `tool_allowlist` (measured: 0 destructive).
  `rules/memory.schema.json` is version 3 and a lesson may carry `verified_at` / `expires`:
  a stale row is a named gate row (`--check` refuses, `--windows` counts, `--recall` marks, and
  the MCP `memory_recall` door appends the identical mark, so an agent never sees a friendlier
  answer than a human does). Measured before the default was chosen — 27 rows, all evergreen,
  because no shipped row states a window; keying the rule on `date` would have aged every row by
  a claim it never made. `kb.py --related` ranks the FTS5 terms `ingest` already stored by inverse
  document frequency and prints the evidence each line stood on.
- **`kb.py --related` refuses the repo's own surface** — both a plain overlap ratio and the
  IDF-weighted one answered "what is near the memory-planes map?" with ROADMAP.md, CHANGELOG.md
  and HANDOFF.md. The cause was taxonomy, not arithmetic: a document at the repo root mentions
  every word, so it is near every note and about none. `--related` now ranks only notes inside
  zones, states how many shelf documents it skipped (10 here, from 56 indexed notes), refuses when
  the note you named is one of them, and leaves `search` untouched — that question is *where is
  this written*, not *what resembles it*.
- **Phase 43: the elephant/goldfish method is a gate, not a slogan** — `scripts/goldfish_check.py`
  judges a review artifact: five stages in order, a roster where a reviewer that did not run is
  never counted as zero findings, finding ids that cannot move between rounds, a comprehension
  section that must paraphrase in two named headings, a `declined` row that must carry a reason, an
  escalated row that must be escalated, and every citation checked with `clone_readable()`.
  8 personae in `11_CONTROL/reviewers/`, three skills (`elephant-draft`, `goldfish-review`,
  `drift-report`) registered through the plan door, and the stop condition kept verbatim: a harness
  with no subagent tool is told that a review in the same context is not a Goldfish review.
  `--self-test` runs 12 cases (the honest artifacts pass, every lie is refused); the gate is the
  twelfth entry of `health.py`.
- **Phase 42: an eval that cannot share examples with training** — a tracked independent eval set
  (`tests/fixtures/retrieval-independent-eval.json`, 6 self-contained cases with their provenance
  written in the fixture) and `sources.py dataset-eval-gate`, which exits 1 and prints the training
  id when any eval case id appears in the training manifest. `compare-benchmarks --claim --margin`
  returns `IMPROVEMENT` only when every repeat raises **both** recall and MRR past the margin, and
  refuses a claim with no recorded base before it renders a verdict.
- **Phase 41: the manager agent, and a conversation path that says what it does not do** —
  `AGT-7DE1AB28` is a registered proposer whose `tool_allowlist` holds no approve tool, so
  `Registry.execute` refuses its own plan and the human stays the only signer;
  `skills/conversation-memory` plus `02_WIKI/reference_maps/conversation-memory-path.md` give one
  row per step (import → rebuild → propose --quote → evaluate → approve --approve), where an
  invented quote is refused and nothing ever scans a history folder.
- **Phase 40: the lessons ledger grew a plane and learned to disagree** — `plane` on every row,
  read from `system.json → memory_planes` so no second taxonomy can drift, with an additive
  `--migrate-planes --write` that typed all 27 shipped rows and deleted nothing; and a contradiction
  rule measured before it was written (325 active pairs, closest same-plane shared-topic pair 0.31
  and *agreeing*, opposite verdicts 0.00 at every threshold), so the bar is cue Jaccard >= 0.50 and
  the shipped ledger holds 0 contradictions — nothing was reclassified to make a number look good.
- **Phase 39: the two missing reference maps** — `harness2-to-hades-map.md` (15 rows) and
  `claude-obsidian-to-hades-map.md` (16 rows) in the shape the SuperAGI map already had, every
  adopted row citing the script **and** the test. Enumerated by `02_WIKI/indexes/reference-maps.md`
  instead of wikilinked, because `install.py` ships `reference_maps/` but not `indexes/`, so a link
  inside a map would dangle in every installed home.
- **Phase 38: a stranger is told how to work here** — `CONTRIBUTING.md` rewritten as the protocol
  in working order (issue first, test first, the registry door, the shelf, `doc_report.py --write`
  in the same commit, the version derived not typed, a goldfish review last) with all twelve gates
  named in a table, and `.github/CODEOWNERS` over the files where a quiet edit does the most damage.
- **The method the owner asked to apply to the repo itself** — `02_WIKI/reference_maps/` now answers
  for four peers rather than three: `elephant-goldfish-to-hades-map.md` and
  `graphify-to-hades-map.md` record what was taken (EGM's stages, isolation and stop condition;
  graphify's edge confidence, ambiguity-escalates-to-a-human and stamped `schema_version`) and what
  was refused with the reason (plugin packaging; ~40 tree-sitter grammars, NetworkX, graspologic,
  an LLM semantic pass, a 3.10 floor).

- **Phase 37, second half: the python floor is now something CI can install** — on 2026-11-01
  `ubuntu-latest` moved to Ubuntu 26.04, `actions/python-versions` carries no CPython 3.9 x64
  build for it, and **every `ci` and `loop` run died inside `setup-python`** (five red runs,
  24 seconds each) while `python scripts/health.py` stayed green on the owner's machine and the
  README went on claiming "Python 3.9+". The nightly improvement loop — the promise the repo is
  named for — had silently stopped. `scripts/ci_floor.py` now compares four places in one run:
  `requires-python`, the ci matrix, the runner images those jobs ride, and the
  `| python floor |` rows in README and START. No workflow rides a floating image any more, and
  fifteen tests in `tests/test_phase37_ci_python_floor.py` each break one of those four places
  and read the refusal.

- **Phase 37: the version is measured, not typed** — `VERSION` said `0.0.3`, the README opened
  with `HADES OS v0.01`, and nothing compared either of them to `pyproject.toml`, the badge,
  `CHANGELOG.md` or the tag the clone carries. `scripts/version.py --check` now judges all five
  places at once and refuses by name, and `--bump auto` derives the number from the work: commit
  subjects since the last tag, highest signal wins (`feat!`/`BREAKING CHANGE` → major, `feat` →
  minor, `fix`/`perf` → patch, `docs`/`test`/`chore`/`refactor` → `NO_BUMP`). Measured on this
  folder: **121 commits after `v0.0.3`, level `minor`, so the next release is `0.1.0`** — a
  number no author can inflate, and one a fresh clone can recompute. At 0.x a breaking change
  raises the minor (SemVer §4) because the jump to 1.0 is the owner's call. The gate never tags:
  it prints `git tag v… && git push origin v…` and leaves that promise to a human. Sixteen tests
  in `tests/test_phase37_version_gate.py`, including a check over this repo's own number.

- **Phase 36, step one: a dataset that refuses what the owner did not offer** — the roadmap's
  next phase starts with the only part that can be checked without training anything.
  `15_SYSTEM/scripts/backend/dataset.py` (behind `sources.py dataset-share`, `dataset-build`,
  `dataset-verify`) builds `examples.jsonl` + `manifest.json` from imported source records: a
  record must be marked shareable by an explicit `--approve` (the bare command is a preview and
  writes nothing), an unmarked record is refused with its id instead of being silently
  included, and every example cites its `source_id` plus a byte range into that record's own
  `raw.txt` — checked at build time by slicing the bytes back out. The manifest records the
  source ids, kinds, origins, checksums, per-source example counts and a digest over the
  examples, so a run reproduces from records alone; `dataset-verify` re-hashes a folder and
  reports the mismatches. Eight tests in `tests/test_phase36_dataset.py` hold it, including a
  Persian record (the range is computed in UTF-8 bytes, not characters) and a tampered file.
  Nothing is trained and no improvement is claimed: the independent eval, the before/after
  report and the recovery path are still listed as planned.

- **The issue ledger: a status a clone can read** — the brief's "if it is resolved, show it in the
  repo" had no mechanism, so issue #39 stayed fixed in a commit message and open on GitHub.
  `15_SYSTEM/config/issues.json` now records all 22 issues with a state (`open` / `partial` /
  `fixed` / `closed`), the upstream state at the last snapshot, the fix commit, the evidence
  paths, and — for every row that is not finished — one sentence naming what is missing.
  `scripts/issues.py` renders `00_START_HERE/ISSUES.md` (Persian), and its `--check` joins the
  health gates (nine now): a `fixed` row without a commit or without a clone-readable evidence
  path is refused, so is a `fixed` row that hides why the upstream issue is still open, so is an
  `open` row with no gap, and so is a page that drifted from the ledger. `--fetch` is the only
  networked path and it never writes; it prints the drift between the ledger and
  `api.github.com` when the ledger is a stale snapshot. An installed home has no ledger and the
  gate stays quiet there, like the other machine-plane gates.

- **Three open issues closed by fixing the sentence, not the permission** — `tests/test_phase36_doors_tell_the_truth.py`.
  **#15** `state_fingerprint` counted `15_SYSTEM/generated/`, so one `hades.py index` aged every
  recorded probe and no clone could reproduce a saved base; regenerated output is now
  paperwork beside the quarantine shelf and the backups folder, and a real edit still moves
  the identity. **#16** a refused `export` called every denied path "the denied machine plane",
  which is false for `09_OPERATIONS` (`"plane": "human"`, excluded because it holds client
  data) and teaches an agent that the folder is disposable; the refusal now names the rule
  that fired (`denied_for_default_context` / `generated_denied`) and the plane the zone
  declares, and `AGENTS.md`, `00_START_HERE/ACCESS.md` and `SYSTEM_MAP.md` deny the whole zone
  the config denies — with a test that compares the three documents to
  `denied_prefixes()`, so the list cannot split again. **#17** `memory.py --add --supersedes
  <unknown>` wrote the row and let `--check` refuse a lesson already in the ledger and already
  rendered into `MEMORY.md`; retirement is validated at the door now (unknown id and
  self-retirement both refused, nothing written), while the gate keeps its "never held" rule
  for a phantom that arrives any other way. The HADES battery's export check asserts the new
  wording: 120/120.

- **A Persian audit of the five-phase brief, with a downloadable copy** — `00_START_HERE/PLAN_FA.md`
  maps each phase of the owner's brief (audit, knowledge core, harnesses and multi-device sync,
  evidence-backed learning, ecosystem and automation) to the roadmap phases that implement it,
  gives the command that proves each row, and names every gap that is still open. The same
  document ships as `downloads/second-brain-plan-fa.pdf`, a shareable PDF built from the
  markdown, and the README leads with a Persian description and links both. `ROADMAP.md` gains
  phase 36 — the fine-tuning pipeline the brief defers — as *planned*, with its acceptance
  criteria (dataset manifest, independent eval, before/after report, recovery path) and its
  refusal: no "better model" claim without all four.
- **`source_import`: the harness door records a source, not only reads one** — the brief asks for
  a stable interface to register as well as search sources from CLI *and* MCP; `source_search`
  existed and the recording path was CLI-only. `15_SYSTEM/scripts/mcp_server.py` now exposes
  `source_import` (thirteen tools): one explicitly named UTF-8 file inside the brain becomes a
  private source record with its raw bytes, kind, origin, filename and import time; the same
  bytes and origin are idempotent; the index is rebuilt after a successful import; and a path
  outside the brain or inside a denied zone (`.brain-data`, `.git`, secrets, runtime/lab/
  candidate/backup) is refused before any record exists. Nothing is scanned or fetched. Two
  tests in `tests/test_phase22_harness_bridge.py` prove the round trip and the refusals, the
  HADES battery asserts the thirteen-tool set, and the MCP registry record, integration docs,
  canon and lesson ledger carry the new door.
- **An installed brain is a whole brain** (phase 35, issue #27) — `scripts/install.py` now
  lays the same sixteen zones the repo uses (read from `15_SYSTEM/config/system.json`) and
  ships what the gates judge: `15_SYSTEM/scripts` (registry door, backend, MCP),
  `15_SYSTEM/schemas`, `15_SYSTEM/memory`, `15_SYSTEM/integrations`, `15_SYSTEM/migrations`,
  `15_SYSTEM/templates`, `02_WIKI/reference_maps`, `AGENTS.md`, `.gitignore` and
  `tests/test_installed_home.py`. The home's `system.json` says `"home": true` and binds every
  memory plane's `test` to that one proof, so a fresh install can re-run its own map. The
  phase-16 test now runs the *installed* `health.py` (it used to run the source repo's script
  with `cwd=<install>`, so every root-only gate judged the repo and a home with no readers,
  no map and no registry door passed) and compares the installed zone shape to the source.
  Measured in a fresh home: 16 zones, 6 plane stores, health 8/8 OK (12 tracked stores, 4
  disposable absent by design), 5 tests, `NO_ENTRY` from `memory.py --recall`.
- **Registry hardening leftovers** (phase 30) — a `supersedes` link is a structural change, so
  `hades.py link … --supersedes` now writes a `mode: link` plan carrying the record's
  `pre_image_sha1` and applies only with `apply --plan … --approve`; a file changed after
  planning is refused, and the resulting amendment is recorded on the record. Additive
  relations (`depends-on`, `related`, …) still write through, because they never retire a
  record. `doctor` walks `supersedes` as a directed graph and errors on every cycle
  (`A -> B -> A`), with self-edges left to the existing self-supersession check and dangling
  targets ignored. All 34 kinds now own a status set in `system.json` (20 sets added;
  `default` stays for a kind added without one), and `GUIDE_FA_EN.md` lists every set in both
  languages. `scripts/probe.py` refuses `scripts/base.py` (recovery belongs to the owner) and
  `scripts/install.py` (writes outside the repo) by name. Nineteen tests in
  `tests/test_phase30_registry_hardening.py`; the cycle walk is read-only, and a plan is still
  only as honest as the human who approves it.
- **The embedding seam, inert by default** (phase 29, charter §2) — `backend/vector.py` ships
  one `Embedder` interface, `cosine`/`rank` as pure functions, and `HashingEmbedder`: a
  sha256 bag-of-words double, deterministic across processes, marked
  `production = False`. No model, no dependency, no socket — a test patches `socket` to
  prove it. `scripts/vector.py status|probe` reports OFF/REFUSED/ACTIVE and demonstrates the
  double on a fixed corpus; `scripts/vector_check.py` is the eighth health gate. Activation
  needs `feature_flags.vector_search: true`, a shape-checked evidence file
  (`11_CONTROL/vector/activation.json`: `verdict: beats_bm25`, BM25/candidate rates, a
  positive margin that equals their difference, ≥5 cases with a 64-hex case-set digest,
  `approved_by`, `approved_at`), and a registered production embedder. The last door cannot
  open today, so perfect evidence still refuses — installing a model is the owner's act.
  Twenty-two tests; the double's lexical overlap is not evidence for semantics.
- **One clock for the rituals** (phase 28, charter §6) — a first-class `schedule` registry kind
  (`11_CONTROL/schedules/*.json`) holds the spec objects the backend already knows how to read,
  so the nightly loop (`SCH-0D1E2F3A`, `{"daily_at": "02:00"}` UTC, target `scripts/loop.py`)
  and the weekly ritual (`SCH-0D1E2F3B`, `{"every_minutes": 10080}`) are governed definitions
  rather than cron comments. `python scripts/loop.py --due [--target …] [--now …]
  [--last-run …]` imports `backend/schedules.is_due` (no second definition of "due"), exits
  0 = due / 3 = not due / 1 = refused (no record, paused, unreadable spec) and writes nothing;
  history rows now carry `ran_at` so a same-day rerun can be judged. The two skills say the
  command, and the Actions workflow asks for a verdict only on `schedule` events — a manual
  dispatch stays a human override. Stated limits: the weekly check derives its last run from
  `git log --grep='ritual(weekly)'`, and a record says *when*, not that a runner exists.
- Phases 31–34 — **private source memory**: `15_SYSTEM/scripts/sources.py` imports one
  explicitly selected UTF-8 file (or a reviewed manifest) into `.brain-data/sources/<id>/`
  as authoritative raw bytes plus metadata (kind, origin, filename, import time, format,
  checksum); the id is content-addressed, so re-import is idempotent and changed content is a
  new record. `rebuild` validates every record and atomically replaces a disposable SQLite
  index; `search` is BM25-style with a legacy scan path and returns provenance with each hit.
  Conversation adapters read Codex JSONL, Claude Code stream JSON and Cursor stream JSON,
  indexing user/assistant text only and refusing mixed sessions.
- **Evidence-backed private lessons** — `backend/learning.py` accepts a proposal only with an
  exact quote present in an imported source, evaluates source checksum + quote + whether the
  query retrieves that source, and writes a receipt only after explicit `--approve`; `recall`
  returns approved lessons with their origin. The evaluation says what it does not prove.
- **Retrieval measurement** — `backend/retrieval_eval.py` reports mean recall and MRR on an
  independently curated case set and refuses to compare reports with different cases, limits
  or corpus hash; any regression fails the verdict.
- **Transfer between devices** — `backend/source_sync.py` previews an explicit folder copy,
  names conflicts (same kind + origin, different content; copied only with
  `--allow-conflicts`), keeps both versions, previews approval receipts but imports them only
  with `--include-approvals`, and `verify-copy` compares every record byte-for-byte.
- **Capability catalogue and install gate** — `15_SYSTEM/scripts/capabilities.py` inventories
  active registry skills/plugins/MCP records/extensions and built-in tools with origin,
  permissions, harness approvals and installation state; `backend/install_skill.py` plans by
  file digest and applies only with `--approve`, never replacing a directory.
- **Default read boundary** — `backend/access.py` refuses `.env`, key/credential filenames,
  `.git`, `secrets`, the runtime/lab/candidate/backup zones and client metadata in file reads,
  search and MCP resources; MCP resources now serve only the advertised list. This is a
  tool-level path guard, not OS access control or a secret scanner.
- MCP door grows from 8 to 12 tools: `source_search`, `lesson_propose`, `lesson_recall`,
  `capabilities`. Write tools remain proposal-only; approval stays local.
- **The eight memory planes, mapped and gated** (phase 26, charter §5) — `system.json` →
  `memory_planes` declares per plane the tracked store a clone must open, the disposable store
  that may be absent by design, the reader, the proving test and the map row;
  `02_WIKI/reference_maps/eight-memory-planes.md` is the human map with a measured inventory of
  what the clone can open today; `scripts/plane_check.py` is the seventh health gate and refuses
  a dropped plane, a missing tracked store, an empty folder without `.gitkeep`, or a
  reader/test/map that no longer exists. Disposable stores (`12_RUNTIME/`, `.brain-data/`,
  `.kb/`) are reported, never required. Gaps filed as #24 (no contradiction detection), #25
  (lessons carry no plane field); #20 keeps the conversation-extraction path and `kb.py` open.
- **`kb.py` searches this brain's own prose** (phase 27, charter §1) — `ingest` now indexes the
  tracked, clone-readable human plane instead of `vault-template`: the machine plane
  (`11_CONTROL/`–`15_SYSTEM/`), the template, dot-folders and rendered agent doors are excluded
  by the same boundary `common.clone_readable()` declares. Frontmatter is stripped before
  indexing, so a snippet opens on the first sentence instead of on `id:`/`topics:`; matching
  folds case and NFKC and maps Arabic `ي`/`ك` to Persian `ی`/`ک`, while displayed text keeps
  its original bytes. Every hit carries its zone and title; a missing index prints one line
  instead of answering, and an index built by an older corpus rule is refused until
  re-ingested. Measured here: 43 notes into a 1.4 MB index, ingest 81 ms, median query
  3.8 ms over 40 runs (max 5.9 ms); an installed home indexes its own 28 notes. The phase-4 golden gate is repointed at
  repo paths and `tests/test_phase27_repo_corpus.py` adds ten tests (boundary, installed home,
  shared golden fixture).
- **Retirement is visible where a record is read** (phase 27 item 2) — measured before the
  change in a scratch vault: `list` showed 4 rows, 1 retired, 0 markers; `search --query
  provider` returned 5 hits, 1 of them the retired record's file, 0 markers. Now `list` prints
  `records: N (active A, retired R)` and appends `[retired by ID]` to the retired row;
  `search` appends the same marker to the retired record's own file and names the count in its
  summary; `show` prints `# retired by: ID`; the MCP door (`registry_list`, `registry_show`)
  carries `superseded_by` / `retired by`. Nothing is deleted or hidden — retirement stays a
  verdict, not a delete. Four tests cover the three CLI surfaces and the MCP door.
- Phase 7 — continuous improvement loop: `scripts/loop.py` (one-cycle ratchet:
  integrity/test/inbox/gap/hygiene signals → candidate report → prev-run compare;
  REGRESSED verdicts are loud, P1 exits non-zero), `skills/loop`, and a nightly
  GitHub Actions workflow committing candidate reports to `14_CANDIDATES/loop/`.
- Phase 8 — public project standard: community files (SECURITY / CONTRIBUTING /
  CODE_OF_CONDUCT / issue + PR templates / Actions dependabot), README badges,
  Keep-a-Changelog changelog, GitHub topics + Release for the existing tag, and
  the **HANDOFF standard**: `scripts/handoff.py` (machine-written §1 State
  Snapshot + frozen §8 Rules; model-owned §2–§6 refresh in place) — a formal,
  test-gated work-resume artifact any agent or human can trust.
- **Repo memory** (issue #7) — `scripts/memory.py` + `rules/memory.schema.json`:
  an append-only `15_SYSTEM/memory/lessons.jsonl` ledger with verdict, evidence,
  cue and confidence, a generated root `MEMORY.md` table, `--recall` retrieval that
  answers `NO_ENTRY` instead of inventing a lesson, `--supersedes` retirement, and a
  health gate that fails when the document drifts from the ledger.
- **One law, every host** (issue #8) — `AGENTS.md` is the canon and
  `scripts/sync_hosts.py` renders it into `CLAUDE.md`, `GEMINI.md`,
  `.github/copilot-instructions.md`, `.cursor/rules/agents.mdc` and
  `.windsurf/rules/agents.md`; `--lint` refuses a door that points at a file that
  does not exist, `--check` fails on drift, and hosts that read `AGENTS.md`
  natively get no duplicate file. Nothing in the pack requires an app: the prose
  gates (`common.is_prose`) keep README/SKILL/rules out of the note counts, so an
  installed brain (`scripts/install.py`) is green standalone with no editor, no
  network and no plugin.
- **Typed, counted candidates** (issue #9) — `rules/candidate.schema.json` plus
  `scripts/candidate_check.py`: every shelf row is `invariant` or `domain`, carries
  the real execution that probed it, and the ledger's count identity
  (`proposed == adopt + revise + drop + keep_base + open`) is checked against the
  folder, so a missing row cannot be papered over. A `verdict: proposed` row is
  legal on the shelf and never promotable.
- **Measured documents** (issues #4, #10) — `scripts/doc_report.py` writes and owns
  the block between two markers in `README.md`, `HANDOFF.md` §1 and
  `00_START_HERE/START.md`; `--check` is the sixth health gate, so a stale number
  fails CI instead of becoming project lore.
- **Control plane populated** — `11_CONTROL/skills/SKL-*` and `11_CONTROL/agents/AGT-*`
  registry records for the skills and agents this pack actually ships, created only
  through `plan → apply --approve`; a record whose body cannot be found is now a
  doctor error (`entrypoint` must resolve), and `hades.py sync` follows the pointer
  instead of keeping a copy that can drift.
- Cold-start procedures as skills: `skills/first-session` (what to do when all you
  were given is the repo URL), `skills/memory`, `skills/self-audit`.
- **Evidence portability law** — `common.clone_readable()` names the documented git
  boundary (`.kb/`, `12_RUNTIME/`, `13_LAB/`, most of `14_CANDIDATES/`, caches, key
  material, databases) with the one exception the shelf keeps (`14_CANDIDATES/loop/`),
  `candidate_check.py` refuses a row whose evidence sits behind it, and the law is
  written in `AGENTS.md` so every host projection carries it.
- **The way back as a mechanism** — `scripts/base.py`: `--save` records the last known
  good state only when every health gate is green, `--status` compares base to current
  by fingerprint, and `--recover` restores those bytes, re-proves the fingerprint and
  writes `fell_back: true` to the tracked journal `14_CANDIDATES/loop/recovery.jsonl`.
  A snapshot covers the same inventory as `state_fingerprint` — `15_SYSTEM/backups/` is
  now paperwork, so recording a base cannot invalidate the state it just recorded —
  and recovery reverts the brain, never the shelf. This is the `keep_base` piece of the
  harness2 spine: falling back is an output, not a failure.
- **Amendments** (issue #12) — `hades.py set --id --field --value [--approve]`: an applied
  registry record can now be corrected instead of duplicated. It goes through the same
  plan → `apply --approve` gate as a creation, `id` / `kind` / `created_at` are immutable,
  an amendment that breaks the record's own contract or strands its `entrypoint` is refused
  before a byte moves, a plan whose record moved since it was written is refused as stale,
  and every accepted amendment appends `field, from, to, when, plan` to the record's own
  `amendments` trail. A field neither the record nor its kind's schema has ever heard of is
  refused at the plan — a typo would silently add a second truth.
  `tests/test_phase22_amend_a_record.py` is red without it.
- **Retirement that the index honours** (issue #12) — `supersedes` was declared in
  `15_SYSTEM/config/system.json` as "replaces a record; superseded leaves the active index"
  and `link` accepted it, while `index` listed both records and `doctor` printed `errors: 0`
  (measured: 12 before the link, 12 after). Now `cmd_index` moves a superseded record into a
  `superseded` block that names who retired it, `cmd_doctor` counts active records, prints the
  retirements and errors when a record supersedes itself, and `cmd_status` reports the split.
  Nothing is deleted — `list` still enumerates every record on disk; retirement is a verdict,
  not a shredder. `tests/test_phase23_superseded_leaves_the_index.py` is red without it.
- `02_WIKI/decisions/` has its first inhabitant: *Gates enforce laws or they are comments*
  (`WIK-B7ED0084`), written through `plan` → `apply --approve` and amended through `set` for its
  own provenance — the instruction in `AGENTS.md` to "record decisions in `02_WIKI/decisions`"
  finally carried out, with the lesson of the same pass that built the tools it describes.
  `doctor` counts it (`registry records: 13`, `errors: 0`, `by kind: {"wiki_note": 1}`); the
  generated index it also lands in stays local paperwork, outside the git boundary.
- **The owner's charter is a tracked file** — `00_START_HERE/PROJECT_CHARTER.md`: the
  project brief (15 sections — vision, app-independence, the reference repos, the
  folder/ID law, the eight memory planes, the improvement cycle, agent and skill
  management, the repository workflow, per-repo memory, PR review, conversation
  knowledge, English docs, fourteen laws, the expected outcome, the order of work)
  existed only in a chat, where no future agent could read it. It is now read-before-acting
  item (2) in `AGENTS.md`, with the law that **the charter outranks the task**: a conflict
  is filed on the shelf with its section number, not resolved silently by the last editor.
  Text is verbatim except seventeen ZWNJ insertions the Persian hygiene gate requires
  (`Skillها` → `Skill‌ها`); `qc` measures clean across 36 files and `doctor` at
  `errors: 0 | warnings: 0`.
- **The harness door** (SuperAGI reverse-engineering, phase 22) — the backend agents call
  is the protocol harnesses already speak: `15_SYSTEM/scripts/mcp_server.py`, a Model
  Context Protocol server over stdio, stdlib-only (newline-delimited JSON-RPC 2.0;
  initialize / ping / tools / resources / batches / JSON-RPC errors). Read tools open —
  `vault_search` (BM25 over the brain's prose, rebuilt per call, unicode tokenizer so
  Persian matches), `memory_recall`, `registry_list`, `registry_show`, `doctor_status` —
  and exactly one write tool, `candidate_propose`, which files a **registered** row on the
  quarantine shelf: agents propose, humans decide. Client registration examples live in
  `15_SYSTEM/integrations/` and the first real record `MCP-E1807E50` was created and
  amended through the sanctioned door itself. `doctor` now refuses an `mcp` record whose
  `.py` endpoint does not exist — a server definition whose body is missing is a rumour.
- **The backend package: SuperAGI's logic, stdlib-ported** — `15_SYSTEM/scripts/backend/`
  (`engine`, `tools_kit`, `workflows`, `schedules`, `ltm`, `search`) driven by the thin
  `orchestrator.py` CLI: the AgentExecution state machine and step loop, the BaseTool
  contract with per-actor `tool_allowlist` gating (a write tool needs `--approve` AND the
  list; empty list = zero write tools), declarative workflows validated before they walk,
  pure schedule math, an FTS5 long-term memory, and the BM25 index moved out of
  `mcp_server.py` into a single source. The first `workflow` record (`WFL-6ACDE232`,
  "standup scan") was created through the door, its `body_path` amended to the executable
  `steps.json` beside it, and run for real against the live repo (COMPLETED, 2 steps).
  Tests 235 → 254, battery 116 → 120.
- **Runs promote to evidence; the door sees the runs** — `15_SYSTEM/scripts/runs.py promote`
  exports a finished run's append-only feed into a **registered** shelf row: the feed is
  embedded because the run directory lives behind the git boundary — evidence is exported,
  never cited across it (a run still running, an empty feed, and a second promotion of the
  same run are all refused). The harness door grew two read tools, `runs_list` and
  `runs_show` (eight tools total; `MCP-E1807E50` amended through the plan door again), so
  a harness can see what its actors did without leaving the protocol.
- **Agent runs in the disposable plane** — `15_SYSTEM/scripts/runs.py` borrows SuperAGI's
  `AgentExecution` model at git scale: `12_RUNTIME/agent_runs/<RUN-*/>` with `run.json`
  plus an append-only `steps.jsonl` feed, `start` (refuses actors the registry has never
  heard of), `step` (refuses a finished feed), `finish` (completed|failed, once),
  `list`, `show`. The registry keeps who the actor is; the runtime keeps what it did; both
  die at the git boundary — evidence that matters is promoted, never stranded. The full
  reverse-engineering map (what was adopted, what was refused, why, and the phase-2
  roadmap) is `02_WIKI/reference_maps/superagi-to-hades-map.md`.

### Changed
- **Install layout: the repo's sixteen zones, not the template folders** (phase 35, owner's
  choice). A new home no longer gets `00_Inbox/`, `10_Projects/`, `20_Notes/`,
  `30_Resources/`, `90_Agent_Output/`; `vault-template/` is now only the starter
  (`index.md`, `_templates`). Migration for an existing home: keep your notes where they are
  and install into a fresh folder (the installer refuses a non-empty target), then move the
  note folders into `01_INBOX`/`02_WIKI`/`03_PROJECTS` by hand — the installer moves nothing.
  The zone list is read from `15_SYSTEM/config/system.json`, so a home and this repo stay one
  shape for a later sync to compare.
- **The golden retrieval gate's cases are decidable, not coin flips** (the phase-4 gate,
  found while measuring phase 27 item 3) — four of the five cases sat within 0.14 BM25 units
  of their runner-up, and `plan apply approve` lost `START.md` to `GUIDE_FA_EN.md` by 0.0006
  after ordinary documentation growth shifted the index's global average length. Both documents
  genuinely discuss the pipeline, so the case was asking the ranker to break a tie it had no
  evidence to break. The five cases were re-picked by measured margin (1.23–3.74) and a new
  test holds a 0.5 floor, so a case that becomes ambiguous later fails as a *case* defect
  instead of flipping silently. Corpus, tokenizer and ranker are unchanged.
- **No recency ranker in the prose search** (phase 27 item 3) — the roadmap allowed a BM25
  recency boost only behind a measured win, so it was measured first and refused. 3 of 43
  corpus notes declare `updated:`; the other 40 fall back to mtime, which in a clone is a
  single checkout day (measured: one distinct fallback date). A recency-aware re-rank over
  the shared golden set moved recall@1 and MRR by 0.000 at every weight from 0.05 to 1.0.
  `tests/test_phase27_repo_corpus.py` pins the contract that mattered: a six-year-old exact
  match still outranks a fresh weak one. Revisit only when every note carries a true date and
  labeled cases exist where freshness, not relevance, decides the order.
- `scripts/loop.py` exports the unanswered-search register it read from the local
  SQLite index as a tracked snapshot (`14_CANDIDATES/loop/gaps.jsonl`) and cites the
  snapshot, not the index, in the candidate it raises.
- `scripts/health.py` grew from two gates to six and exposes `GATES` as the measure
  that `doc_report.py` counts rather than a number someone remembers.
- README no longer asserts an app-dependent workflow; the "empty skeleton" claim
  was replaced by what is actually in the folder.

### Fixed
- The version gate refused a folder for a tag it cannot carry. `is_repo_checkout` counts a
  `pyproject.toml` as repo paperwork, and `tests/test_phase20_known_good_base.py` builds its
  fixture clone by copying the tracked files — a manifest with no `.git`. The gate ran there,
  `git` could not name a tag, and the answer was `VERSION 0.1.0 is not tagged and CHANGELOG.md's
  [Unreleased] declares nothing`: found while cutting this release, and it turned the twelve
  base/fingerprint tests red because a copy that keeps no history has no way to pass it except
  to write a changelog entry for a change nobody made. `check()` now judges the tag half only
  where history is readable, and `--check` states the skip in its OK line rather than going quiet
  about it (a silent skip is the failure mode this gate was built for). Both real refusals stand: a
  folder with `.git` whose version is untagged still demands a declaring `## [Unreleased]`, and a
  checkout whose manifest is missing still refuses by name. Four tests in
  `tests/test_phase37_version_gate.py` (`TestACopyThatCarriesNoHistory`) hold the new line, and the
  two tests that assert the old refusal now build a folder that actually keeps a `.git`.
- `zone_check.py` applied `agent_edit_never` only when `action` was exactly "edit", so
  "overwrite", "Edit", "replace", "delete", "update" or " edit" fell through to the approval
  branch and an approved rewrite of a human zone printed OK (issue #39). The action is now a
  closed set: it is normalised (`str(...).strip().lower()`) and anything that is not `create`
  or `edit` is rejected as an unknown action before any zone rule runs, so a synonym is no
  longer a way past the fence. Five tests in `tests/test_phase3.py` hold the line, including
  the issue's own two-proposal example.
- A registry record in a human zone was judged as a broken note (issue #14). `apply` writes a `wiki_note` as
  markdown into `02_WIKI`, and an installed brain scans its own root (`health.py --vault .`), so
  the first decision record this repo filed came back `INVALID: missing field: type … invalid
  status: 'draft'` — the note contract and the registry contract both claiming one file. The
  tempting fix (write a `title`, a `type` and a note `status` next to `name`, `kind` and a registry
  `status`) would have given one field two truths nobody keeps in step, so the gate now picks the
  contract from the file's content using the recognizer the registry already uses, and reads the
  record's required fields and status vocabulary from `15_SYSTEM/config/system.json` and
  `15_SYSTEM/schemas/manifest.schema.json` instead of retyping them. It bites harder, not softer: a
  record with a status its kind disallows, or missing its identity, is refused, and a file that
  claims a registry `kind` with an id the registry cannot enumerate is named as an orphan.
  `tests/test_phase24_a_record_is_not_a_note.py` (13 tests) is red without it.
- Amending or linking a markdown record deleted its prose — found by dogfooding `set` the moment
  it shipped. The body was *rendered from* `notes`/`claim`, but the reader parsed only the
  frontmatter, so the next write-back re-rendered the file from fields that no longer held the
  paragraph. Those fields now round-trip, and
  `test_an_amendment_does_not_lose_the_prose_of_a_markdown_record` is red without the fix.
- A markdown record was created invisible (issue #13): `news` and `wiki_note` land as
  `<ID>-<slug>.md`, while `iter_records` admitted a markdown record only when its stem was
  exactly `note`. `apply` wrote the record, then `show`, `list`, `index` and `doctor` answered
  that nothing existed — and `doctor` printed `errors: 0`, which is a silent gate, not a clean
  house. Enumeration is now by content (a registry-shaped `id` **and** a declared `kind`), a
  body (`OVERVIEW.md`, `SKILL.md`) stays a body, and `link` round-trips relations through the
  markdown writer instead of dropping them on the floor.
- CI was red on all four matrices while every local gate printed OK. The shelf row
  `cand-2026-10-27-c3-01` blamed a gap count held in `.kb/kb.sqlite`, a file that is
  gitignored by design: it existed on the machine that wrote the claim and nowhere
  else, so the evidence gate correctly refused it in a fresh clone. The row now cites
  the exported snapshot, the loop cannot write such a row again, and a test rebuilds
  the clone from `git ls-files` and runs the gate there.
- The zone/git-boundary law: `12_RUNTIME` and `13_LAB` are declared but gitignored,
  and the toolchain now says so at the boundary instead of reporting a missing zone
  as damage.
- A Persian-text regression class the hygiene gate now catches mechanically: an
  Arabic lookalike inside generated Persian prose.

## [0.0.3] - 2026-10-27

### Added
- Bilingual README (EN/FA) and bilingual engine addendum; version surfaced in
  `VERSION` + `pyproject.toml`, consistency test-gated.
- Engine v0.0.3 shipped alongside the HADES OS v3 plane skeleton (merged, not
  replaced): fenced zones 00_Inbox…90_Agent_Output, `vault-template/AGENTS.md`
  contract, rules (`rules/schema.json`, `rules/zones.json`).
- Integrity toolchain: `link_check.py`, `frontmatter_check.py`, `vault_stats.py`.
- Zone fence + write gate: `zone_check.py`, `write_gate.py`, quarantine→promote
  (`promote.py`) with audit trail.
- Local knowledge base: `kb.py` (SQLite FTS5, LIKE fallback), kb-search skill,
  gap register (unanswered searches = self-driving backlog), golden-set eval gate.
- Composite health check, weekly-ritual skills, installer (`install.py`).
- GitHub Actions CI: ubuntu+windows × py3.9+3.12, health + tests + write-gate smoke.

### Fixed
- CI write-gate smoke test made cross-shell safe (pwsh has no `test` builtin).
