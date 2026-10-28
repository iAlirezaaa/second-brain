# راهنمای شروع

همه دستورات با `py -3.10` اجرا می‌شوند و از ریشه والت (`E:\Agent\HADES_OS_v3`).
دلیل این انتخاب: `python` پیش‌فرض این سیستم ۳.۹ است و روی کنسول cp1252 ویندوز،
خروجی فارسی را می‌شکند. `start.bat` هم نسخه ۳.۱۰ را صدا می‌زند و خودش فقط ASCII
است.

## ۰) اندازه‌های امروز (خودکار، نه تایپی)

هر عدد در جدول زیر همین الان از همین پوشه خوانده شده. `python scripts/doc_report.py --write`
نویسندهٔ آن است و `--check` همان گیتِ «اعدادِ اسناد» در سلامت است: اگر بعد از یک تغییر، عددی
قدیمی بماند، سبز نمی‌شود. هیچ‌چیز در این فایل با عددِ حافظه‌ای پر نمی‌شود.

<!-- BEGIN measured — written by `python scripts/doc_report.py --write` -->
| measure | now |
| --- | --- |
| tests collected (`python -m unittest discover -s tests`) | 421 |
| health gates (`python scripts/health.py`) | 8 |
| registry records (`11_CONTROL/**/*.json`) | 15 |
| skills in the pack (`skills/*/SKILL.md`) | 10 |
| agent-host doors (`python scripts/sync_hosts.py --list`) | 5 |
| active lessons (`15_SYSTEM/memory/lessons.jsonl`) | 26 |
| candidate rows on the shelf (`14_CANDIDATES/loop`) | 6 |
| kinds in the contract (`15_SYSTEM/config/system.json`) | 34 |
| relation types in the contract | 13 |
| zones a fresh clone reproduces / declared (`12_RUNTIME`, `13_LAB` are gitignored) | 12 / 16 |
| python floor | 3.9 (standard library only) |
<!-- END measured -->

## ۱) اول بررسی کن که سالم است

```powershell
py -3.10 15_SYSTEM\scripts\hades.py doctor
py -3.10 15_SYSTEM\scripts\hades.py status
py -3.10 15_SYSTEM\scripts\hades.py index
```

`doctor` ناحیه‌ها، مانیفست‌ها، رابطه‌ها، `.gitignore`، رازها و بهداشت فارسی را
می‌خواند. `errors: 0` تنها وضعیت قابل‌قبول است؛ اگر خطایی دیدی، همان خط می‌گوید
کجا را درست کن. فهرست چیزی که این بسته **مدعی‌اش نیست** هم چاپ می‌شود
(`not enforced by this package`) — آن را جدی بگیر.

## ۲) یک چیز جدید بساز: اول پلان، بعد تأیید

```powershell
py -3.10 15_SYSTEM\scripts\hades.py plan --kind project --name "پروژه انیمیشن" --description "هدف" --type animation
# خروجی: PLAN-XXXXXXXXXXXX | id | path
py -3.10 15_SYSTEM\scripts\hades.py apply --plan PLAN-XXXXXXXXXXXX --approve
```

`plan` فقط می‌نویسد چه می‌خواهد بسازد؛ `apply --approve` می‌سازد. اگر عجله داری،
`new` همان دو را با هم انجام می‌دهد ولی باز هم `--approve` لازم دارد:

```powershell
py -3.10 15_SYSTEM\scripts\hades.py new --kind organization --name "Example Provider" --url "https://example.com" --approve
```

نام فارسی در مانیفست می‌ماند و مسیر پوشه ASCII می‌شود. این عمدی است: هارنس‌ها،
Git و ابزارهای خط فرمان با مسیر غیرASCII می‌لنگند.

## ۳) kinds موجود

`project` `organization` `model` `model_version` `news` `benchmark` `prompt`
`workflow` `asset` `deliverable` `channel` `episode` `campaign` `app` `tutorial`
`task` `decision` `wiki_note` `agent` `subagent` `skill` `mcp` `hook` `command`
`mode` `loop` `harness` `plugin` `template` `policy` `sandbox` `experiment`
`candidate`

هر kind در `15_SYSTEM/config/system.json` تعریف شده: ناحیه، ظرف، نام مانیفست و
المان‌های لازم. افزودن یک نوع جدید یعنی یک ردیف در همان جدول، نه ویرایش اسکریپت.

## ۴) پیدا کردن و وصل کردن

```powershell
py -3.10 15_SYSTEM\scripts\hades.py list --kind skill
py -3.10 15_SYSTEM\scripts\hades.py show --id SKL-XXXXXXXX
py -3.10 15_SYSTEM\scripts\hades.py search --query "انیمیشن"
py -3.10 15_SYSTEM\scripts\hades.py link --id PRJ-XXXXXXXX --rel depends_on --to MOD-XXXXXXXX
py -3.10 15_SYSTEM\scripts\hades.py graph
py -3.10 15_SYSTEM\scripts\hades.py context --project PRJ-XXXXXXXX
```

`context` بسته‌ای که به ایجنت می‌دهی را می‌سازد و سقف کاراکتش از config می‌آید؛
ناحیه‌های مجاز به خواندن هم همان‌جا محدود می‌شوند.

## ۵) از آزمایشگاه تا نهایی

```powershell
py -3.10 15_SYSTEM\scripts\hades.py promote --id EXP-XXXXXXXX --to candidates --approve
py -3.10 15_SYSTEM\scripts\hades.py promote --id CAND-XXXXXXXX --to production --approve
```

ارتقا چهار شرط را یک‌جا می‌خواهد: `evaluation.passed`، `safety_review.passed`،
`human_approved` و وجود واقعی فایل‌های `evidence_paths` روی دیسک. هر کدام نباشد،
دستور رد می‌شود و فهرست کمبودها را چاپ می‌کند. داده آموزشی و checkpoint کپی
نمی‌شوند.

بازگشت هم راه‌بر دارد، نه خاطره. پیش از دست زدن به چیزی:

```powershell
py -3.10 scripts\base.py --save --note "پیش از تغییر"
py -3.10 scripts\base.py --status
```

`--save` فقط وقتی ثبت می‌کند که همهٔ گیت‌ها سبز باشند؛ خانهٔ قرمز پایه نمی‌شود، چون
پایه‌ای که نشود به آن اعتماد کرد دو بار کار را خراب می‌کند. بعد از تغییری که اندازه‌گیری‌اش
بد شد: `py -3.10 scripts\base.py --recover --candidate 14_CANDIDATES/loop/cand-x.md`
همان بایت‌ها را برمی‌گرداند، اثرانگشت را دوباره اثبات می‌کند و `fell_back: true` را در
`14_CANDIDATES/loop/recovery.jsonl` می‌نویسد. برگشت مغز را برمی‌گرداند و کاغذها را نه:
ردیف‌های قفسه و درس‌هایی که بعد از پایه ثبت شده‌اند می‌مانند، و فایلی که بعد از پایه
افزوده شده نام برده می‌شود و حذف نمی‌شود.

## ۶) اسکیل را به هارنس بده

```powershell
py -3.10 15_SYSTEM\scripts\hades.py sync --harness HAR-XXXXXXXX
```

فقط اسکیل‌های `status: approved` که در `approved_for_harness_ids` آن هارنس هستند
کپی می‌شوند؛ اسکیل‌های غایب از آینه پاک می‌شوند. هارنس ناشناخت = رد، چون adapter
تأیید نشده یک ادعاست نه یک اتصال.

## ۷) دروازهٔ هارنس و اجرای ایجنت‌ها

مغز از طریق پروتکل MCP روی stdio صدا زده می‌شود — بدون پورت، کلید و دیمن
(`15_SYSTEM/scripts/mcp_server.py`؛ نمونهٔ اتصال OpenCode و Claude Desktop در
`15_SYSTEM/integrations/`). ابزارهای خواندن بازند و تنها ابزار نوشتن
`candidate_propose` است که یک ردیف ثبت‌شده روی قفسهٔ قرنطینه می‌گذارد — ایجنت
پیشنهاد می‌دهد، انسان تصمیم می‌گیرد.

```powershell
py -3.10 15_SYSTEM\scripts\mcp_server.py          # خودِ دروازه؛ هارنس این را اجرا می‌کند
py -3.10 15_SYSTEM\scripts\runs.py start --agent AGT-XXXXXXXX --goal "..."
py -3.10 15_SYSTEM\scripts\runs.py step --run RUN-XXXXXXXX --text "..."
py -3.10 15_SYSTEM\scripts\runs.py finish --run RUN-XXXXXXXX --status completed
py -3.10 15_SYSTEM\scripts\runs.py promote --run RUN-XXXXXXXX   # خروجِ شاهد از صفحهٔ یک‌بارمصرف
py -3.10 15_SYSTEM\scripts\runs.py list
py -3.10 15_SYSTEM\scripts\orchestrator.py workflow validate --file WF.json
py -3.10 15_SYSTEM\scripts\orchestrator.py workflow run --file WF.json --agent AGT-XXXXXXXX
py -3.10 15_SYSTEM\scripts\orchestrator.py tool list
py -3.10 15_SYSTEM\scripts\orchestrator.py ltm fetch --query "..."
```

موتورِ اجرا در پکیج `15_SYSTEM/scripts/backend/` است — لاجیک SuperAGI به‌صورت stdlib:
ماشینِ وضعیت و حلقهٔ گام، toolkit ها با allowlist واقعی (`tool_allowlist` ایجنت)،
workflow اعلانی، ریاضیِ schedule و حافظهٔ بلندمدت FTS5. فقط گام‌های قطعی اجرا می‌شوند؛
گامِ LLM تصمیمِ انسان است، نه کارِ موتور.

ایجنتی که رجیستری نشناسد نمی‌تواند اجرا شروع کند. ران‌ها در `12_RUNTIME/agent_runs/`
زندگی می‌کنند و در مرز گیت می‌میرند؛ `promote` فید را *داخل* ردیف قفسه صادر می‌کند و
فقط به فایل‌های track شده اشاره می‌کند — پوشهٔ ران هرگز شاهد نیست، چون پشت مرز گیت است.

## ۸) ویکی

```powershell
py -3.10 15_SYSTEM\scripts\wiki.py build
py -3.10 15_SYSTEM\scripts\wiki.py serve
```

سایت فقط از ناحیه‌های ۰۰ تا ۱۰ ساخته می‌شود و `01_INBOX` و `10_ARCHIVE` را هم
برای خودش نمی‌خواند مگر با `--include` صریح (و فقط برای ناحیه انسانی). خروجی روی
`127.0.0.1` می‌نشیند و `noindex` می‌گیرد.

## ۹) انتشار به GitHub

```powershell
py -3.10 15_SYSTEM\scripts\hades.py export --path 11_CONTROL/skills/SKL-XXXXXXXX-name
py -3.10 15_SYSTEM\scripts\hades.py publish --path 11_CONTROL/skills/SKL-XXXXXXXX-name --repo OWNER/REPO --approve
```

`export` تک‌تک فایل‌ها را برای راز، symlink و نوع باینری بررسی می‌کند؛ یک
BLOCKED یعنی publish مسدود. انتشار فقط مخزن **جدید خصوصی** است و بعد از ساخت،
visibility را از GitHub دوباره می‌خواند؛ اگر PRIVATE نبود، هشدار می‌دهد.

## ۱۰) راهنمای کامل

این فایل فقط دستورهای روزمره است. برای توضیح کامل ناحیه‌ها، انواع رکورد و رابطه‌های
تعریف‌شده در قرارداد (عددشان را در جدول بخش ۰ همین فایل بخوان، نه از حافظه)، فهرست گیت‌ها،
عیب‌یابی پیام‌به‌پیام و بخش انگلیسی، `00_START_HERE/GUIDE_FA_EN.md` را بخوان.

## ۱۱) تست گیت‌ها

```powershell
py -3.10 15_SYSTEM\scripts\test_hades.py
```

یک والت موقت می‌سازد، عیب عمدی داخلش می‌گذارد و بررسی می‌کند که ابزار قرمز شود.
روی والت اصلی چیزی نمی‌نویسد. اگر یک قانون را بشکنی و تست سبز بماند، آن قانون
دیگر گیت نیست — و این تست همان را لو می‌دهد.
