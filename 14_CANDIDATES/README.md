# 14_CANDIDATES — قفسهٔ کاندیدها / the candidate shelf

**صفحهٔ ماشین است، نه دانش.** هیچ چیزی اینجا تولیدی نیست تا وقتی انسان ارتقا بدهد.
This is the machine plane's review shelf: nothing here is knowledge until a human promotes it.

## چه چیزی داخلش مجاز است

- `loop/` — گزارش چرخهٔ بهبود (`scripts/loop.py`)؛ تنها بخشِ این ناحیه که در Git ثبت می‌شود.
- زیرپوشه‌های `agents/ skills/ outputs/` — کاندیدهای ساخته‌شده از `13_LAB`، با مانیفست `CAND-*`.

`README.md` هم مثل `loop/` استثناست: بقیهٔ این پوشه در `.gitignore` قرنطینه است، چون
خروجیِ ماشین حالت محلی و قابل‌دورریختن است.

## What lives here

- `loop/` — improvement-loop cycle reports, written by `scripts/loop.py`. The only tracked part.
- `agents/`, `skills/`, `outputs/` — candidates promoted out of `13_LAB`, each with a `CAND-*` manifest.

## گیت‌ها / the gates

1. **هیچ نوشتاری از اینجا به صفحهٔ انسان راه نمی‌یابد مگر با promote.**
   Nothing reaches the human plane except through `promote`.
2. **کاندید بدون شاهد، کاندید نیست.** `evidence_paths` باید روی دیسک وجود داشته باشد؛
   گیت `doctor` و `promote` هر دو همین را چک می‌کنند، نه باورِ عددِ داخل مانیفست.
   A candidate without a witness on disk is a guess.
3. **ادعای رفتاری با اجرای واقعی سنجیده می‌شود، نه با تیک.**
   `scripts/probe.py` must have run before a behaviour claim is promotable
   (`docs: ROADMAP.md → Phase 9.5`, borrowed from google-research/harness²).
4. **ردّ هم یک خروجی است.** اگر چرخهٔ جدید چیزی بهتر از وضعیت فعلی نساخت،
   گزارش باید صریحاً بنویسد `keep_base` — نه اینکه یک تغییر اختراع کند.

این ناحیه در ایندکس تولیدی حساب نمی‌شود (`hades.py index` آن را کنار می‌گذارد) و برای
زمینهٔ پیش‌فرض ایجنت مسدود است (`denied_for_default_context`).
