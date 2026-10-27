# HADES OS v0.01

یک محفظه محلی برای دانش، پروژه‌ها و ایجنت‌ها. صفحه انسان ۰۰ تا ۱۰، صفحه ماشین ۱۱ به بعد.

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

## وضعیت فعلی (از `doctor` و `status` خوانده می‌شود، نه از این فایل)

این بسته **اسکلت خالی** است: ناحیه‌ها، قراردادها، الگوها و اسکریپت‌های آزمودنی. هیچ پروژه، مدل، خبر یا اسکیل واقعی داخلش نیست و هیچ‌کدام با داده نمونه پر نشده‌اند. رجیستری موجودی را با `hades.py status` بخوان؛ عددی که در این README نباشد، عددی است که کسی اثباتش نکرده.

تأییدهای انجام‌شده روی همین پوشه، با اجرای زنده:

```
hades.py status   -> zones present: 16/16 | registry records: 0
hades.py doctor   -> errors: 0 | warnings: 0
hades.py qc       -> persian hygiene: clean
init_structure.py --check -> OK
test_hades.py     -> failed: 0   (شمارش_checks را خود اجرا چاپ می‌کند)
```

اسکریپت‌ها: `hades.py` (رجیستری و گیت‌ها)، `init_structure.py` (ساخت ناحیه‌ها،
idempotent)، `wiki.py` (سایت ناحیه انسان)، `test_hades.py` (تست‌های مثبت و منفی روی
یک والت موقت). الگوها در `15_SYSTEM/templates`‌اند و فقط قالب‌اند؛ داده نمونه نیستند.

## آنچه اینجا نیست

Orchestrator زنده، صف کارِ اجراکننده، RBAC یا ACL فایل‌سیستم، سندباکس واقعی، MCP Server مرکزی، جست‌وجوی سمانتیک و Vector DB، همگام‌سازی خودکار GitHub، سرویس بکاپ زمان‌دار و داشبورد آنلاین. برای هر کدام اسلات رزرو شده، ولی سرویس ساخته نشده.

---

Owner: Hades 3rd ([@iAlirezaaa](https://github.com/iAlirezaaa))

---

## Engine addendum — second-brain engine v0.0.3 · پیوست موتور

> **EN —** Alongside the HADES plane structure, this repo now ships the **second-brain engine v0.0.3**: an agent harness toolkit that enforces the same philosophy as scripts. `vault-template/` holds a fenced-zone starter vault (00_Inbox…90_Agent_Output) the agent reads via `vault-template/AGENTS.md`; `rules/` and the tests are machine-readable; every capability is test-gated. Run the suite with `python -m unittest discover -s tests` and the health check with `python scripts/health.py`. Install into a fresh home with `python scripts/install.py`. The engine inherited the quarantine→promote, gap-register and write-gate patterns — direct implementations of the promotion and safety gates this design already specified.
>
> **FA —** در کنار ساختار صفحاتِ HADES، این ریپو از این به بعد **موتورِ سکند برین نسخهٔ 0.0.3** را هم دارد: کیت ابزارِ هارنسِ ایجنت که همان فلسفه را با اسکریپت اجرا می‌کند، نه با توصیه. `vault-template/` والتی استارتر با زون‌های حصارکشی‌شده است که ایجنت از `vault-template/AGENTS.md` می‌خواند؛ `rules/` و تست‌ها قابل خواندن ماشین هستند و هر قابلیت با تست محافظت می‌شود. سوت را با `python -m unittest discover -s tests` و سلامت ولت را با `python scripts/health.py` صدا بزنید؛ نصب در خانهٔ نو: `python scripts/install.py`. موتور الگوهای قرنطینه→ارتقا، ثبت‌شکاف جست‌وجو و گیتِ نوشتار را هم دقیق همان جاهایی پیاده کرده که این طراحی خواسته بود.
>
> **Maps / نگاشت:** `00_Inbox` ≈ `01_INBOX`، `20_Notes`+`30_Resources` ≈ `02_WIKI`+`15_SYSTEM/templates`، `90_Agent_Output` ≈ `13_LAB`+`14_CANDIDATES`، `promote` ≈ ارتقای `13/14` به صفحهٔ انسان. Two vocabularies, one philosophy: **nothing reaches the human plane un-promoted, nothing breaks a link un-checked.** · دو گویش، یک فلسفه: **هیچ‌چیز بدون ارتقا به صفحهٔ انسان نمی‌رسد، هیچ‌چیز بدون چک لینک نمی‌شکند.**
