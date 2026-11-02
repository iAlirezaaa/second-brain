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
| #20 | Charter section 5/11: the eight memory planes have no mapping, no conversation-memory reader, and kb.py skips this repo's own prose | نیمه | باز | `02_WIKI/reference_maps/eight-memory-planes.md`، `scripts/plane_check.py` |
| #21 | Charter section 7: the manager agent named in the charter is not a registered definition | بسته | بسته | `8c757b4`، `11_CONTROL/agents/AGT-7DE1AB28-structure-manager`، `skills/conversation-memory/SKILL.md` |
| #22 | Charter section 3: only SuperAGI has a standing reference map; harness2 and claude-obsidian live in prose history | بسته | بسته | `6e7121a`، `02_WIKI/reference_maps/harness2-to-hades-map.md`، `02_WIKI/reference_maps/claude-obsidian-to-hades-map.md` |
| #24 | Charter section 5: no memory plane can detect a contradiction | بسته | بسته | `dde3cad`، `scripts/memory.py`، `rules/memory.schema.json` |
| #25 | Charter section 5: lessons are not typed by plane, so error memory is unlabelled | بسته | بسته | `dde3cad`، `scripts/memory.py`، `scripts/plane_check.py` |
| #27 | Fresh install fails plane_check: the dev system.json is copied into a template-shaped home | بسته | بسته | — |
| #39 | zone_check: an action other than "edit" skips the agent_edit_never rule | بسته | بسته | `f73a378`، `scripts/zone_check.py`، `tests/test_phase3.py` |

## وضعیت‌ها

**0 باز · 1 نیمه · 0 اصلاح‌شده · 21 بسته** — جمعاً 22 ایشیو.

- **#20** نگاشت هشت پلین و گیتش (۹a561d5) و فیلد plane برای همهٔ درس‌ها (dde3cad) و مسیرِ ثبت‌شدهٔ حافظهٔ گفتگو با ایجنتِ مدیر و اسکیلش (8c757b4) ساخته شد. آنچه مانده خواندنِ *زندهٔ* گفتگوست: امروز تنها راه، واردکردن صریح فایل به دفتر درس است و هیچ دری در ۱۲_RUNTIME این کار را خودکار نمی‌کند.
