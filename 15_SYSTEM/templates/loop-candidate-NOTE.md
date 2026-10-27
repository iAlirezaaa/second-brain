---
id: cand-YYYY-MM-DD-name
type: note
title: کاندید چرخهٔ بهبود
status: raw
owner: agent
topics: [loop, candidate, evidence]
created: YYYY-MM-DD
updated: YYYY-MM-DD
dimension: domain
cue: چه وضعیتی این درس را فعال می‌کند — یک خط، قابل تشخیص توسط ایجنت دیگر
lesson: دفعهٔ بعد دقیقاً چه کار کنم — دستورش اجراشدنی باشد، نه شعار
evidence:
  - HANDOFF.md
  - 14_CANDIDATES/loop/probes/index.jsonl
confidence: 0.0
verdict: keep_base
probe: scripts/health.py
probe_args: []
probe_expects: []
probe_writes: []
---

# قالب: ردیف روی قفسهٔ `14_CANDIDATES/loop/`

این فایل یک **ادعا** است، نه یادداشت. ادعا باید سنجیده شود؛ گیت‌ها همین را
می‌خوانند: `python scripts/candidate_check.py`.

## دو بُعد، دو میلهٔ سنجش

`dimension: invariant` یعنی این کاندید ابزار اندازه‌گیری را تغییر می‌دهد
(`rules/`، `scripts/`، `tests/`). اینجا اجرای واقعی همیشه لازم است — یک قانون
بدون اجرای واقعی فقط یک آرزو است.

`dimension: domain` یعنی محتوا (ویکی، دایرکتوری‌های انسانی، مستندات). اگر ادعا
دربارهٔ رفتار است، باز هم به run نیاز دارد.

## رای چیست و چه چیزی می‌خواهد

| verdict | معنی | برای promotable بودن |
| --- | --- | --- |
| `helped` | بعد از تغییر سنجش بهتر شد | یک probe تازه با outcome=pass |
| `hurt` | سنجش بدتر شد | یک probe تازه با outcome=fail |
| `no_observed_effect` | تغییر دادیم، چیزی تکان نخورد | یک probe تازه |
| `confounded` | سنجش قابل اعتماد نیست | فقط ثبت؛ تکی promote نمی‌شود |
| `keep_base` | جواب صادقانه این است که چیزی تغییر نکند | run لازم نیست — این خروج است، نه شکست |
| `proposed` | این ردیف را loop نام برده و هنوز سنجیده نشده | هرگز promotable نیست؛ اول probe، بعد یک رایِ سنجیده |

`cue: NO_ENTRY` هم قانونی است: «هیچ‌چیز از حافظه به این وضعیت مربوط نبود». این
داده است، نه کمبود — ولی ردیفی که NO_ENTRY است نمی‌تواند هم‌زمان درس هم بدهد.

## ردیف دستی هم شمرده می‌شود

اگر خودت ردیفی نوشتی (نه از زبان loop)، باید در `ledger.jsonl` ثبت شود؛ وگرنه
گیت آن را «ردیفی که هرگز proposed نشده» می‌خواند:

```
py -3.10 scripts/candidate_check.py --register 14_CANDIDATES/loop/<this-file>.md
```

هویت شمارش در هر گزارش چاپ می‌شود: `proposed == adopt + revise + drop + keep_base + open`.

## تازگی، نه تاریخ

probe درختی را توصیف می‌کند که در لحظهٔ اجرا وجود داشت. اگر بعد از اجرای آن فایلی
تغییر کند، اثر انگشت (`fingerprint_at` و `fingerprint_after`) دیگر با درخت فعلی
نمی‌خواند و گیت می‌گوید: **تازه نیست، دوباره اجرا کن**. برای همین بعد از probe چیزی
را دست نزن — اول promote. خودِ ردیف هم امضای هش‌شده دارد (`candidate_digest`): اگر
رای را بعد از اجرا بنویسی، آن اجرا مالِ این متن نیست.

```
py -3.10 scripts/probe.py --candidate 14_CANDIDATES/loop/<this-file>.md
py -3.10 scripts/candidate_check.py --file 14_CANDIDATES/loop/<this-file>.md
```

## promotable شدن

`confidence` باید عددی بین ۰ و ۱ باشد و از کف تعریف‌شده در
`rules/candidate.schema.json` بالاتر برود؛ هر خط `evidence` باید باز شود
(مسیرش روی دیسک، URL، یا شناسهٔ probe در `probes/index.jsonl`). مسیر نمی‌خواند =
جعل، و گیت آن را رد می‌کند.
