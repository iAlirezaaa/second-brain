# Second Brain OS v0.2.0

**What the name means.** *Second Brain OS* is what this is for anyone who needs to know in three
words: a second brain (external memory you can trust) that is a complete system rather than a
folder of notes — zones, gates, a registry, a ledger and its own improvement loop. **HADES** is the
engine's codename, and it stays in the code where it already lives: `15_SYSTEM/scripts/hades.py`
is the registry door, `HADES OS v3` is the plane skeleton the engine lays. The badge below reads
`engine-v…` for that reason.

**دومغزیِ شخصی و محلی (فارسی):** یک مغزِ مارک‌داون برای یک انسان و چند ایجنت — دانش، پروژه‌ها
و اجراها در ناحیه‌های شماره‌دار می‌مانند و قانون را اسکریپت اجرا می‌کند، نه تذکر. هارنس‌ها از
همان پروتکلی وصل می‌شوند که همین حالا حرف می‌زنند (MCP روی stdio، بدون پورت و کلید)، هر
منبع با منشأ و زمانش بازیابی می‌شود، و هر تغییر پایدار سیستم فقط با تأیید انسان انجام می‌گیرد.

**برنامهٔ مرحله‌ای و ممیزی، به فارسی:** [PLAN_FA.md](00_START_HERE/PLAN_FA.md) — نگاشت
پنج فاز به کد امروز، دستورِ اثبات هر بند، و فهرست شکاف‌های باز. نسخهٔ قابل دانلود:
[second-brain-plan-fa.pdf](downloads/second-brain-plan-fa.pdf).

**توضیحِ کوتاهِ همین ریپو (آمادهٔ کپی در About گیت‌هاب):**
[REPO_ABOUT_FA.md](00_START_HERE/REPO_ABOUT_FA.md) — متن فارسی، موضوع‌ها، و آنچه نباید در
توضیح ادعا شود.

**وضعیت ایشیوها، در خود مخزن:** [ISSUES.md](00_START_HERE/ISSUES.md) — هر ایشیو با
وضعیتِ واقعی‌اش (باز / نیمه / اصلاح‌شده / بسته)، کامیتِ اصلاح و مسیرِ شاهد؛ از
`15_SYSTEM/config/issues.json` ساخته می‌شود و گیتِ `scripts/issues.py --check` نمی‌گذارد
صفحه از دفتر جدا بماند یا ردیفِ «اصلاح‌شده» بی‌شاهد باشد.

For explicitly importing and searching local documents or conversation exports, see
[local source ingestion](15_SYSTEM/integrations/local-sources.md). Imported content is
private local data, and the MCP source search exposes matches to connected clients.

[![CI](https://github.com/iAlirezaaa/second-brain-os/actions/workflows/ci.yml/badge.svg)](https://github.com/iAlirezaaa/second-brain-os/actions/workflows/ci.yml)
[![loop](https://github.com/iAlirezaaa/second-brain-os/actions/workflows/loop.yml/badge.svg)](https://github.com/iAlirezaaa/second-brain-os/actions/workflows/loop.yml)
[![version](https://img.shields.io/badge/engine-v0.2.0-blue)](https://github.com/iAlirezaaa/second-brain-os/releases)
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
   (`15_SYSTEM/integrations/`). Read tools answer inside the boundary
   `15_SYSTEM/scripts/backend/access.py` draws (`vault_search`, `memory_recall`, the registry,
   `doctor_status`, `source_search`): a read the law denies is refused with the rule named and
   nothing from inside that plane on the wire, and `source_search` answers with a citation plus
   a bounded excerpt instead of the whole stored body; `source_import` records one
   file the client names from inside the brain as a private source with its provenance,
   `candidate_propose` files on the quarantine shelf, and `lesson_propose` files private
   source-backed proposals — humans decide. Agent runs
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

**دانلود / Downloads**

| فایل | چیست |
| --- | --- |
| [second-brain-plan-fa.pdf](downloads/second-brain-plan-fa.pdf) | سند فارسی برنامهٔ مرحله‌ای و ممیزی، برای خواندن و اشتراک‌گذاری بیرون از گیت‌هاب |
| [PLAN_FA.md](00_START_HERE/PLAN_FA.md) | همان سند به شکل مارک‌داون، با پیوند به تست و دستور هر بند |

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
| tests collected (`python -m unittest discover -s tests`) | 866 |
| health gates (`python scripts/health.py`) | 15 |
| registry records (`11_CONTROL/**/*.json`) | 20 |
| skills in the pack (`skills/*/SKILL.md`) | 14 |
| agent-host doors (`python scripts/sync_hosts.py --list`) | 5 |
| active lessons (`15_SYSTEM/memory/lessons.jsonl`) | 27 |
| candidate rows on the shelf (`14_CANDIDATES/loop`) | 6 |
| kinds in the contract (`15_SYSTEM/config/system.json`) | 34 |
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
`registry_list`، `registry_show`، `doctor_status`، `source_search`). ابزار `source_import`
یک فایلِ صریحاً انتخاب‌شده را با منشأ و زمان به‌عنوان منبع خصوصی ثبت می‌کند (مسیر بیرون از
مغز یا در نواحی ممنوع رد می‌شود)، `candidate_propose` روی قفسهٔ قرنطینه و `lesson_propose`
در حافظهٔ خصوصی پیشنهاد ثبت می‌کند — ایجنت پیشنهاد می‌دهد، انسان تصمیم می‌گیرد. نمونهٔ اتصال برای OpenCode و Claude Desktop در `15_SYSTEM/integrations/` است.

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

## Engine addendum — second-brain engine v0.2.0 · پیوست موتور

> **EN —** Alongside the HADES plane structure, this repo now ships the **second-brain engine v0.2.0**: an agent harness toolkit that enforces the same philosophy as scripts. `vault-template/` holds only the starter pieces (`index.md`, `_templates`); `python scripts/install.py` lays the same sixteen zones the repo uses, read from `15_SYSTEM/config/system.json`, together with the engine (`scripts/`, `15_SYSTEM/scripts/`), the registry schemas, the lesson ledger and all five agent doors. An installed home is not a snapshot: `python scripts/install.py --upgrade ~/brain` moves it onto this engine one judged path at a time — a file the engine changed is rewritten, a file the person edited is kept and named, a file the home's own record cannot vouch for stays exactly where it is and makes the run exit 1 — and nothing is ever deleted; `--dry-run` proves it writes nothing by comparing the home's tree fingerprint on entry and exit. `rules/` and the tests are machine-readable; every capability is test-gated. Run the suite with `python -m unittest discover -s tests` and the health check with `python scripts/health.py`. The engine inherited the quarantine→promote, gap-register and write-gate patterns — direct implementations of the promotion and safety gates this design already specified.
>
> **FA —** در کنار ساختار صفحاتِ HADES، این ریپو از این به بعد **موتورِ سکند برین نسخهٔ 0.2.0** را هم دارد: کیت ابزارِ هارنسِ ایجنت که همان فلسفه را با اسکریپت اجرا می‌کند، نه با توصیه. `vault-template/` فقط قطعات آغازین (`index.md` و `_templates`) را دارد؛ `python scripts/install.py` همان شانزده زون مخزن را از `15_SYSTEM/config/system.json` می‌سازد و موتور (`scripts/` و `15_SYSTEM/scripts/`)، شِماهای رجیستری، دفترِ درس‌ها و هر پنج درِ ایجنت را کنارشان می‌گذارد. خانهٔ نصب‌شده یک عکس فوری نیست: `python scripts/install.py --upgrade ~/brain` خانه را مسیر‌به‌مسیر و دانه‌به‌دانه به این موتور می‌آورد — فایلی که موتور عوضش کرده بازنویسی می‌شود، فایلی که آدم اینجا ویرایش کرده دست‌نخورده می‌ماند و نامش گفته می‌شود، و فایلی که رکوردِ خودِ خانه گواهی‌اش را ندارد سرِ جایش می‌ماند و اجرای آپگرید با کد خطا (۱) تمام می‌شود — و هیچ‌چیز حذف نمی‌شود؛ `--dry-run` ثابت می‌کند چیزی نمی‌نویسد، چون ردختِ درختِ خانه را در ورود و خروج مقایسه می‌کند. `rules/` و تست‌ها قابل خواندن ماشین هستند و هر قابلیت با تست محافظت می‌شود. سوت را با `python -m unittest discover -s tests` و سلامت ولت را با `python scripts/health.py` صدا بزنید.
>
> **Maps / نگاشت:** `00_Inbox` ≈ `01_INBOX`، `20_Notes`+`30_Resources` ≈ `02_WIKI`+`15_SYSTEM/templates`، `90_Agent_Output` ≈ `13_LAB`+`14_CANDIDATES`، `promote` ≈ ارتقای `13/14` به صفحهٔ انسان. Two vocabularies, one philosophy: **nothing reaches the human plane un-promoted, nothing breaks a link un-checked.** · دو گویش، یک فلسفه: **هیچ‌چیز بدون ارتقا به صفحهٔ انسان نمی‌رسد، هیچ‌چیز بدون چک لینک نمی‌شکند.**
