# ایشیوها — دفترِ وضعیت

این صفحه از `15_SYSTEM/config/issues.json` ساخته می‌شود؛ دستی ویرایش نکنید. `python scripts/issues.py`
می‌نویسد و `python scripts/issues.py --check` (داخل `python scripts/health.py`)
می‌سنجد که هر ردیفِ «اصلاح‌شده» یک کامیت و یک مسیرِ شاهد دارد که در یک کلون هم هست،
و هر ردیفِ «باز» جمله‌ای می‌گوید که چه چیزی هنوز کم است.

| ایشیو | موضوع | وضعیت در کد | گیت‌هاب | شاهد |
| --- | --- | --- | --- | --- |
| #3 | Promotion is not gated on measured evidence | بسته | بسته | — |
| #4 | Test-count badge is hand-typed and already wrong (39 vs 58) | بسته | بسته | — |
| #5 | write_gate.py --file crashes instead of blocking | بسته | بسته | — |
| #6 | rules/zones.json points at a zone that does not exist (`02_Index`) | بسته | بسته | — |
| #7 | No durable repository memory — HANDOFF is transient by design | بسته | بسته | — |
| #8 | Agent contract is single-host and the installer still points at Obsidian | بسته | بسته | — |
| #9 | Loop report candidates are untyped free text with no count identity | بسته | بسته | — |
| #10 | README/START/HANDOFF quote numbers a fresh clone cannot reproduce | بسته | بسته | — |
| #11 | Candidate evidence can cite gitignored local state, so CI is the first reader to fail | بسته | بسته | — |
| #12 | Registry is create-only, and the declared supersedes rule is not enforced | بسته | بسته | — |
| #13 | A markdown-layout record is created invisible: news and wiki_note escape every gate | بسته | بسته | — |
| #14 | Two contracts claim one file: the note gate judges a registry record as a broken note | بسته | بسته | — |
| #15 | state_fingerprint counts gitignored, regenerated `15_SYSTEM/generated/` -- an `index` run ages every probe and no clone can reproduce a base | بسته | بسته | `c75bf27`، `scripts/common.py`، `tests/test_phase36_doors_tell_the_truth.py` |
| #16 | Refusing human-plane `09_OPERATIONS` says "denied machine plane", and AGENTS.md/ACCESS.md/SYSTEM_MAP.md deny a subfolder the config never named | بسته | بسته | `c75bf27`، `15_SYSTEM/scripts/hades.py`، `AGENTS.md` |
| #17 | `memory.py --add --supersedes <unknown id>` writes the row; the ledger only fails at --check, after the render | بسته | بسته | `c75bf27`، `scripts/memory.py`، `tests/test_phase36_doors_tell_the_truth.py` |
| #20 | Charter section 5/11: the eight memory planes have no mapping, no conversation-memory reader, and kb.py skips this repo's own prose | بسته | بسته | `8c757b4`، `02_WIKI/reference_maps/eight-memory-planes.md`، `scripts/plane_check.py` |
| #21 | Charter section 7: the manager agent named in the charter is not a registered definition | بسته | بسته | `8c757b4`، `11_CONTROL/agents/AGT-7DE1AB28-structure-manager`، `skills/conversation-memory/SKILL.md` |
| #22 | Charter section 3: only SuperAGI has a standing reference map; harness2 and claude-obsidian live in prose history | بسته | بسته | `6e7121a`، `02_WIKI/reference_maps/harness2-to-hades-map.md`، `02_WIKI/reference_maps/claude-obsidian-to-hades-map.md` |
| #24 | Charter section 5: no memory plane can detect a contradiction | بسته | بسته | `dde3cad`، `scripts/memory.py`، `rules/memory.schema.json` |
| #25 | Charter section 5: lessons are not typed by plane, so error memory is unlabelled | بسته | بسته | `dde3cad`، `scripts/memory.py`، `scripts/plane_check.py` |
| #27 | Fresh install fails plane_check: the dev system.json is copied into a template-shaped home | بسته | بسته | — |
| #39 | zone_check: an action other than "edit" skips the agent_edit_never rule | بسته | بسته | `f73a378`، `scripts/zone_check.py`، `tests/test_phase3.py` |
| #41 | Nightly loop report never lands: the workflow pushes to protected main and is rejected | باز | باز | — |
| #42 | continue-on-error turns the loop's own refusals into a green job | باز | باز | — |
| #43 | loop.py --due: rc 1 (refused) takes the same branch as rc 3 (not due) | باز | باز | — |
| #44 | loop.yml cron (30 3 * * *) disagrees with the schedule record (daily_at 02:00) | باز | باز | — |
| #45 | The nightly runs --no-tests, so the ratchet never sees the test suite | باز | باز | — |
| #46 | Documented interpreter py -3.10 is not installed, and the docs justify it with a false claim | باز | باز | — |
| #47 | The documented wiki build leaves 23 generated pages untracked in the human plane | باز | باز | — |
| #48 | LIFECYCLE documents 14_CANDIDATES/outputs/ while .gitignore makes it uncommittable | باز | باز | — |
| #49 | No gate reads the repo's own notes: health.py judges only vault-template | باز | باز | — |
| #50 | HANDOFF says 421 tests beside its own 843, and its staleness gate is never run | باز | باز | — |
| #51 | MCP drift: server serves 13 tools, the registry declares 10, HANDOFF names 6 | باز | باز | — |
| #52 | CONTRIBUTING's gate table lists 10 of the 15 gates health.py runs | باز | باز | — |
| #53 | No measured document reports the HADES battery's 120 checks, though ROADMAP claims one does | باز | باز | — |
| #54 | 14_CANDIDATES/README.md cites ROADMAP Phase 9.5, which does not exist | باز | باز | — |
| #55 | roadmap_check drops space-bearing citations and launders fake paths as DECLARED | باز | باز | — |
| #56 | loop.py hygiene() counts its own source as the repo's TODO debt (9 of 10) | باز | باز | — |
| #57 | datetime.utcnow() deprecated at 10 call sites; handoff.py subtracts it | باز | باز | — |
| #58 | The suite leaks its mkdtemp fixtures: 23 sites in 13 files, never removed | باز | باز | — |
| #59 | link_check --confidence prints len(edges) twice and cannot exit 1 | باز | باز | — |
| #60 | Five gates print OK over a zero denominator; link_check accepts a missing vault | باز | باز | — |
| #61 | doc_report --write turns a failed measurement into a row, then certifies it fresh | باز | باز | — |
| #62 | parse_frontmatter drops lines it cannot parse, cutting shipped reviewer laws | باز | باز | — |
| #63 | issues.py --check reports health when a repo checkout has no ledger | باز | باز | — |
| #64 | CI red on all four jobs since 744cbb0: two harness battery checks fail | باز | باز | — |

## وضعیت‌ها

**24 باز · 0 نیمه · 0 اصلاح‌شده · 22 بسته** — جمعاً 46 ایشیو.

- **#41** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#42** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#43** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#44** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#45** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#46** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #46; no confirmed complete fix has been merged.
- **#47** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #47; no confirmed complete fix has been merged.
- **#48** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #48; no confirmed complete fix has been merged.
- **#49** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #49; no confirmed complete fix has been merged.
- **#50** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #50; no confirmed complete fix has been merged.
- **#51** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #51; no confirmed complete fix has been merged.
- **#52** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #52; no confirmed complete fix has been merged.
- **#53** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #53; no confirmed complete fix has been merged.
- **#54** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #54; no confirmed complete fix has been merged.
- **#55** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #55; no confirmed complete fix has been merged.
- **#56** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #56; no confirmed complete fix has been merged.
- **#57** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #57; no confirmed complete fix has been merged.
- **#58** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #58; no confirmed complete fix has been merged.
- **#59** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#60** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#61** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#62** Open upstream. The detailed failure, reproduction steps and acceptance criteria are recorded in GitHub issue #62; no confirmed complete fix has been merged.
- **#63** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
- **#64** Open upstream. Candidate fix and regression coverage are under review in PR #69 or on current main; verify the acceptance criteria and full CI before closure.
