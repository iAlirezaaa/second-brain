# HADES OS v3

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
