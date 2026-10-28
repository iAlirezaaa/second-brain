# HADES OS v0.01

For explicitly importing and searching local documents or conversation exports, see
[local source ingestion](15_SYSTEM/integrations/local-sources.md). Imported content is
private local data, and the MCP source search exposes matches to connected clients.

[![CI](https://github.com/iAlirezaaa/second-brain/actions/workflows/ci.yml/badge.svg)](https://github.com/iAlirezaaa/second-brain/actions/workflows/ci.yml)
[![loop](https://github.com/iAlirezaaa/second-brain/actions/workflows/loop.yml/badge.svg)](https://github.com/iAlirezaaa/second-brain/actions/workflows/loop.yml)
[![version](https://img.shields.io/badge/engine-v0.0.3-blue)](https://github.com/iAlirezaaa/second-brain/releases)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**📋 نقشهٔ عمومی راه / Public roadmap (با چیپ وضعیت و تیک پیوسته): [ROADMAP.md](ROADMAP.md)**

## What this is

یک محفظهٔ محلی برای دانش، پروژه‌ها و ایجنت‌ها — که هارنس‌ها از طریق پروتکلی که همین حالا
حرف می‌زنند (MCP روی stdio) به آن وصل می‌شوند و هر اجرای ایجنت هم ثبت می‌شود.
صفحهٔ انسان ۰۰ تا ۱۰، صفحهٔ ماشین ۱۱ به بعد.
قانون‌ها را اسکریپت اجرا می‌کند، نه تذکر دوستانه: هر تخلف از قرارداد، یک گیتِ قرمز است.

EN — A local, plain-markdown second brain for one human curator and many AI agents: knowledge,
projects and agents live in numbered zones, and the rules are enforced by scripts instead of by
good intentions. Harnesses reach it through the protocol they already speak — an MCP server over
stdio, no server farm — and every agent run is recorded in a disposable ledger whose evidence can
be promoted to the shelf. **No app is required.** Python 3.9+ standard library and markdown files
are the whole system; Obsidian, VS Code, Cursor, Claude Code, Codex, Zed or `notepad` are
optional lenses on the same folder.

Four properties this repo is built to keep:

1. **It gets smarter.** Every lesson the repo learns is appended to
   `15_SYSTEM/memory/lessons.jsonl` with a verdict, evidence and a confidence;
   `python scripts/memory.py --recall "<question>"` answers it, and `NO_ENTRY` is a legal answer.
   The root `MEMORY.md` is generated from that ledger — it is never typed by hand.
2. **It learns from its mistakes.** A claim about behaviour is believed only after a real
   execution probed it (`scripts/probe.py`); candidates wait on a quarantine shelf
   (`14_CANDIDATES/`) and reach the human plane only through a gated promotion, with the
   ledger's count identity checked against the folder. And when a change measures worse there
   is a way back that is a mechanism, not an intention: `python scripts/base.py --save` records
   the last state that passed every gate, `--recover` returns to it, proves the fingerprint, and
   writes `fell_back: true` to `14_CANDIDATES/loop/recovery.jsonl`.
3. **An agent can start from the URL alone.** Hand this repository's address to any agent:
   it reads `AGENTS.md` — or the generated door for its host — and follows
   `skills/first-session/SKILL.md`: orient, prove the house is healthy, take one bounded task,
   leave a handoff.
4. **The brain is callable, and its agents are accountable.** The backend agents call is
   `15_SYSTEM/scripts/mcp_server.py` — a Model Context Protocol server over stdio, stdlib-only,
   no port, no keys; OpenCode, Claude Desktop and friends register it natively
   (`15_SYSTEM/integrations/`). Read tools are open (`vault_search`, `memory_recall`, the
   registry, `doctor_status`, the run ledger); `candidate_propose` files on the quarantine
   shelf, and `lesson_propose` files private source-backed proposals — humans decide. Agent runs
   are a disposable ledger (`15_SYSTEM/scripts/runs.py` → `12_RUNTIME/agent_runs/`) that
   refuses actors the registry has never heard of, and `runs.py promote` exports a finished
   run's feed into a registered shelf row — the run dir never becomes evidence, it lives behind
   the git boundary. The execution logic behind runs is a stdlib package
   (`15_SYSTEM/scripts/backend/`: engine, toolkits with real allowlists, declarative
   workflows, schedules, FTS5 memory) driven by the thin `orchestrator.py` CLI —
   deterministic steps only; an LLM step stays a human decision. The full reverse-engineering
   map behind these choices: `02_WIKI/reference_maps/superagi-to-hades-map.md`.

```text
python scripts/health.py                   # every gate in one command, incl. the numbers below
python -m unittest discover -s tests       # the suite — its size is in the measured table below
python 15_SYSTEM/scripts/hades.py doctor   # the HADES plane: zones, manifests, relations
```

**اول اینها را به همین ترتیب بخوان:**

1. [راهنمای جامع](00_START_HERE/GUIDE_FA_EN.md) — همه‌چیز در یک سند: ناحیه‌ها، شناسه، انواع، دستورها، گیت‌ها، عیب‌یابی (فارسی و انگلیسی)
2. [سند طراحی](00_START_HERE/DESIGN_v3.md) — چرا این شکل، ناحیه‌ها، و آنچه عمداً ساخته نشده
3. [راهنمای شروع](00_START_HERE/START.md) — دستورات روزمره
4. [نقشه سیستم](00_START_HERE/SYSTEM_MAP.md) — ناحیه‌ها، شناسه‌ها، رابطه‌ها
5. [چرخه حیات و ارتقا](00_START_HERE/LIFECYCLE.md) — از ورودی تا تولیدی
6. [دسترسی و رازها](00_START_HERE/ACCESS.md) — مرز دو صفحه، Git، رمز

**پژوهش مرتبط:** [قالب دومغزی دو‌صفحه‌ای](00_START_HERE/SECOND_BRAIN_TEMPLATE.md) — مقایسه قالب‌های موجود، الگوی پیشنهادی و نگاشت آن به همین ساختار.

```powershell
py -3.10 15_SYSTEM/scripts/hades.py doctor
py -3.10 15_SYSTEM/scripts/hades.py index
py -3.10 15_SYSTEM/scripts/hades.py status
py -3.10 15_SYSTEM/scripts/wiki.py build
```

`py -3.10` را جدی بگیر: روی این سیستم `python` پیش‌فرض نسخه ۳.۹ است و با stdout ویندوز، متن فارسی را می‌شکند. `start.bat` همین را برایت انجام می‌دهد.

## وضعیت فعلی / Current state

این بسته **اسکلت است، نه نمونه‌کار**: ناحیه‌ها، قراردادها، الگوها و اسکریپت‌های آزمودنی. هیچ پروژهٔ شخصی، مدل، خبر یا دادهٔ نمونه‌ای داخلش نیست و هیچ‌چیز با پرکنندهٔ ساختگی انباشته نشده. آنچه پر است، خودِ قانون است: رجیستری کنترل‌پلین (اسکیل‌ها و ایجنت‌هایی که این بسته واقعاً دارد) و حافظهٔ ریپو. موجودی را با `hades.py status` و جدول پایین بخوان؛ عددی که اندازه‌گیری نشده باشد، عددی است که کسی اثباتش نکرده.

EN — This package is a skeleton, not a portfolio: no personal projects, models, news or sample data, and nothing padded with filler. What *is* populated is the law itself — the control-plane registry (the skills and agents this pack really ships) and the repo's own memory. Read the inventory from `hades.py status` and the table below.

هر عدد زیر همین الان از همین پوشه خوانده شده و `python scripts/doc_report.py --write` آن را
می‌نویسد. اگر بعد از یک تغییر دستی قدیمی بماند، گیتِ «اعدادِ اسناد» در `python scripts/health.py`
قرمز می‌شود — یک عددِ تایپی در سند، ادعاست، نه اندازه‌گیری.

EN — Every number below is read from this folder by `python scripts/doc_report.py --write`. A
stale number fails the numbers gate in `python scripts/health.py` rather than becoming lore.

<!-- BEGIN measured — written by `python scripts/doc_report.py --write` -->
| measure | now |
| --- | --- |
| tests collected (`python -m unittest discover -s tests`) | 343 |
| health gates (`python scripts/health.py`) | 7 |
| registry records (`11_CONTROL/**/*.json`) | 13 |
| skills in the pack (`skills/*/SKILL.md`) | 10 |
| agent-host doors (`python scripts/sync_hosts.py --list`) | 5 |
| active lessons (`15_SYSTEM/memory/lessons.jsonl`) | 26 |
| candidate rows on the shelf (`14_CANDIDATES/loop`) | 6 |
| kinds in the contract (`15_SYSTEM/config/system.json`) | 33 |
| relation types in the contract | 13 |
| zones a fresh clone reproduces / declared (`12_RUNTIME`, `13_LAB` are gitignored) | 12 / 16 |
| python floor | 3.9 (standard library only) |
<!-- END measured -->

اسکریپت‌ها: `hades.py` (رجیستری و گیت‌ها)، `init_structure.py` (ساخت ناحیه‌ها،
idempotent)، `wiki.py` (سایت ناحیه انسان)، `test_hades.py` (تست‌های مثبت و منفی روی
یک والت موقت). الگوها در `15_SYSTEM/templates`‌اند و فقط قالب‌اند؛ داده نمونه نیستند.

## پل هارنس / The harness bridge

بک‌اندی که ایجنت‌ها صدا می‌زنند، پروتکلی است که هارنس‌ها همین حالا حرف می‌زنند:
`15_SYSTEM/scripts/mcp_server.py` — سرور MCP روی stdio، فقط کتابخانهٔ استاندارد، بدون
پورت و کلید و دیمن. ابزارهای خواندن بازند (`vault_search`، `memory_recall`،
`registry_list`، `registry_show`، `doctor_status`). ابزار `candidate_propose` روی قفسهٔ قرنطینه
و `lesson_propose` در حافظهٔ خصوصی پیشنهاد ثبت می‌کند — ایجنت پیشنهاد می‌دهد، انسان تصمیم
می‌گیرد. نمونهٔ اتصال برای OpenCode و Claude Desktop در `15_SYSTEM/integrations/` است.

EN — The backend agents call is the protocol harnesses already speak:
`15_SYSTEM/scripts/mcp_server.py`, a Model Context Protocol server over stdio,
stdlib-only, no port, no keys, no daemon. `candidate_propose` files on the quarantine shelf;
`lesson_propose` files a private source-backed proposal — agents propose,
humans decide. Client examples: `15_SYSTEM/integrations/`. Agent runs are a separate
disposable ledger (`15_SYSTEM/scripts/runs.py` → `12_RUNTIME/agent_runs/`): the registry
keeps who the actor is, the run keeps what it did, and both die at the git boundary —
evidence is promoted, never stranded.

## آنچه اینجا نیست

Orchestrator زنده، صف کارِ اجراکننده، RBAC یا ACL فایل‌سیستم، سندباکس واقعی، جست‌وجوی سمانتیک و Vector DB، همگام‌سازی خودکار GitHub، سرویس بکاپ زمان‌دار و داشبورد آنلاین. برای هر کدام اسلات رزرو شده، ولی سرویس ساخته نشده.

---

Owner: Hades 3rd ([@iAlirezaaa](https://github.com/iAlirezaaa))

---

## Engine addendum — second-brain engine v0.0.3 · پیوست موتور

> **EN —** Alongside the HADES plane structure, this repo now ships the **second-brain engine v0.0.3**: an agent harness toolkit that enforces the same philosophy as scripts. `vault-template/` holds a fenced-zone starter vault (00_Inbox…90_Agent_Output) the agent reads via `vault-template/AGENTS.md`; `rules/` and the tests are machine-readable; every capability is test-gated. Run the suite with `python -m unittest discover -s tests` and the health check with `python scripts/health.py`. Install into a fresh home with `python scripts/install.py`. The engine inherited the quarantine→promote, gap-register and write-gate patterns — direct implementations of the promotion and safety gates this design already specified.
>
> **FA —** در کنار ساختار صفحاتِ HADES، این ریپو از این به بعد **موتورِ سکند برین نسخهٔ 0.0.3** را هم دارد: کیت ابزارِ هارنسِ ایجنت که همان فلسفه را با اسکریپت اجرا می‌کند، نه با توصیه. `vault-template/` والتی استارتر با زون‌های حصارکشی‌شده است که ایجنت از `vault-template/AGENTS.md` می‌خواند؛ `rules/` و تست‌ها قابل خواندن ماشین هستند و هر قابلیت با تست محافظت می‌شود. سوت را با `python -m unittest discover -s tests` و سلامت ولت را با `python scripts/health.py` صدا بزنید؛ نصب در خانهٔ نو: `python scripts/install.py`. موتور الگوهای قرنطینه→ارتقا، ثبت‌شکاف جست‌وجو و گیتِ نوشتار را هم دقیق همان جاهایی پیاده کرده که این طراحی خواسته بود.
>
> **Maps / نگاشت:** `00_Inbox` ≈ `01_INBOX`، `20_Notes`+`30_Resources` ≈ `02_WIKI`+`15_SYSTEM/templates`، `90_Agent_Output` ≈ `13_LAB`+`14_CANDIDATES`، `promote` ≈ ارتقای `13/14` به صفحهٔ انسان. Two vocabularies, one philosophy: **nothing reaches the human plane un-promoted, nothing breaks a link un-checked.** · دو گویش، یک فلسفه: **هیچ‌چیز بدون ارتقا به صفحهٔ انسان نمی‌رسد، هیچ‌چیز بدون چک لینک نمی‌شکند.**
