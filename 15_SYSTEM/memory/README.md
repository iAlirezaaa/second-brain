# 15_SYSTEM/memory

> صفحه ماشین (11-15) | حافظه

`lessons.jsonl` تنها منبع حقیقت است: هر خط یک درس، با `cue` / `lesson` / `evidence` /
`confidence` / `verdict`. قراردادش در `rules/memory.schema.json` نوشته شده و
`scripts/memory.py --check` (که `health.py` هم اجرا می‌کند) همان را می‌خواند.

`MEMORY.md` در ریشه فقط رندرِ همین فایل است. دستی ویرایشش نکن — اول خط ledger، بعد
`python scripts/memory.py --render`. اگر دو طرف از هم فاصله بگیرند، گیت رنگ قرمز می‌شود:
حافظه‌ای که با منبعش نمی‌خواند، حافظه نیست.

The ledger is the truth, the root index is a rendering, and the gate refuses the pair when
they drift.

```
py -3.10 scripts/memory.py --recall "stale probe fingerprint"     # retrieve, ordered
py -3.10 scripts/memory.py --add --id mem-x --cue ... --lesson ... \
    --evidence HANDOFF.md,tests/test_phase13_candidate_contract.py \
    --confidence 0.9 --verdict helped --source "chat 2026-10-27"
```

Lesson retired? Do not delete the line — add a new row with `--supersedes mem-x` and keep
the old one for the record.
