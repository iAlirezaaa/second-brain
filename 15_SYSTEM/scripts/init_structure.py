"""HADES OS v3 -- zone seeder.

Creates the two-plane zone structure with a README per zone and a .gitkeep in
every leaf folder. Idempotent: existing folders, READMEs and .gitkeep files are
left untouched, so it is safe to re-run after editing a README.

Run:  py -3.10 15_SYSTEM/scripts/init_structure.py
      py -3.10 15_SYSTEM/scripts/init_structure.py --check   (report only)
"""
import sys
import argparse
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]

# (dir, plane, one-line purpose, subfolders, README body)
# plane: "human" = 00..10, "machine" = 11..15
ZONES = [
    ("00_START_HERE", "human", "نقطه ورود انسان و ایجنت",
     ["dashboards"],
     "اینجا را اول بخوان. راهنمای شروع، نقشه سیستم، پروتکل بوت ایجنت و سند طراحی در این ناحیه‌اند.\n\n"
     "چه چیزی اینجا نمی‌نشیند: داده، لاگ، تنظیمات ماشین، خروجی پروژه. اینها رجیستری و حالت‌اند و جای دیگری هستند."),

    ("01_INBOX", "human", "صف ورودی خام",
     ["web_clips", "transcripts", "voice_notes", "bookmarks", "triage"],
     "هر چیزی که از بیرون می‌آید و هنوز دسته‌بندی نشده اینجا می‌ریزد. خام ماندن در این ناحیه اشکال نیست؛ "
     "اشکال آن است که چیزی در ۰۱ بماند و کسی تریاژش کند و فراموش شود.\n\n"
     "گردش کار: raw -> triaged -> linked -> verified -> promoted -> archived. فایل خام اینجا شناسه رجیستری نمی‌گیرد؛ بعد از تریاژ است که به یک رکورد با شناسه در ناحیه مقصد تبدیل می‌شود."),

    ("02_WIKI", "human", "روایت قابل‌فهم برای انسان",
     ["concepts", "decisions", "glossary", "indexes", "playbooks", "reference_maps", "_site"],
     "لایه روایت: مفهوم، واژه‌نامه، تصمیم، دستورکار و نقشه مرجع. خروجی ویکی‌ساز هم در `_site` می‌نشیند.\n\n"
     "قانون تفکیک: فکت‌های رجیستری (مدل، قیمت، خبر) در ۰۴ می‌مانند و صفحه ویکی فقط آنها را با شناسه نقل می‌کند؛ "
     "کپی‌کردن عدد به داخل ویکی یعنی دو منبع حقیقت. پیشوند شناسه: WIK. تصمیم‌ها رکورد DEC در ۰۹ هستند و اینجا فقط نقل می‌شوند."),

    ("03_PROJECTS", "human", "پروژه‌ها و ساختارشان",
     ["active", "incubating", "paused", "completed", "archived", "portfolios", "_templates"],
     "برای هر پروژه یک پوشه با `project.json` و مستندات. وضعیت در مانیفست و نام پوشه باید یکی باشد.\n\n"
     "قانون مهم: **کد اینجا نمی‌نشیند.** مانیفست آدرس مخزن کد را می‌دهد (`repo.path`، `repo.remote`، `repo.branch`) "
     "و آن مخزن تاریخچه خودش را دارد. زیرپروژه با `parent_ids` وصل می‌شود، نه با تودرتوکردن فولدر. "
     "نسخه شخصی یک پروژه با `variant_of` ثبت می‌شود و رجیستری موازی نمی‌سازد. پیشوند شناسه: PRJ."),

    ("04_INTELLIGENCE", "human", "اخبار، مدل‌ها و شرکت‌ها در یک مرجع",
     ["organizations", "models", "news", "releases", "benchmarks", "pricing_snapshots", "papers", "licenses_policies", "watchlists"],
     "اتم‌های حقیقت درباره اکوسیستم AI: شرکت، خانواده مدل، نسخه مدل، خبر، بنچمارک، اسنپ‌شات قیمت، مقاله و لایسنس. "
     "هر رکورد منبع، تاریخ مشاهده و تاریخ آخرین بررسی را نگه می‌دارد.\n\n"
     "خانواده مدل، نسخه مدل، API و رانتایم محلی چهار شیء جدا هستند؛ نام نسخه را جای نام خانواده نگذار. "
     "این ناحیه خوراک ویکی است، نه خود ویکی. پیشوند: ORG، MOD، VER، NWS، BMK."),

    ("05_WORKS", "human", "پرامپت، workflow، اَسِت و تحویل‌دادنی نهایی",
     ["prompts", "workflows", "assets", "deliverables"],
     "چیزهای بازاستفاده‌شدنی و خروجی‌های نهایی: پرامپت، workflow (ComfyUI، n8n، Remotion، DCC)، "
     "مانیفست اَسِت و فایل تحویل‌شده.\n\n"
     "فایل حجیم بیرون از اینهاست و اینجا فقط مسیر مرجع، هش و نسخه‌اش ثبت می‌شود. هر تحویل‌دادنی باید زنجیره "
     "`uses_model_ids` / `uses_prompt_ids` / `produced_by` را داشته باشد، وگرنه قابل بازتولید نیست. "
     "پیشوند: PRM، WFL، AST، DEL."),

    ("06_CHANNELS", "human", "کانال‌ها، اپیزودها و انتشار",
     ["channels", "episodes", "campaigns", "calendar", "metrics"],
     "شبکه‌های اجتماعی، پادکست، کمپین، تقویم انتشار و متریک.\n\n"
     "کلید API، رمز و توکن اینجا نمی‌نشیند؛ فقط ارجاع به مخزن رمز (`secret_ref`). متریک با تاریخ اندازه‌گیری "
     "یا بی‌اعتبار علامت می‌خورد. پیشوند: CHN، EPI، CMP."),

    ("07_PRODUCTS", "human", "محصول‌ها و اپ‌ها",
     ["apps", "miniapps", "games", "extensions"],
     "اپ، مینی‌اپ، بازی، اکستنشن و وضعیت انتشار هرکدام. باینری خروجی بیرون از Vault است و اینجا لینک با هش "
     "و نسخه می‌ماند. پیشوند: APP."),

    ("08_LEARNING", "human", "آموزش و دوره",
     ["tutorials", "courses", "learning_paths", "exercises", "credentials_metadata_only"],
     "آموزش، دوره، مسیر یادگیری و تمرین. ادعای به‌روز بودن بدون تاریخ بررسی مجاز نیست؛ اعتبار اسناد و "
     "مدرک‌ها فقط به‌صورت متادیتا ثبت می‌شود. پیشوند: TUT."),

    ("09_OPERATIONS", "human", "کار روزمره و کسب‌وکار",
     ["tasks", "meetings", "clients_metadata_only", "kpis", "incidents", "decisions"],
     "تسک، جلسه، کارفرما، KPI، حادثه و تصمیم کسب‌وکاری.\n\n"
     "سطح دسترسی این ناحیه از بقیه مستقل است: اطلاعات کارفرما و مالی فقط متادیتا، بدون هرگونه مدرک احراز هویت. "
     "این ناحیه به‌صورت پیش‌فرض در context ایجنت نمی‌آید. پیشوند: TSK، DEC."),

    ("10_ARCHIVE", "human", "اسنپ‌شات منجمد",
     ["knowledge", "projects", "works", "lab"],
     "هر چیزی که از ناحیه‌های بالا حذف یا بایگانی شده، اینجا یخ می‌زند. اینجا خواندنی است: یک فایل بایگانی‌شده "
     "ویرایش نمی‌شود، جایگزینش رکورد تازه است با `supersedes`.\n\n"
     "بایگانی، بکاپ نیست. بکاپ نسخه‌ی قابل‌بازیابیِ کل است و جای دیگری تعریف می‌شود."),

    ("11_CONTROL", "machine", "قانون‌نامه ایجنت‌ها",
     ["agents", "subagents", "skills", "mcp", "hooks", "commands", "modes", "loops",
      "harnesses", "plugins", "templates", "policies", "permissions", "sandboxes", "routing", "evaluations"],
     "تعریف چیزهای ایجنتی، نه لاگ آنها: ایجنت، ساب‌ایجنت، اسکیل، MCP، هوک، دستور، مود، حلقه، هارنس، پلاگین، "
     "قالب، سیاست، سطح‌دسترسی، سندباکس، routing و معیار ارزیابی.\n\n"
     "این تنها ناحیه صفحه ماشین است که باید در Git بماند، چون «قانون» است و تاریخچه‌اش ارزش دارد. "
     "پیشوند: AGT، SAG، SKL، MCP، HOK، CMD، MDE، LOP، HAR، PLG، TPL، POL، SBX."),

    ("12_RUNTIME", "machine", "حافظه و حالت ماشین (قابل حذف)",
     ["harness_memory", "sessions", "traces", "jobs", "telemetry", "context_packs", "cache", "audit"],
     "جایی که هر هارنس چیزهایی که یادش هست را می‌گذارد: حافظه هر هارنس در `harness_memory/<HAR>/`، نشست‌ها، "
     "trace، صف کار، هزینه و تلمتری، بسته‌های context، cache و زنجیره ممیزی.\n\n"
     "قانون: چیزی که اینجا است و مهم است، هنوز مهم نشده است. برای مهم‌شدن باید ارتقا بخورد به صفحه انسان "
     "(۰۲ یا ۰۳ یا ۰۵) با شناسه و شاهد. این ناحیه در Git نیست، در context پیش‌فرض نیست، و پاک‌کردنش "
     "نباید هیچ دانشی را از بین ببرد. فایل‌هایش شناسه رجیستری نمی‌گیرند؛ با زمان و شناسه اجرا نام می‌گیرند."),

    ("13_LAB", "machine", "آزمایش و ترین، قرنطینه",
     ["models_in_training", "agents_in_training", "experiments", "evals", "checkpoints_metadata_only"],
     "مدل‌ها و ایجنت‌های در حال آموزش اینجا هستند و هیچ دسترسی تولیدی ندارند: نه در ایندکس تولیدی، نه در "
     "context پیش‌فرض، نه در ویکی.\n\n"
     "صراحت: فولدر جدا **سندباکس واقعی نیست**. قرنطینه واقعی یعنی کاربر/کانتینر/VM و دسترسی فایل و شبکه جدا. "
     "تا آن نباشد، این فقط یک قرارداد ادعایی است. پیشوند: EXP."),

    ("14_CANDIDATES", "machine", "انتخاب‌های آماده تأیید تو",
     ["agents", "skills", "outputs"],
     "تنها پوشه صفحه ماشین که عمداً باز می‌کنی. بهترین‌هایی که از ۱۳ بیرون آمده‌اند، هرکدام با عدد و فایل شاهد: "
     "پاس ارزیابی، بازبینی ایمنی، و آدرس لاگ یا خروجی‌ای که این نتیجه را ساخته.\n\n"
     "کاندید با تأیید صریح تو به ۱۱ (ایجنت/اسکیل) یا ۰۵ (خروجی هنری) ارتقا می‌یابد. «بهتر شده» یعنی شاهد، "
     "نه قضاوت مدل. پیشوند: CAND."),

    ("15_SYSTEM", "machine", "زیرساخت",
     ["config", "schemas", "scripts", "generated", "migrations", "integrations", "templates"],
     "config، schema، اسکریپت‌ها، ایندکس تولیدشده، مهاجرت نسخه و یادداشت اتصال به ابزار بیرون (Obsidian، "
     "هارنس‌ها، GitHub).\n\n"
     "پوشه `15_SYSTEM/generated` هرگز دستی ویرایش نمی‌شود؛ از بازسازی تازه می‌آید. کلید و رمز در هیچ فایل این "
     "ناحیه نمی‌نشیند؛ فقط `secret_ref`."),
]


def zone_readme(z, root):
    d, plane, purpose, subs, body = z
    head = "# %s\n\n> صفحه %s | %s\n\n%s\n" % (d, "انسان (00-10)" if plane == "human" else "ماشین (11-15)", purpose, body)
    return head


def plan(root, create):
    made_dirs = made_readme = made_keep = skipped = 0
    for z in plan_zones():
        d, plane, purpose, subs, body = z
        zone_dir = root / d
        leafs = [zone_dir] + [zone_dir / s for s in subs]
        for p in leafs:
            if not p.exists():
                if create:
                    p.mkdir(parents=True)
                made_dirs += 1
            else:
                skipped += 1
        # README belongs to the zone folder only
        rd = zone_dir / "README.md"
        if not rd.exists():
            if create:
                rd.write_text(zone_readme(z, root), encoding="utf-8")
            made_readme += 1
        # .gitkeep only in leaf folders that hold no README
        for p in leafs:
            if p == zone_dir:
                continue
            gk = p / ".gitkeep"
            if not gk.exists():
                if create:
                    gk.write_text("", encoding="utf-8")
                made_keep += 1
    return made_dirs, made_readme, made_keep, skipped


def plan_zones():
    return ZONES


GITIGNORE_HEAD = """# HADES OS v3 -- the machine plane never leaves this disk.
# Every path below is also required by 15_SYSTEM/config/system.json
# (gitignore_required_paths); doctor fails if the two lists drift.
12_RUNTIME/
13_LAB/
14_CANDIDATES/
15_SYSTEM/generated/
15_SYSTEM/backups/
"""

GITIGNORE_TAIL = """
# credentials and session state -- never in the vault, never in git
.env
*.env
.secrets/
credentials.json
token.json
*_token.txt
*.pem
*.p12
*.key
ssh/
Browser/
**/Cookies
**/Login Data

# large media: registry holds the path + hash, the file stays on storage
*.mp4 *.mov *.mkv *.wav *.als *.hip *.blend *.psd *.zip *.7z *.rar *.ckpt *.safetensors *.bin

# tooling noise
__pycache__/
*.pyc
.DS_Store
Thumbs.db
desktop.ini
.obsidian/workspace*
"""


def seed_gitignore(root, create):
    """Create-only: an existing .gitignore belongs to the owner, never overwritten."""
    gi = root / ".gitignore"
    if gi.exists():
        return 0, "kept (owner edits win)"
    if create:
        gi.write_text(GITIGNORE_HEAD + GITIGNORE_TAIL, encoding="utf-8")
    return 1, "created"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report what is missing without writing")
    args = ap.parse_args()
    create = not args.check
    dirs, readme, keep, skipped = plan(ROOT, create)
    gi_n, gi_state = seed_gitignore(ROOT, create)
    verb = "created" if create else "would create"
    print("HADES OS v3 seeder | root: %s" % ROOT)
    print("zones declared: %d" % len(ZONES))
    print("%s folders: %d | READMEs: %d | .gitkeep: %d | already present: %d"
          % (verb, dirs, readme, keep, skipped))
    print(".gitignore: %s" % gi_state)
    if args.check and (dirs or readme or keep or gi_n):
        print("INCOMPLETE: structure is missing items above")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
