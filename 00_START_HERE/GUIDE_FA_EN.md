# راهنمای جامع HADES OS v3

> این سند دو بخش دارد: **فارسی**، سپس **English**. هر دو یک سیستم را توصیف می‌کنند؛ اگر فقط یکی را می‌خوانی، بخش فارسی کامل است. اگر بین این سند و دیسک اختلافی دیدی، **دیسک درست است**: مرجع نهایی `15_SYSTEM/config/system.json`، کدِ اسکریپت‌ها و خروجی `doctor` است، نه این متن.

نسخه: `3.0.0` | تاریخ نوشتن: 2026-10-24 | ریشه: `E:\Agent\HADES_OS_v3`

**فهرست**

۱. این سیستم چه مشکلی را حل می‌کند
۲. دو صفحه در یک نگاه
۳. نقشه شانزده ناحیه
۴. شناسه: چرا و چگونه
۵. شکل یک رکورد
۶. سی‌وسه نوع و جای هرکدام
۷. رابطه‌ها
۸. دستورها، دسته‌بندی‌شده
۹. چرخه عمر: از خام تا تولیدی
۱۰. گیت‌ها: چه چیزی واقعاً جلوی تو را می‌گیرد
۱۱. راز، Git، بکاپ، سندباکس
۱۲. عیب‌یابی: پیام، معنا، راه‌حل
۱۳. مرز صداقت
۱۴. گام بعدی
۱۵. واژه‌نامه

---

## ۱) این سیستم چه مشکلی را حل می‌کند

سه درد را هدف گرفته است:

- **حافظه‌ی پراکنده‌ی هارنس‌ها.** هر هارنس (Codex، Claude، Cursor، Hermes، …) حافظه، اسکیل و تنظیمات خودش را دارد. وقتی سشن تمام می‌شود، دانش داخل آن هم تمام می‌شود. اینجا هر چیزی که ارزش نگه‌داشتن دارد شناسه می‌گیرد و روی دیسک می‌نشیند.
- **پروژه‌های بی‌زنجیره.** یک فینال بدون این‌که بدانی با کدام مدل، پرامپت و ورک‌فلو ساخته شده، فقط یک فایل خوش‌شانس است. اینجا زنجیره تولید فیلد اجباری است.
- **خبر و مدل‌هایی که در ده جا پخش‌اند.** یک مرجع برای شرکت، خانواده مدل، نسخه، خبر و بنچمارک؛ و یک ویکی که از همان مرجع نقل می‌کند، نه کپی.

قانون مرکزی، در یک جمله: **چیزی که فقط در حافظه‌ی هارنس است، حافظه نیست.** یا شناسه و شاهد دارد، یا هنوز دانش نشده.

## ۲) دو صفحه در یک نگاه

```
        ┌──────────────── صفحه انسان (۰۰–۱۰) ────────────────┐
        00_START_HERE   01_INBOX   02_WIKI   03_PROJECTS
        04_INTELLIGENCE 05_WORKS   06_CHANNELS 07_PRODUCTS
        08_LEARNING     09_OPERATIONS 10_ARCHIVE
        └────── می‌خوانی، ویرایش می‌کنی، ویکی می‌سازی، تصمیم می‌گیری ──────┘
                                  ▲
                     promote (شناسه + شاهد + تأیید تو)
                     context (بسته‌ی محدود و بودجه‌دار)
                                  │
        ┌──────────────── صفحه ماشین (۱۱–۱۵) ────────────────┐
        11_CONTROL   تعریف: ایجنت، اسکیل، MCP، هوک، هارنس
        12_RUNTIME   حالت: سشن، آینه، صف -- دورریختنی
        13_LAB       آزمایش و آموزش -- قرنطینه
        14_CANDIDATES کاندید آماده‌ی تأیید -- با شاهد
        15_SYSTEM    config، schema، اسکریپت، قالب، خروجی
        └────── ایجنت می‌نویسد، می‌سوزاند، و ارتقا می‌دهد ──────┘
```

**قانون سه‌سؤالی برای جای هر فایل:**

1. با چشم می‌خوانی یا ویرایش می‌کنی؟ → ۰۰ تا ۱۰.
2. ماشین می‌نویسد و پاک‌کردنش هیچ دانشی را نمی‌بَرد؟ → `12_RUNTIME` (یا `13_LAB` اگر آزمایش است).
3. ماشین می‌نویسد ولی پاک‌کردنش دانش را می‌برد؟ → باز هم می‌تواند موقتاً در ماشین بماند، ولی باید **promote** شود به صفحه انسان با شناسه و شاهد.

این مرز عمدی است: همیشه می‌دانی یک فایل **برای خواندن توست** یا **برای سوختن ماشین**. صفحه ماشین لازم نیست در ذهنت باشد؛ صفحه انسان باید باشد.

## ۳) نقشه شانزده ناحیه

| ناحیه | صفحه | چه چیزی اینجاست | نوع رکورد |
|---|---|---|---|
| `00_START_HERE` | انسان | سند طراحی، همین راهنما، شروع، نقشه، داشبورد | — |
| `01_INBOX` | انسان | ورود خام: کلیپ، رونوشت، بوکمارک، صف تریاژ | — |
| `02_WIKI` | انسان | روایت، مفهوم، واژه‌نامه، دستورکار، سایت ساخته‌شده در `_site` | `WIK` |
| `03_PROJECTS` | انسان | مانیفست و مستند پروژه؛ **کد اینجا نیست** | `PRJ` |
| `04_INTELLIGENCE` | انسان | شرکت، خانواده مدل، نسخه، خبر، بنچمارک | `ORG` `MOD` `VER` `NWS` `BMK` |
| `05_WORKS` | انسان | پرامپت، ورک‌فلو، مانیفست اَسِت، تحویل نهایی | `PRM` `WFL` `AST` `DEL` |
| `06_CHANNELS` | انسان | کانال، اپیزود، کمپین | `CHN` `EPI` `CMP` |
| `07_PRODUCTS` | انسان | اپ، مینی‌اپ، بازی، اکستنشن | `APP` |
| `08_LEARNING` | انسان | آموزش، دوره، مسیر یادگیری | `TUT` |
| `09_OPERATIONS` | انسان | تسک، تصمیم، کارفرما، KPI؛ پیش‌فرض از context بیرون | `TSK` `DEC` |
| `10_ARCHIVE` | انسان | اسنپ‌شات منجمد و فقط‌خواندنی | — |
| `11_CONTROL` | ماشین | **تعریف**: ایجنت، اسکیل، MCP، هوک، دستور، مود، حلقه، هارنس، پلاگین، قالب، سیاست، سندباکس | `AGT` `SAG` `SKL` `MCP` `HOK` `CMD` `MDE` `LOP` `HAR` `PLG` `TPL` `POL` `SBX` |
| `12_RUNTIME` | ماشین | **حالت**: حافظه هارنس، سشن، تریس، صف کار، آینه اسکیل؛ gitignored | — |
| `13_LAB` | ماشین | آزمایش و آموزش مدل/ایجنت؛ gitignored، هرگز تولیدی | `EXP` |
| `14_CANDIDATES` | ماشین | کاندید آماده تأیید، با شاهد؛ gitignored | `CAND` |
| `15_SYSTEM` | ماشین | `config`، `schemas`، `scripts`، `templates`، `integrations`، `migrations`، `generated`، `backups` | — |

دو ناحیه رکورد نمی‌گیرند و این عمدی است:

- `01_INBOX` فایل خام است نه دانش. تا وقتی تریاژ نشده، شناسه ندارد؛ بعد از تریاژ به یک رکورد در ناحیه‌ی مقصد تبدیل می‌شود.
- `10_ARCHIVE` انبار اسنپ‌شات است. رکوردها بایگانی نمی‌شوند که «جابه‌جا» شوند؛ وضعیتشان عوض می‌شود (`archived` یا `deprecated`) و در ناحیه‌ی خودشان می‌مانند. یک نوع رکورد یک ناحیه دارد و جابه‌جایی فیزیکی، `doctor` را قرمز می‌کند.

پوشه‌های کمکی `11_CONTROL/evaluations`، `permissions` و `routing` یادداشت‌اند و ظرف رکورد نیستند.

## ۴) شناسه: چرا و چگونه

هر رکورد یک شناسه دارد با این شکل:

```
PRJ-7C1A9E20
│   └──────── ۸ رقم هگزادسیمال (A-F و 0-9)
└──────────── پیشوند نوع، ۲ تا ۶ حرف بزرگ
```

- الگو: `^[A-Z]{2,6}-[0-9A-F]{8}$` — همان چیزی که در `15_SYSTEM/schemas/manifest.schema.json` نوشته شده و `doctor` enforce می‌کند.
- پیشوند باید با نوع رکورد بخواند (`PRJ` برای project، `SKL` برای skill). پیشوند غلط، خطای `doctor` است.
- شناسه در نام پوشه و فایل هم می‌آید؛ به همین دلیل مسیر **ASCII** می‌ماند و نام فارسی فقط در محتوا زندگی می‌کند. Git، Task Scheduler و `gh` روی مسیر غیر ASCII می‌لنگند.
- شناسه‌ی تکراری، خطای `doctor` است. `new` و `plan` قبل از ساخت، شناسه‌های موجود را می‌خوانند.
- **تله‌ی نام فایل:** اگر یک مانیفست را دستی به اسمی غیر از اسم اعلام‌شده در config تغییر بدهی (یا شناسه را از سر فایل حذف کنی)، آن رکورد از دید رجیستری بیرون می‌رود. `new` همیشه نام درست را می‌سازد؛ دستی تغییرش نده.

## ۵) شکل یک رکورد

هر مانیفست یک شیء JSON با شش فیلد مشترک است: `id`، `kind`، `name`، `status`، `classification`، `created_at`. نمونه‌ی واقعی یک پروژه:

```json
{
  "kind": "project",
  "id": "PRJ-7C1A9E20",
  "name": "پروژه نمونه",
  "status": "incubating",
  "classification": "internal",
  "created_at": "2026-10-24",
  "type": "animation",
  "repo": { "path": "E:/Layout/projects/sample", "remote": "", "branch": "main" },
  "notes": "هدف در یک جمله",
  "tags": [],
  "relations": {}
}
```

- **`classification`**: `public` | `internal` | `confidential` | `restricted`؛ پیش‌فرض `internal`. این فیلد برچسب است، نه دیوار؛ ACL فایل‌سیستم در این بسته اجرا نمی‌شود.
- **`status`**: از مجموعه‌ی مجاز همان نوع. جدول کامل در بخش ۶ و در `config` (`status_sets`).
- **`repo`**: مسیر و ریموت مخزن کد. کد در والت نیست؛ مانیفست فقط آدرس می‌دهد.
- **`relations`**: همه‌ی لینک‌ها یک‌جا. با `hades.py link` هم قابل ساخت است.

سه چیدمان برای رکوردها وجود دارد و config تعیینش می‌کند:

| چیدمان | یعنی | نمونه |
|---|---|---|
| `folder` | پوشه‌ای به نام `ID-slug` با مانیفست داخلش | `project`، `skill`، `agent` |
| `file` | یک فایل به نام `ID-slug.json` | `news`، `hook`، `harness` |
| `subfolder` | زیرمجموعه‌ی والد | `model_version` در `04_INTELLIGENCE/models/<MOD-ID>/versions/` |

`news` و `wiki_note` به‌جای JSON، یک `note.md` با frontmatter می‌نویسند؛ همان شناسه، ولی خوانا برای انسان.

## ۶) سی‌وسه نوع و جای هرکدام

نوع، قرارداد است: ناحیه، ظرف، نام مانیفست و فیلدهای اجباری‌اش از `config` می‌آید. **افزودن نوع تازه = یک ردیف در config، نه ویرایش کد.**

| نوع | پیشوند | ناحیه و ظرف | چه وقت استفاده می‌شود |
|---|---|---|---|
| `project` | `PRJ` | `03_PROJECTS` / وضعیت پروژه | یک کار مستقل با هدف و محدوده |
| `organization` | `ORG` | `04` / `organizations` | شرکت یا تیم سازنده‌ی مدل |
| `model` | `MOD` | `04` / `models` | خانواده مدل، نه یک نسخه‌ی مشخص |
| `model_version` | `VER` | `04` / `models/<MOD>/versions` | نسخه، قیمت، رانتایم |
| `news` | `NWS` | `04` / `news` | ادعای بیرونی با منبع و تاریخ مشاهده |
| `benchmark` | `BMK` | `04` / `benchmarks` | عدد سنجش همراه پروتکل |
| `wiki_note` | `WIK` | `02` / `concepts`، `decisions`، `glossary`، `playbooks`، `reference_maps` | روایت با ارجاع شناسه‌ای |
| `prompt` | `PRM` | `05` / `prompts` | پرامپت بازاستفاده‌شدنی |
| `workflow` | `WFL` | `05` / `workflows` | گراف ComfyUI، n8n، Remotion، DCC |
| `asset` | `AST` | `05` / `assets` | فایل حجیم با مسیر، هش، مجوز |
| `deliverable` | `DEL` | `05` / `deliverables` | خروجی نهایی با زنجیره تولید |
| `channel` | `CHN` | `06` / `channels` | کانال انتشار |
| `episode` | `EPI` | `06` / `episodes` | یک انتشار مشخص در یک کانال |
| `campaign` | `CMP` | `06` / `campaigns` | کمپین چندکاناله |
| `app` | `APP` | `07` / `apps\|miniapps\|games\|extensions` | محصول نرم‌افزاری |
| `tutorial` | `TUT` | `08` / `tutorials\|courses\|learning_paths` | آموزش با تاریخ اعتبار |
| `task` | `TSK` | `09` / `tasks` | کار با موعد و پروژه |
| `decision` | `DEC` | `09` / `decisions` | تصمیم با تاریخ و قابلیت برگشت |
| `agent` | `AGT` | `11` / `agents` | ایجنت با دامنه خواندن/نوشتن و allowlist |
| `subagent` | `SAG` | `11` / `subagents` | زیرایجنت با والد و ابزار محدود |
| `skill` | `SKL` | `11` / `skills` | دستورنامه‌ی اجرایی با `SKILL.md` |
| `mcp` | `MCP` | `11` / `mcp` | اتصال ابزار با transport و endpoint |
| `hook` | `HOK` | `11` / `hooks` | واکنش به رویداد؛ پیش‌فرض خاموش |
| `command` | `CMD` | `11` / `commands` | دستور کوتاه و تکرارشدنی |
| `mode` | `MDE` | `11` / `modes` | بسته‌ی سیاست و دامنه برای یک نوع کار |
| `loop` | `LOP` | `11` / `loops` | اجرای زمان‌بندی‌شده |
| `harness` | `HAR` | `11` / `harnesses` | رانتایم بیرونی با مسیر حافظه، کانفیگ و آینه |
| `plugin` | `PLG` | `11` / `plugins` | بسته‌ی توسعه |
| `template` | `TPL` | `11` / `templates` | قالب ساخت رکورد |
| `policy` | `POL` | `11` / `policies` | قاعده با دامنه‌ی اعمال |
| `sandbox` | `SBX` | `11` / `sandboxes` | تعریف محیط جداشده با `isolation` |
| `experiment` | `EXP` | `13_LAB` / `experiments\|agents_in_training\|models_in_training` | آزمایش با هدف و معیار رد‌شدنی |
| `candidate` | `CAND` | `14_CANDIDATES` / `agents\|skills\|outputs` | کاندید آماده‌ی تأیید با شاهد |

**وضعیت‌های مجاز:**

| نوع | وضعیت‌ها |
|---|---|
| `project` | incubating → active → paused / completed → archived |
| `experiment` | running → evaluating → passed / failed → archived |
| `candidate` | proposed → reviewed → approved / rejected |
| `agent`، `subagent` | draft → tested → approved → production → deprecated |
| `skill` | draft → tested → approved → deprecated |
| `model`، `model_version` | rumored → announced → available → deprecated |
| `news` | unverified → verified → superseded |
| `organization` | tracked → verified → stale |
| `tutorial` | draft → verified → stale |
| بقیه | draft → tested → approved → deprecated |

وضعیتی که برای نوعی تعریف نشده باشد، رد می‌شود؛ `doctor` فهرست مجاز را در همان خط خطا چاپ می‌کند.

## ۷) رابطه‌ها

سیزده رابطه وجود دارد؛ همه در `config` تعریف شده‌اند و `doctor` هر کدام را چک می‌کند:

| کلید | معنا | نکته |
|---|---|---|
| `parent_ids` | والد ساختاری؛ چند والد مجاز | زیرپروژه با این وصل می‌شود، نه با تودرتوکردن پوشه |
| `depends_on` | پیش‌نیاز مسدودکننده | تا آماده نباشد، خروجی یکپارچه نیست |
| `integrates_with` | قرارداد رابط، بدون والدیت | برای اتصال دو سیستم نه دو نسخه |
| `related_ids` | ارجاع ساده | هیچ الزام اجرایی ندارد |
| `variant_of` | نسخه‌ی شخصی یا جایگزین همان چیز | از رجیستری موازی جلوگیری می‌کند |
| `derived_from` | خط‌خون | از چه ساخته شده |
| `supersedes` | جایگزین یک رکورد | رکورد قبلی باید deprecated شود، نه حذف |
| `uses_model_ids` | کدام مدل این را ساخت | زنجیره تولید |
| `uses_prompt_ids` | کدام پرامپت | زنجیره تولید |
| `uses_workflow_ids` | کدام ورک‌فلو | زنجیره تولید |
| `produced_by` | کدام ایجنت یا اجرا | زنجیره تولید |
| `approved_for_harness_ids` | کدام هارنس مجاز است | `sync` بدون این کاری نمی‌کند |
| `evidence_paths` | فایل‌های شاهد روی دیسک | **مسیر است، نه شناسه**؛ وجود فایل چک می‌شود |

هر مقدار دیگر باید یک شناسه‌ی کامل و موجود باشد. مقدار بدشکل (`PRJ-123`) و مقدار ناموجود، هر دو خطا هستند؛ اولی خطرناک‌تر است چون شبیه لینک سالم به نظر می‌رسد.

## ۸) دستورها، دسته‌بندی‌شده

همه از ریشه‌ی والت و با `py -3.10` اجرا می‌شوند. دلیلش: `python` پیش‌فرض این ماشین ۳.۹ است و روی کنسول cp1252 ویندوز، فارسی را می‌شکند.

**بررسی سلامتی**

```powershell
py -3.10 15_SYSTEM\scripts\hades.py doctor
py -3.10 15_SYSTEM\scripts\hades.py doctor --json
py -3.10 15_SYSTEM\scripts\hades.py status
py -3.10 15_SYSTEM\scripts\hades.py index
py -3.10 15_SYSTEM\scripts\hades.py qc
```

`doctor` ناحیه‌ها، مانیفست‌ها، شناسه‌ها، رابطه‌ها، `.gitignore`، رازها، UTF-8، مخزن تودرتو، رکورد قاچاقی داخل `12_RUNTIME` و بهداشت فارسی را می‌خواند. `index` فایل `15_SYSTEM/generated/catalog.json` را از اسکن زنده می‌سازد.

**ساخت: اول پلان، بعد تأیید**

```powershell
py -3.10 15_SYSTEM\scripts\hades.py plan --kind project --name "پروژه انیمیشن" --description "هدف" --type animation
py -3.10 15_SYSTEM\scripts\hades.py apply --plan PLAN-XXXXXXXXXXXX --approve
```

`plan` فقط می‌نویسد چه می‌خواهد بسازد و در `15_SYSTEM/generated/plans/` ذخیره می‌کند. `apply --approve` می‌سازد و **قبل از هر چاپ** مهر `applied` را روی پلان می‌زند؛ اگر چاپ بشکند، رکورد یتیم نمی‌ماند. پلان مصرف‌شده دوباره اجرا نمی‌شود.

```powershell
py -3.10 15_SYSTEM\scripts\hades.py new --kind organization --name "Example Provider" --url "https://example.com" --approve
```

`new` همان plan و apply در یک قدم است و بدون `--approve` رد می‌شود. فیلدهای اختیاری بسته به نوع: `--status`، `--classification`، `--tags`، `--container`، `--parent`، `--depends-on`، `--variant-of`، `--type`، `--url`، `--category`، `--org`، `--model`، `--version`، `--engine`، `--path`، `--project`، `--produced-by`، `--platform`، `--channel`، `--capabilities`، `--agent`، `--transport`، `--endpoint`، `--event`، `--action`، `--invocation`، `--schedule`، `--mode`، `--runtime`، `--isolation`، `--experiment`، `--metric`، `--template-kind`، `--name-slug`.

**دیدن و پیدا کردن**

```powershell
py -3.10 15_SYSTEM\scripts\hades.py list --kind skill
py -3.10 15_SYSTEM\scripts\hades.py list --zone 03_PROJECTS
py -3.10 15_SYSTEM\scripts\hades.py show --id SKL-XXXXXXXX
py -3.10 15_SYSTEM\scripts\hades.py search --query "انیمیشن" --limit 20
py -3.10 15_SYSTEM\scripts\hades.py graph
```

`search` همه‌ی کلمات کوئری را با هم می‌خواهد و ناحیه‌های ممنوع را نمی‌خواند. `--machine` این فهرست ممنوع را خاموش می‌کند (پس ۰۹ و ۱۲ و ۱۳ و ۱۴ را هم می‌بیند)؛ آگاهانه استفاده کن. `graph` گراف `mermaid` را در `15_SYSTEM/generated/graph.mmd` می‌نویسد.

**بسته‌ی context برای ایجنت**

```powershell
py -3.10 15_SYSTEM\scripts\hades.py context --project PRJ-XXXXXXXX
py -3.10 15_SYSTEM\scripts\hades.py context --project PRJ-XXXXXXXX --max-chars 6000
```

مانیفست پروژه، فایل‌های همان پوشه و رکوردهای وصل‌شده را تا سقف کاراکتر (پیش‌فرض از config: `12000`) جمع می‌کند و در `15_SYSTEM/generated/context/` می‌نویسد. ناحیه‌های ممنوع با برچسب `DENIED` رد می‌شوند، نه ساکت.

**وصل کردن**

```powershell
py -3.10 15_SYSTEM\scripts\hades.py link --id PRJ-XXXXXXXX --rel depends_on --to MOD-XXXXXXXX
```

اگر مقصد هنوز وجود نداشته باشد، لینک نوشته می‌شود ولی هشدار می‌دهد و `doctor` آن را «آویزان» گزارش می‌کند. نام رابطه باید در config باشد.

**ارتقا**

```powershell
py -3.10 15_SYSTEM\scripts\hades.py promote --id EXP-XXXXXXXX --to candidates --approve
py -3.10 15_SYSTEM\scripts\hades.py promote --id CAND-XXXXXXXX --to production --approve
```

چهار شرط، هر چهارتا هم‌زمان: `evaluation.passed == true`، `safety_review.passed == true`، `human_approved == true`، و وجود واقعی هر مسیر در `evidence_paths`. اگر یکی نباشد، دستور رد می‌شود و فهرست کمبودها را چاپ می‌کند. منبع در آزمایشگاه می‌ماند؛ داده‌ی آموزشی و checkpoint کپی نمی‌شوند.

**هارنس و آینه‌ی اسکیل**

```powershell
py -3.10 15_SYSTEM\scripts\hades.py sync --harness HAR-XXXXXXXX
```

فقط اسکیل‌های `status: approved` که شناسه‌ی هارنس در `approved_for_harness_ids` آن‌ها هست کپی می‌شوند. اسکیل‌هایی که از آینه بیرون می‌افتند پاک می‌شوند. هارنس ناشناس یا بدون `skills_dir` رد می‌شود: آداپتر تأییدنشده یک ادعاست، نه اتصال.

**ویکی**

```powershell
py -3.10 15_SYSTEM\scripts\wiki.py build
py -3.10 15_SYSTEM\scripts\wiki.py build --open
py -3.10 15_SYSTEM\scripts\wiki.py serve --port 8765
```

سایت فقط از ناحیه‌های ۰۰ تا ۱۰ ساخته می‌شود. `01_INBOX`، `10_ARCHIVE` و خود `02_WIKI` به‌صورت پیش‌فرض خوانده نمی‌شوند؛ `--include` فقط ناحیه‌ی انسانی می‌پذیرد. هر پیوند داخلی که به لنگر موجود نرسد، ساخت را با خروج غیرصفر می‌ایستد. خروجی `noindex` دارد و سرور فقط روی `127.0.0.1` می‌نشیند.

**انتشار**

```powershell
py -3.10 15_SYSTEM\scripts\hades.py export --path 11_CONTROL\skills\SKL-XXXXXXXX-name
py -3.10 15_SYSTEM\scripts\hades.py publish --path 11_CONTROL\skills\SKL-XXXXXXXX-name --repo OWNER/NAME --approve
```

`export` فقط ممیزی است و چیزی بیرون نمی‌نویسد: symlink، فایل باینری، فایل بزرگ‌تر از ۸ مگابایت، بیش از ۱۰۰۰ فایل و هر الگوی راز، `BLOCKED` می‌شود و یک `BLOCKED` کل انتشار را متوقف می‌کند. `publish` فقط مخزن **تازه و خصوصی** می‌سازد، مخزن موجود را رد می‌کند، و بعد از ساخت visibility را از GitHub دوباره می‌خواند تا «خصوصی» بودن ادعا نماند. هیچ‌چیز خودکار بیرون نمی‌رود.

**آزمون گیت‌ها**

```powershell
py -3.10 15_SYSTEM\scripts\test_hades.py
py -3.10 15_SYSTEM\scripts\test_hades.py --keep
```

یک والت موقت در `%TEMP%` می‌سازد، عیب عمدی می‌گذارد و بررسی می‌کند ابزار قرمز شود. روی والت اصلی چیزی نمی‌نویسد.

**لانچر**

```powershell
start.bat check
start.bat build
start.bat test
start.bat all
start.bat wiki
```

`start.bat` فقط ASCII است (کنسول ویندوز با کدپیج cp1252 متن فارسی داخل `.bat` را می‌شکند) و خودش `py -3.10` را صدا می‌زند.

**کدهای خروج**

| کد | معنا |
|---|---|
| `0` | انجام شد؛ سالم |
| `1` | خطای وضعیت یا ورودی (`ERROR:`، `doctor` قرمز، `qc` کثیف، پیدا نشد) |
| `2` | گیت سیاستی رد کرد (`REFUSED:`، `BLOCKED:`) |

## ۹) چرخه عمر: از خام تا تولیدی

```
ورودی خام (01)  →  تریاژ  →  رکورد + شناسه (02..09)  →  لینک و اعتبارسنجی
                                                        │
آزمایش (13_LAB)  →  ارزشیابی با شاهد  →  کاندید (14)  →  تأیید تو
                                                        │
                                       11_CONTROL (agent / skill، approved)
                                     یا 05_WORKS (deliverable، فینال)
```

- **ورودی:** تا `verified` نشده، حق ورود به ویکی ندارد. منبع بیرونی داده است، نه دستور.
- **پروژه:** وضعیت مانیفست و نام پوشه باید یکی باشد؛ جابه‌جایی فیزیکی آگاهانه است، نه خودکار.
- **ادعای بیرونی:** بی‌تاریخ یعنی بی‌اعتبار. رکوردی که `last_verified` یا `observed_at` آن از ۹۰ روز کهنه‌تر باشد، هشدار می‌گیرد.
- **خروجی بهتر = فینال:** مسیر کوتاه برای کار هنری: `14_CANDIDATES/outputs/` → تأیید تو → `05_WORKS/deliverables/` با زنجیره‌ی `uses_model_ids`، `uses_prompt_ids`، `uses_workflow_ids` و `produced_by`.
- **افت کیفیت:** رکورد `deprecated` می‌شود، جایگزینش با `supersedes` وصل می‌شود؛ حذف نمی‌شود.

## ۱۰) گیت‌ها: چه چیزی واقعاً جلوی تو را می‌گیرد

| گیت | چه چیزی را می‌ایستاند | کجا اجرا می‌شود |
|---|---|---|
| schema | فیلد اجباری غایب یا خالی، نوع غلط، وضعیت غیرمجاز | `apply` قبل از نوشتن، و `doctor` |
| ناحیه و ظرف | رکورد بیرون ناحیه‌ی نوعش، یا در پوشه‌ی اعلام‌نشده | `doctor` (و `apply`) |
| شناسه | قالب غلط، پیشوند غلط، تکرار | `apply` و `doctor` |
| رابطه | مقدار بدشکل یا مقصد ناموجود | `doctor` |
| شاهد | مسیر شاهد روی دیسک نیست | `doctor` و `promote` |
| ارتقا | یکی از چهار شرط | `promote` |
| آینه | هارنس ناشناس، `skills_dir` نبودن، اسکیل تأییدنشده | `sync` |
| راز | الگوی کلید/توکن یا آنتروپی بالا | `doctor`، `export`، `publish` |
| مرز Git | مسیر لازم در `.gitignore` نیست، یا `.git` تودرتو | `doctor` |
| انتشار | مخزن موجود، visibility غیر PRIVATE، فایل بزرگ، symlink، باینری | `export` و `publish` |
| ویکی | ناحیه‌ی ماشین در خروجی، لنگر مرده | `wiki.py` |
| بهداشت فارسی | کاراکتر چینی/کانا/هنگول/تایلندی، شبیه‌عربی، چسبیدگی لاتین | `qc` و `doctor` (هشدار) |

هر گیت یک تست منفی دارد: اگر قانون را بشکنی و تست سبز بماند، آن قانون دیگر گیت نیست. شمارش تست‌ها را خود اجرا چاپ می‌کند، نه این سند.

## ۱۱) راز، Git، بکاپ، سندباکس

- **راز:** هیچ کلید، رمز، کوکی، توکن یا فایل session داخل والت نه. فقط `secret_ref` با اشاره به مدیر رمز. اسکنر الگو و آنتروپی، هم روی کل والت (`doctor`) و هم روی مسیر انتشار (`export`) اجرا می‌شود.
- **Git:** یک مخزن خصوصی برای خود OS (۰۰ تا ۱۰، `11_CONTROL`، `15_SYSTEM` به‌جز `generated` و `backups`) و یک مخزن جدا برای کد هر پروژه بیرون از والت. `12_RUNTIME`، `13_LAB`، `14_CANDIDATES` و `15_SYSTEM/generated` هرگز کامیت نمی‌شوند.
- **بکاپ:** Git و Sync بکاپ نیستند. سه نسخه لازم است: دیسک سالم، دیسک مستقل، مقصد رمزنگاری‌شده‌ی خارج از محل. این بسته فقط مانیفست و مسیرها را نگه می‌دارد؛ زمان‌بندی خودکار ندارد. بکاپی که restore‌اش آزمایش نشده، بکاپ نیست.
- **سندباکس:** پوشه، سندباکس نیست؛ فقط قرنطینه‌ی سازمانی است. تا کانتینر یا VM با کاربر جدا نباشد، `isolation: none` صادقانه‌ترین مقدار است. `13_LAB` در مانیفست آزمایش همین را ثبت می‌کند.

## ۱۲) عیب‌یابی: پیام، معنا، راه‌حل

| پیام | معنا | راه‌حل |
|---|---|---|
| `duplicate id X in A and B` | دو رکورد هم‌شناسه | یکی را با `supersedes` بازنشسته کن و شناسه‌ی تازه بساز |
| `malformed id reference k -> 'v'` | مقدار رابطه شکل شناسه ندارد | شناسه‌ی کامل `PREFIX-8HEX` بگذار |
| `dangling relation k -> ID` | مقصد وجود ندارد | مقصد را بساز، یا رابطه را با `link` درست کن |
| `record for kind X sits outside its zone` | فایل در ناحیه‌ی اشتباه | به ناحیه‌ی نوعش ببر (جدول بخش ۶) |
| `folder 'x' is not a declared container` | پوشه‌ی اعلام‌نشده | به ظرف‌های مجاز همان نوع ببر |
| `project status 's' disagrees with folder 'f'` | وضعیت و پوشه یکی نیست | پوشه یا مانیفست را هم‌تراز کن |
| `kind X requires a non-empty 'f'` | فیلد اجباری خالی است | مقدار واقعی بگذار؛ رشته‌ی خالی یعنی فقدان |
| `evidence file does not exist` | شاهد روی دیسک نیست | فایل را بگذار یا مسیر را درست کن |
| `registry manifest inside 12_RUNTIME` | رکورد در ناحیه‌ی دورریختنی | با `promote` به صفحه‌ی انسان ببر |
| `possible secret (...)` | الگوی راز پیدا شد | حذف کن و `secret_ref` بگذار |
| `non-ASCII path segment` | نام مسیر فارسی است | مسیر ASCII، نام در محتوا |
| `.gitignore does not exclude X` | مرز مستند و واقعی فرق دارد | `.gitignore` را با `gitignore_required_paths` هم‌تراز کن |
| `nested git repo inside the vault` | `.git` تودرتو | مخزن را بیرون ببر؛ دو تاریخچه برای یک چیز ممنوع |
| `zone without README` | ناحیه بی‌راهنما | `init_structure.py` را اجرا کن |
| `last verified ... days ago` (هشدار) | ادعای کهنه | دوباره بررسی کن و تاریخ را به‌روز کن |
| `not valid UTF-8` | فایل خراب یا غیر UTF-8 | با UTF-8 ذخیره کن |
| `persian hygiene {...}` (هشدار) | کاراکتر چینی/شبه‌عربی/چسبیدگی | متن را با حروف فارسی بازنویسی کن |
| `BLOCKED x => not a text type` | باینری در مسیر انتشار | باینری را از مسیر بیرون ببر |
| `REFUSED: apply needs --approve` | تأیید نبود | `--approve` بگذار |
| `REFUSED: plan already applied` | پلان مصرف شده | پلان تازه بساز |
| `REFUSED: unknown harness` | هارنس ثبت نشده | اول رکورد `harness` بساز |
| `REFUSED: harness ... has no skills_dir` | آینه تعریف نشده | `skills_dir` را در مانیفست هارنس بگذار |
| `REFUSED: GitHub CLI (gh) is not installed` | ابزار بیرونی نیست | نصب با توست؛ این بسته ابزار نصب نمی‌کند |
| `ERROR: unknown kind` | نوع اعلام‌نشده | ردیف تازه در `15_SYSTEM/config/system.json` |

## ۱۳) مرز صداقت

این بسته **اسکلت** است، نه سرویس زنده. `doctor` خودش فهرست چیزهایی که enforce نمی‌کند را چاپ می‌کند.

آنچه ساخته نشده: ارکستراسیون زنده و صف کار، RBAC یا ACL واقعی فایل‌سیستم، سندباکس کانتینری، MCP Server مرکزی، جست‌وجوی سمانتیک و Vector DB، همگام‌سازی خودکار GitHub، بکاپ زمان‌دار، و داشبورد آنلاین.

آنچه در همین لحظه اندازه‌گیری شده است (اعداد از اجرای زنده، با تاریخ 2026-10-24):

```
hades.py status  -> zones present: 16/16 | registry records: 0
hades.py doctor  -> errors: 0 | warnings: 0
hades.py qc      -> persian hygiene: clean across 25 files
wiki.py build    -> 16 pages | machine-plane pages: 0
test_hades.py    -> checks: 75 | passed: 75 | failed: 0
```

رجیستری صفر است چون هیچ پروژه، مدل یا خبر واقعی وارد نشده. این عدد عیب نیست؛ نشان می‌دهد داده‌ی نمونه جعل نشده. بازاجرا کن تا عدد روز خودت را ببینی.

## ۱۴) گام بعدی

1. **نقشه‌ی مهاجرت پروژه‌های موجود** (`E:\Layout`، `E:\Agent\BreakDown`، `E:\Social Media` و بقیه): فقط مانیفست و مسیر مخزن ثبت می‌شود؛ هیچ فایلی جابه‌جا نمی‌شود. با تأیید تک‌تک.
2. **هارنس‌ها:** برای هر رانتایمی که واقعاً استفاده می‌کنی یک `HAR` بساز، مسیر حافظه و کانفیگش را بنویس، و `skills_dir` را فقط وقتی اعلام کن که واقعاً وجود دارد.
3. **اسکیل‌های موجود** را به `11_CONTROL/skills` بیاور، وضعیت `draft` به `approved` را با آزمایش، نه با ادعا.
4. **ریموت خصوصی مخزن OS** و اولین کامیت؛ قبلش `doctor` باید صفر خطا باشد.
5. **اولین حلقه‌ی واقعی:** جاروی خبر در `04_INTELLIGENCE/news` با `source_url` و `observed_at`، و بعد ویکی از همان.

## ۱۵) واژه‌نامه

| واژه | معنا |
|---|---|
| رکورد | یک شیء ثبت‌شده با شناسه، نوع، وضعیت و مانیفست روی دیسک |
| مانیفست | فایل JSON یا `note.md` که رکورد را توصیف می‌کند |
| نوع (kind) | قرارداد ناحیه، ظرف، پیشوند و فیلدهای اجباری |
| ظرف (container) | پوشه‌ی مجاز داخل ناحیه برای یک نوع |
| صفحه (plane) | انسان (۰۰–۱۰) یا ماشین (۱۱–۱۵) |
| گیت | بررسی‌ای که با شکستن قانون، قرمز می‌شود |
| promote | انتقال تأییدشده از آزمایش/کاندید به تعریف یا خروجی |
| کاندید | خروجی آزمایش که چهار شرط را دارد و منتظر تأیید است |
| آینه (mirror) | کپی اسکیل‌های تأییدشده در پوشه‌ی یک هارنس |
| بسته‌ی context | مجموعه‌ی محدود و بودجه‌دار فایل‌ها که به ایجنت داده می‌شود |
| شاهد (evidence) | فایل روی دیسک که یک ادعا را پشتیبانی می‌کند |
| supersedes | رابطه‌ی جایگزینی؛ قدیمی می‌ماند، حذف نمی‌شود |

---
---

# HADES OS v3 — Complete Guide

> This document has two halves: **Persian**, then **English**. Both describe the same system. If this text and the disk disagree, **the disk wins**: `15_SYSTEM/config/system.json`, the scripts, and `doctor` output are the source of truth.

Version `3.0.0` | written 2026-10-24 | root `E:\Agent\HADES_OS_v3`

## 1. What problem this solves

- **Harness memory evaporates.** Every harness (Codex, Claude, Cursor, Hermes, ...) keeps its own memory and skills; when the session ends, the knowledge ends. Here anything worth keeping gets an ID and lives on disk.
- **Projects without lineage.** A final cut with no record of the model, prompt and workflow that produced it is a lucky file, not a deliverable. Lineage is a required field here.
- **Scattered news and model facts.** One registry for organizations, model families, versions, news and benchmarks, and a wiki that *cites* that registry instead of copying it.

The one rule: **anything that lives only in harness memory is not memory.** It either has an ID and evidence, or it has not become knowledge yet.

## 2. Two planes at a glance

```
Human plane 00-10 : read, edit, cite, decide, build the wiki
  00_START_HERE  01_INBOX  02_WIKI  03_PROJECTS  04_INTELLIGENCE
  05_WORKS  06_CHANNELS  07_PRODUCTS  08_LEARNING  09_OPERATIONS  10_ARCHIVE

                     ▲  promote (ID + evidence + your approval)
                     │  context (bounded pack)
                     ▼
Machine plane 11-15 : definitions, disposable state, quarantine, candidates
  11_CONTROL (definition)  12_RUNTIME (state)  13_LAB (experiment)
  14_CANDIDATES (review shelf)  15_SYSTEM (config, schema, scripts, output)
```

**Three questions decide where a file goes:**

1. Will you read or edit it with your eyes? → `00`–`10`.
2. Will a machine write it, and deleting it would lose no knowledge? → `12_RUNTIME` (or `13_LAB` if it is an experiment).
3. Will a machine write it, and deleting it *would* lose knowledge? → it may live in the machine plane temporarily, but it must be **promoted** to the human plane with an ID and evidence.

## 3. The sixteen zones

| Zone | Plane | Contents | Record kinds |
|---|---|---|---|
| `00_START_HERE` | human | design doc, this guide, start, map, dashboards | — |
| `01_INBOX` | human | raw intake: clips, transcripts, bookmarks, triage | — |
| `02_WIKI` | human | narrative, concepts, glossary, playbooks, built site in `_site` | `WIK` |
| `03_PROJECTS` | human | project manifests and docs; **no code** | `PRJ` |
| `04_INTELLIGENCE` | human | organizations, model families, versions, news, benchmarks | `ORG` `MOD` `VER` `NWS` `BMK` |
| `05_WORKS` | human | prompts, workflows, asset manifests, final deliverables | `PRM` `WFL` `AST` `DEL` |
| `06_CHANNELS` | human | channels, episodes, campaigns | `CHN` `EPI` `CMP` |
| `07_PRODUCTS` | human | apps, mini-apps, games, extensions | `APP` |
| `08_LEARNING` | human | tutorials, courses, learning paths | `TUT` |
| `09_OPERATIONS` | human | tasks, decisions, clients, KPIs; excluded from default context | `TSK` `DEC` |
| `10_ARCHIVE` | human | frozen, read-only snapshots | — |
| `11_CONTROL` | machine | **definition**: agents, skills, MCP, hooks, commands, modes, loops, harnesses, plugins, templates, policies, sandboxes | `AGT` `SAG` `SKL` `MCP` `HOK` `CMD` `MDE` `LOP` `HAR` `PLG` `TPL` `POL` `SBX` |
| `12_RUNTIME` | machine | **state**: harness memory, sessions, traces, job queue, skill mirrors; gitignored | — |
| `13_LAB` | machine | experiments and training; gitignored, never production | `EXP` |
| `14_CANDIDATES` | machine | candidates awaiting approval, with evidence; gitignored | `CAND` |
| `15_SYSTEM` | machine | `config`, `schemas`, `scripts`, `templates`, `integrations`, `migrations`, `generated`, `backups` | — |

Two zones deliberately take no records. `01_INBOX` holds raw files: intake is not knowledge until triaged, and triage produces a record in the destination zone. `10_ARCHIVE` holds frozen snapshots: records are not physically moved there; they change status (`archived`, `deprecated`) and stay in their own zone, because a kind has exactly one zone and physical moves turn `doctor` red.

## 4. Identifiers

```
PRJ-7C1A9E20
│   └──────── 8 uppercase hex digits
└──────────── kind prefix, 2-6 uppercase letters
```

Pattern `^[A-Z]{2,6}-[0-9A-F]{8}$`, declared in the schema, enforced by `apply` and `doctor`. The prefix must match the kind, IDs must be unique, and the ID appears in the folder or file name so paths stay **ASCII** while Persian lives in the content (Git, Task Scheduler and `gh` misbehave on non-ASCII paths).

One trap: rename a manifest by hand and the record becomes invisible to every gate. `new` always writes the declared name; do not improvise.

## 5. Shape of a record

Six fields are always required: `id`, `kind`, `name`, `status`, `classification`, `created_at`. A project adds `type` and `repo`:

```json
{
  "kind": "project",
  "id": "PRJ-7C1A9E20",
  "name": "Sample project",
  "status": "incubating",
  "classification": "internal",
  "created_at": "2026-10-24",
  "type": "animation",
  "repo": { "path": "E:/Layout/projects/sample", "remote": "", "branch": "main" },
  "notes": "goal in one sentence",
  "tags": [],
  "relations": {}
}
```

`classification` is one of `public`, `internal`, `confidential`, `restricted` (default `internal`). It is a label, not a wall: filesystem ACL enforcement is not implemented in this package.

Layouts: `folder` (`ID-slug/` with the manifest inside), `file` (`ID-slug.json`), `subfolder` (model versions under their family). `news` and `wiki_note` are written as `note.md` with YAML frontmatter.

## 6. The thirty-three kinds

| Kind | Prefix | Zone / container | Use it when |
|---|---|---|---|
| `project` | `PRJ` | `03` / status folder | an independent piece of work |
| `organization` | `ORG` | `04` / organizations | a company or team |
| `model` | `MOD` | `04` / models | a model family, not a version |
| `model_version` | `VER` | `04` / models/<MOD>/versions | a version, its pricing and runtime |
| `news` | `NWS` | `04` / news | an external claim with source and date |
| `benchmark` | `BMK` | `04` / benchmarks | a score with a protocol |
| `wiki_note` | `WIK` | `02` / concepts, decisions, glossary, playbooks, reference_maps | narrative that cites IDs |
| `prompt` | `PRM` | `05` / prompts | a reusable prompt |
| `workflow` | `WFL` | `05` / workflows | ComfyUI, n8n, Remotion, DCC graph |
| `asset` | `AST` | `05` / assets | large file by path, hash, licence |
| `deliverable` | `DEL` | `05` / deliverables | final output with lineage |
| `channel` | `CHN` | `06` / channels | a publishing channel |
| `episode` | `EPI` | `06` / episodes | one publication in a channel |
| `campaign` | `CMP` | `06` / campaigns | a multi-channel campaign |
| `app` | `APP` | `07` / apps, miniapps, games, extensions | a software product |
| `tutorial` | `TUT` | `08` / tutorials, courses, learning_paths | a tutorial with a validity date |
| `task` | `TSK` | `09` / tasks | work with a due date |
| `decision` | `DEC` | `09` / decisions | a decision with date and reversibility |
| `agent` | `AGT` | `11` / agents | an agent with scopes and tools |
| `subagent` | `SAG` | `11` / subagents | a child agent |
| `skill` | `SKL` | `11` / skills | an executable playbook with `SKILL.md` |
| `mcp` | `MCP` | `11` / mcp | a tool connection |
| `hook` | `HOK` | `11` / hooks | an event reaction, off by default |
| `command` | `CMD` | `11` / commands | a short repeatable command |
| `mode` | `MDE` | `11` / modes | a policy bundle for a kind of work |
| `loop` | `LOP` | `11` / loops | a scheduled run |
| `harness` | `HAR` | `11` / harnesses | an external runtime with memory/config/mirror paths |
| `plugin` | `PLG` | `11` / plugins | a distribution bundle |
| `template` | `TPL` | `11` / templates | a record template |
| `policy` | `POL` | `11` / policies | a rule with a scope |
| `sandbox` | `SBX` | `11` / sandboxes | an isolation definition |
| `experiment` | `EXP` | `13_LAB` / experiments, agents_in_training, models_in_training | a falsifiable experiment |
| `candidate` | `CAND` | `14_CANDIDATES` / agents, skills, outputs | a candidate awaiting approval |

Status sets: project `incubating → active → paused/completed → archived`; experiment `running → evaluating → passed/failed → archived`; candidate `proposed → reviewed → approved/rejected`; agent and subagent `draft → tested → approved → production → deprecated`; skill `draft → tested → approved → deprecated`; model and version `rumored → announced → available → deprecated`; news `unverified → verified → superseded`; organization `tracked → verified → stale`; tutorial `draft → verified → stale`; everything else falls back to `draft → tested → approved → deprecated`.

## 7. Relations

Thirteen keys, all checked by `doctor`:

| Key | Meaning |
|---|---|
| `parent_ids` | structural parent, multiple allowed |
| `depends_on` | blocking prerequisite |
| `integrates_with` | interface contract, not parenthood |
| `related_ids` | plain reference |
| `variant_of` | a personal or alternate version of the same thing |
| `derived_from` | lineage |
| `supersedes` | replaces a record; the old one is deprecated, not deleted |
| `uses_model_ids` | which model produced this |
| `uses_prompt_ids` | which prompt |
| `uses_workflow_ids` | which workflow |
| `produced_by` | which agent or run |
| `approved_for_harness_ids` | which harnesses a skill is cleared for |
| `evidence_paths` | **paths on disk**, not IDs; existence is checked |

Every other value must be a complete, existing ID. A malformed target is more dangerous than a missing one because it reads like a working link.

## 8. Commands

Run everything from the vault root with `py -3.10`. On this machine plain `python` is 3.9 with a cp1252 console and breaks Persian output.

Health: `hades.py doctor` (add `--json` for machines), `status`, `index`, `qc`.

Structure: `hades.py plan --kind ... --name ...` writes a plan under `15_SYSTEM/generated/plans/`; `hades.py apply --plan PLAN-... --approve` writes the record and stamps the plan as applied **before** printing, so a console failure cannot orphan a record. `hades.py new ... --approve` is plan plus apply in one step and refuses without the flag.

Inspect: `list --kind X`, `list --zone Z`, `show --id ID`, `search --query "..." [--limit N] [--machine]`, `graph`. `--machine` disables the deny list, so it also reaches `09`, `12`, `13` and `14`; use it deliberately.

Context: `context --project PRJ-... [--max-chars N]` writes a bounded pack to `15_SYSTEM/generated/context/`. Denied zones are marked `DENIED`, never silently skipped.

Link: `link --id A --rel depends_on --to B`. Linking to a missing target warns and leaves `doctor` to flag it as dangling.

Promotion: `promote --id EXP-... --to candidates --approve`, then `promote --id CAND-... --to production --approve`. Four conditions: `evaluation.passed`, `safety_review.passed`, `human_approved`, and every `evidence_paths` file present on disk. The source stays in the lab; training data and checkpoints are not copied.

Harness mirror: `sync --harness HAR-...`. Only `approved` skills naming that harness are copied, stale mirrors are pruned, and an unknown harness or a missing `skills_dir` is refused.

Wiki: `wiki.py build [--open]`, `wiki.py serve [--port 8765]`. Human plane only, `01_INBOX`/`10_ARCHIVE`/`02_WIKI` skipped unless explicitly included, dead internal anchors stop the build, output is `noindex`, server binds `127.0.0.1`.

Publish: `export --path ...` audits only; `publish --path ... --repo OWNER/NAME --approve` creates a brand-new private repo, refuses an existing one, and reads visibility back from GitHub afterwards. One blocked file stops the whole publish.

Tests: `test_hades.py [--keep]` builds a scratch vault in `%TEMP%`, plants defects, and asserts the gates turn red. It never touches the real vault.

Exit codes: `0` ok, `1` state or input error (`ERROR:`, dirty `doctor`/`qc`, not found), `2` policy refusal (`REFUSED:`, `BLOCKED:`).

## 9. Lifecycle

```
raw intake (01) → triage → record + ID (02..09) → link → verify
experiment (13_LAB) → evaluation with evidence → candidate (14) → your approval
   → 11_CONTROL (agent/skill, approved)  or  05_WORKS (deliverable, final)
```

An unverified intake may not enter the wiki. External sources are untrusted data, never instructions. A record that goes stale (no verification for 90 days) is flagged, not trusted. Quality regression means `deprecated` plus `supersedes`, never deletion.

## 10. Gates

| Gate | Blocks | Runs in |
|---|---|---|
| schema | missing or empty required field, wrong type, illegal status | `apply`, `doctor` |
| zone/container | record outside its zone or in an undeclared folder | `doctor`, `apply` |
| ID | bad pattern, wrong prefix, duplicate | `apply`, `doctor` |
| relations | malformed or dangling target | `doctor` |
| evidence | missing witness file | `doctor`, `promote` |
| promotion | any of the four conditions | `promote` |
| mirror | unknown harness, missing `skills_dir`, unapproved skill | `sync` |
| secrets | key/token patterns and high entropy | `doctor`, `export`, `publish` |
| Git boundary | missing `.gitignore` entry, nested `.git` | `doctor` |
| publish | existing repo, non-private visibility, oversize or binary file, symlink | `export`, `publish` |
| wiki | machine-plane page, dead anchor | `wiki.py` |
| Persian hygiene | CJK/kana/hangul/thai, Arabic lookalikes, glued Latin | `qc`, `doctor` (warning) |

Every gate ships with a negative test; if breaking the rule leaves the battery green, the rule was never a gate.

## 11. Secrets, Git, backup, sandbox

No keys, tokens, cookies, passwords or session files in the vault; only `secret_ref`. The pattern and entropy scanner runs across the vault (`doctor`) and across any publish path (`export`).

Git: one private repo for the OS (human plane, `11_CONTROL`, `15_SYSTEM` minus `generated` and `backups`) and a separate repo for each project's code outside the vault. `12_RUNTIME`, `13_LAB`, `14_CANDIDATES` and generated output are never committed. A nested `.git` inside the vault is an error: two histories for one thing.

Backup: Git and Sync are not backups. Three copies are required: a healthy drive, an independent drive, and an encrypted off-site target. This package stores only the manifest and reference paths; scheduling lives outside and must be restore-tested.

Sandbox: a folder is not a sandbox, only organisational quarantine. Until a container or VM with a separate user exists, `isolation: none` is the honest value.

## 12. Troubleshooting

| Message | Meaning | Fix |
|---|---|---|
| `duplicate id ...` | two records share an ID | deprecate one with `supersedes`, mint a new ID |
| `malformed id reference ...` | relation value is not an ID | use the full `PREFIX-8HEX` |
| `dangling relation ...` | target does not exist | create it, or re-link |
| `record for kind X sits outside its zone` | wrong folder | move it to its kind's zone |
| `folder 'x' is not a declared container` | undeclared folder | use an allowed container |
| `project status 's' disagrees with folder 'f'` | status and folder differ | align the folder or the manifest |
| `kind X requires a non-empty 'f'` | required field is empty | write a real value |
| `evidence file does not exist` | witness missing | add the file or fix the path |
| `registry manifest inside 12_RUNTIME` | record stranded in disposable state | promote it |
| `possible secret (...)` | secret pattern detected | remove it, use `secret_ref` |
| `non-ASCII path segment` | non-ASCII folder/file name | ASCII path, Persian content |
| `.gitignore does not exclude X` | documented and real boundary differ | align `.gitignore` with config |
| `nested git repo inside the vault` | second history | move the repo out |
| `zone without README` | zone lost its README | run `init_structure.py` |
| `last verified ... days ago` (warning) | stale claim | re-verify and update the date |
| `not valid UTF-8` | corrupt encoding | save as UTF-8 |
| `persian hygiene {...}` (warning) | wrong script or glued Latin | rewrite with Persian letters |
| `BLOCKED ... => not a text type` | binary in a publish path | keep binaries out |
| `REFUSED: ... needs --approve` | approval missing | add the flag |
| `REFUSED: plan already applied` | plan consumed | create a new plan |
| `REFUSED: unknown harness` | harness not registered | create the `harness` record first |
| `REFUSED: GitHub CLI (gh) is not installed` | external tool missing | installing it is your call; the package installs nothing |

## 13. Honest limits

This is a **skeleton**, not a live service. `doctor` prints the list of things it does not enforce.

Not built: live orchestration and a job queue, real RBAC or filesystem ACL, container sandboxing, a central MCP server, semantic search and a vector DB, automatic GitHub sync, scheduled backups, and an online dashboard.

Measured live on 2026-10-24:

```
hades.py status  -> zones present: 16/16 | registry records: 0
hades.py doctor  -> errors: 0 | warnings: 0
hades.py qc      -> persian hygiene: clean across 25 files
wiki.py build    -> 16 pages | machine-plane pages: 0
test_hades.py    -> checks: 75 | passed: 75 | failed: 0
```

The registry is empty because no real project, model or news item has been entered. That is not a defect; it means no sample data was faked. Re-run the commands to measure your own day.

## 14. Next steps

1. **Migration map** for existing projects (`E:\Layout`, `E:\Agent\BreakDown`, `E:\Social Media`, others): manifests and repo paths only, no file moves, approved one by one.
2. **Harnesses**: one `HAR` per runtime you actually use, with its memory and config paths; declare `skills_dir` only where it exists.
3. **Existing skills** into `11_CONTROL/skills`: `draft` becomes `approved` through experiment, not assertion.
4. **Private remote** for the OS repo and the first commit, after `doctor` reaches zero errors.
5. **First real loop**: news sweep into `04_INTELLIGENCE/news` with `source_url` and `observed_at`, then a wiki built from it.

## 15. Glossary

| Term | Meaning |
|---|---|
| record | a registered object with ID, kind, status and a manifest on disk |
| manifest | the JSON file, or `note.md`, that describes a record |
| kind | the contract for zone, container, prefix and required fields |
| container | the allowed folder inside a zone for one kind |
| plane | human (`00`–`10`) or machine (`11`–`15`) |
| gate | a check that turns red when its rule is broken |
| promote | the approved move from lab or candidate into definition or output |
| candidate | a lab result that meets four conditions and awaits approval |
| mirror | a copy of approved skills inside a harness folder |
| context pack | a bounded, budgeted set of files handed to an agent |
| evidence | a file on disk that supports a claim |
| supersedes | replacement relation; the old record stays, it is not deleted |
