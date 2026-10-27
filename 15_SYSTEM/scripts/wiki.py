"""HADES OS v3 wiki builder -- human plane only.

Run with:  py -3.10 15_SYSTEM/scripts/wiki.py build
           py -3.10 15_SYSTEM/scripts/wiki.py serve [--port 8765]

Guarantees this file actually enforces (not just documents):
  * only human-plane zones (00-10) are read; the machine plane is never exported
  * 01_INBOX and 10_ARCHIVE are excluded unless --include is passed explicitly
  * every page is built from a file on disk in this run -- no cached content
  * output carries noindex, so a stray port-forward does not become a leak
  * serve binds 127.0.0.1 only; nothing listens on the network by default
"""
import sys
import re
import json
import argparse
import html
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "15_SYSTEM/config/system.json").read_text(encoding="utf-8"))
SITE = ROOT / "02_WIKI" / "_site"
HUMAN_MAX = 10
ALWAYS_OUT = {"01_INBOX", "10_ARCHIVE", "02_WIKI"}

LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
HEAD_RE = re.compile(r"^(#{1,4})\s+(.*)$")
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
# markdown the vault docs actually use; each one is rendered, not printed raw
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
ITAL_RE = re.compile(r"(?<!\*)\*(?=\S)([^*]+?)(?<=\S)\*(?!\*)")
MD_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
# Persian digits are built with chr() so this file never carries a lookalike of
# another writing system; same convention as hades.py.
FA_DIGITS = chr(0x06F0) + "-" + chr(0x06F9)
ORDER_RE = re.compile(r"^((?:[0-9]{1,3}|[" + FA_DIGITS + r"]{1,3})[.)])\s+(.*)$")
QUOTE_RE = re.compile(r"^>\s?(.*)$")
BULLET_RE = re.compile(r"^[-*+]\s+(.*)$")
HR_RE = re.compile(r"^-{3,}$")


def zone_of(rel_path):
    return rel_path.split("/")[0]


def human_zones():
    return {z["dir"] for z in CFG["zones"]
            if z.get("plane") == "human" and int(z["dir"].split("_")[0]) <= HUMAN_MAX}


def sources(include):
    out = []
    # vault-root entry docs are human plane by definition
    for name in ("README.md", "AGENTS.md"):
        p = ROOT / name
        if p.exists():
            out.append((name, p))
    for z in sorted(human_zones()):
        if z in ALWAYS_OUT and z not in include:
            continue
        d = ROOT / z
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.md")):
            r = p.relative_to(ROOT).as_posix()
            out.append((r, p))
    return out


def split_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, text[m.end():]


def slug(rel_path):
    stem = Path(rel_path).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    base = Path(rel_path).parent.as_posix().replace("/", "__").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    ident = re.search(r"[A-Z]{2,6}-[0-9A-F]{8}", rel_path)
    if ident:
        return ident.group().lower()
    return (base + "-" + stem).strip("-") or "page"


def anchor_of(title):
    return re.sub(r"[^0-9A-Za-z\u0600-\u06FF\- ]+", "", title).strip().lower().replace(" ", "-") or "h"


def emphasis(s):
    s = BOLD_RE.sub(r"<strong>\1</strong>", s)
    return ITAL_RE.sub(r"<em>\1</em>", s)


def render_inline(text, link_map=None, cur_dir=""):
    """Escaped HTML with code spans, links, wikilinks, bold and italic applied.

    link_map maps a vault-relative .md path to its page slug, so a doc that says
    [راهنما](00_START_HERE/START.md) lands on that section instead of a dead file link.

    Code spans are stashed behind placeholders first: emphasis and links are then
    matched across a code span, so bold like `**فلان <code>x</code> بهمان**` cannot
    split in half the way a segment-by-segment walk would split it.
    """
    text = html.escape(text, quote=False)
    stash = []

    def hold(m):
        stash.append(m.group(1))
        return "\x00%d\x00" % (len(stash) - 1)

    text = CODE_SPAN_RE.sub(hold, text)
    text = inline_plain(text, link_map, cur_dir)
    return re.sub(r"\x00(\d+)\x00", lambda m: "<code>%s</code>" % stash[int(m.group(1))], text)


def inline_plain(s, link_map, cur_dir):
    def wikilink(m):
        label = (m.group(2) or m.group(1)).strip()
        return '<a href="#%s">%s</a>' % (anchor_of(label), emphasis(label))

    def mdlink(m):
        is_img, label, target = m.group(1) == "!", m.group(2), m.group(3)
        href, kind = resolve_link(target, link_map, cur_dir)
        if is_img:
            return '<img src="%s" alt="%s">' % (href, label)
        if not label:
            return '&lt;%s&gt;' % href
        return '<a href="%s"%s>%s</a>' % (href, ' rel="noopener" target="_blank"' if kind == "ext" else "",
                                          emphasis(label))

    s = LINK_RE.sub(wikilink, s)
    s = MD_LINK_RE.sub(mdlink, s)
    return emphasis(s)


def resolve_link(target, link_map, cur_dir):
    if re.match(r"^[a-z]+://", target) or target.startswith("mailto:"):
        return target, "ext"
    path = target.split("#", 1)[0]
    if not path:
        return target, "frag"
    import posixpath
    rel = posixpath.normpath(path if path.startswith("/") else posixpath.join(cur_dir, path))
    rel = rel.lstrip("/")
    if link_map and rel in link_map:
        return link_map[rel], "page"
    for suff in ("", ".md"):
        if link_map and rel + suff in link_map:
            return link_map[rel + suff], "page"
    return "../../" + rel, "file"


def split_row(line):
    """Split a table row on | but never inside a code span, so `a|b` stays one cell."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    cells, buf, in_code = [], [], False
    for ch in s:
        if ch == "`":
            in_code = not in_code
            buf.append(ch)
        elif ch == "|" and not in_code:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    cells.append("".join(buf).strip())
    return cells


def is_block_start(ln):
    """True when a line cannot be swallowed into the paragraph above it."""
    s = ln.strip()
    if not s or HEAD_RE.match(ln) or HR_RE.match(s):
        return True
    if s.startswith(("```", "|")) or QUOTE_RE.match(s):
        return True
    return bool(BULLET_RE.match(s) or ORDER_RE.match(s))


def to_html(text, meta, link_map=None, cur_dir=""):
    blocks, lines = [], text.splitlines()
    i, n = 0, len(lines)
    in_code, code_buf = False, []
    while i < n:
        ln = lines[i]
        if ln.strip().startswith("```"):
            if not in_code:
                in_code, code_buf = True, []
            else:
                blocks.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code_buf)))
                in_code = False
            i += 1
            continue
        if in_code:
            code_buf.append(ln)
            i += 1
            continue
        h = HEAD_RE.match(ln)
        if h:
            lvl = len(h.group(1))
            t = h.group(2).strip()
            blocks.append('<h%d id="%s">%s</h%d>' % (lvl, anchor_of(t),
                                                       render_inline(t, link_map, cur_dir), lvl))
            i += 1
            continue
        if HR_RE.match(ln.strip()):
            blocks.append("<hr>")
            i += 1
            continue
        s = ln.strip()
        if BULLET_RE.match(s):
            items = []
            while i < n:
                cur = lines[i].strip()
                mm = BULLET_RE.match(cur)
                if mm:
                    items.append(mm.group(1))
                    i += 1
                elif items and lines[i][:1] in (" ", "\t") and cur and not is_block_start(lines[i]):
                    items[-1] += " " + cur          # indented continuation of the bullet above
                    i += 1
                else:
                    break
            blocks.append("<ul>%s</ul>" % "".join(
                "<li>%s</li>" % render_inline(x, link_map, cur_dir) for x in items))
            continue
        om = ORDER_RE.match(s)
        if om:
            items = []
            while i < n:
                cur = lines[i].strip()
                mm = ORDER_RE.match(cur)
                if mm:
                    items.append((mm.group(1), mm.group(2)))
                    i += 1
                elif items and lines[i][:1] in (" ", "\t") and cur and not is_block_start(lines[i]):
                    items[-1] = (items[-1][0], items[-1][1] + " " + cur)
                    i += 1
                else:
                    break
            blocks.append('<ol class="ord">%s</ol>' % "".join(
                '<li><span class="m">%s</span><span>%s</span></li>'
                % (mark, render_inline(txt, link_map, cur_dir)) for mark, txt in items))
            continue
        if QUOTE_RE.match(s):
            quote = []
            while i < n and QUOTE_RE.match(lines[i].strip()):
                quote.append(QUOTE_RE.match(lines[i].strip()).group(1))
                i += 1
            blocks.append("<blockquote>%s</blockquote>" % render_inline(" ".join(quote), link_map, cur_dir))
            continue
        if s.startswith("|") and i + 1 < n and set(lines[i + 1].strip()) <= set("|-: "):
            head = split_row(s)
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            blocks.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
                "".join("<th>%s</th>" % render_inline(c, link_map, cur_dir) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % render_inline(c, link_map, cur_dir) for c in r) for r in rows)))
            continue
        if not s:
            i += 1
            continue
        para = []
        while i < n and not is_block_start(lines[i]):
            para.append(lines[i].strip())
            i += 1
        blocks.append("<p>%s</p>" % render_inline(" ".join(para), link_map, cur_dir))
    if in_code:
        blocks.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code_buf)))
    body = "".join(blocks)
    badge = ""
    if meta.get("status"):
        badge = '<span class="badge">status: %s</span>' % html.escape(meta["status"])
    if meta.get("id"):
        badge = '<span class="id">%s</span>' % html.escape(meta["id"]) + badge
    return badge, body


PAGE = """<!DOCTYPE html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>@@TITLE@@</title>
<style>
:root{--fg:#1d1f24;--mut:#5b6472;--bg:#fbfbfd;--line:#e3e6ec;--acc:#2b5bd7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.85 "Vazirmatn","Segoe UI",Tahoma,sans-serif}
.wrap{display:grid;grid-template-columns:260px 1fr;gap:28px;max-width:1120px;margin:0 auto;padding:24px}
nav{position:sticky;top:16px;align-self:start;max-height:88vh;overflow:auto;font-size:13px}
nav a{display:block;color:var(--mut);text-decoration:none;padding:4px 8px;border-radius:6px}
nav a.on,nav a:hover{background:#eef2fb;color:var(--acc)}
nav a small{display:block;font-size:11px;color:#8a93a5;direction:ltr;text-align:right}
main{min-width:0}
h1{font-size:26px;margin:0 0 6px} h2{font-size:20px;margin:32px 0 8px;border-top:1px solid var(--line);padding-top:16px}
h3{font-size:16px;margin:22px 0 6px} p{margin:10px 0}
.id{font-family:ui-monospace,Consolas,monospace;font-size:11px;background:#eef1f6;color:#3a4354;padding:2px 7px;border-radius:5px;margin-inline-end:8px}
.badge{font-size:12px;color:var(--mut);margin-inline-end:8px}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:right;vertical-align:top}
th{background:#f2f4f8;font-weight:600}
pre{direction:ltr;text-align:left;background:#11151c;color:#dfe6f3;padding:14px;border-radius:10px;overflow:auto;font-size:13px}
code{font-family:ui-monospace,Consolas,monospace}
p>code,li>code,td>code{background:#eef1f6;padding:1px 5px;border-radius:5px;font-size:13px}
a{color:var(--acc)}
ul,ol{padding-inline-start:22px;margin:10px 0}
ol.ord{list-style:none;padding:0}
ol.ord li{display:flex;gap:8px;align-items:baseline;padding:2px 0}
ol.ord li .m{color:var(--mut);flex:none;min-width:2.5ch;text-align:right}
blockquote{margin:14px 0;padding:6px 14px;border-inline-start:3px solid var(--line);
color:var(--mut);background:#f4f6fa;border-radius:8px}
hr{border:0;border-top:1px solid var(--line);margin:26px 0}
img{max-width:100%;height:auto}
strong{font-weight:700}
.foot{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);color:var(--mut);font-size:12px}
@media(max-width:820px){.wrap{grid-template-columns:1fr}nav{position:static;max-height:none}}
</style></head><body><div class="wrap">
<nav>@@NAV@@</nav><main><h1>@@H1@@</h1>@@BODY@@
<div class="foot">HADES OS v3 | ساخته‌شده از @@COUNT@@ فایل انسانی، @@STAMP@@ | این صفحه فقط محلی است و ایندکس نمی‌شود</div>
</main></div>
<script>
document.querySelectorAll('nav a').forEach(function(a){
  a.addEventListener('click',function(){
    document.querySelectorAll('nav a').forEach(function(x){x.classList.remove('on')});
    a.classList.add('on');
  });
});
</script></body></html>
"""


def build(include, open_after):
    srcs = sources(include)
    if not srcs:
        print("REFUSED: no human-plane markdown found -- nothing to build")
        return 2
    SITE.mkdir(parents=True, exist_ok=True)
    pages, skipped = [], []
    for rel_p, p in srcs:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            skipped.append(rel_p)
            continue
        meta, body = split_frontmatter(text)
        title = meta.get("title") or meta.get("name") or Path(rel_p).stem
        pages.append({"rel": rel_p, "slug": slug(rel_p), "title": title,
                      "badge": "", "html": "", "body": body, "meta": meta})
    # pass 2: every slug is known now, so [text](other.md) can point at a section
    link_map = {pg["rel"]: "#" + pg["slug"] for pg in pages}
    for pg in pages:
        cur_dir = str(Path(pg["rel"]).parent.as_posix()).replace("\\", "/")
        pg["badge"], pg["html"] = to_html(pg["body"], pg["meta"], link_map, "" if cur_dir == "." else cur_dir)
        del pg["body"], pg["meta"]
    nav = "".join('<a href="#%s"%s>%s<small>%s</small></a>' % (
        pg["slug"], ' class="on"' if n == 0 else "", html.escape(pg["title"]),
        " &nbsp; " + html.escape(pg["rel"].split("/")[0])) for n, pg in enumerate(pages))
    main_html = "".join('<section id="%s"><h2>%s</h2>%s%s</section>' % (
        pg["slug"], html.escape(pg["title"]), pg["badge"], pg["html"]) for pg in pages)
    # every in-page link must land on an anchor that this build actually emitted
    ids = set(re.findall(r'id="([^"]+)"', main_html))
    dead = sorted({h for h in re.findall(r'href="#([^"]+)"', main_html) if h not in ids})
    if dead:
        for pg in pages:
            for d in dead:
                if ('href="#%s"' % d) in pg["html"]:
                    print("  dead link in %s -> #%s" % (pg["rel"], d))
        print("REFUSED: %d links point at an anchor this build does not contain" % len(dead))
        return 2
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = SITE / "index.html"
    tmp = SITE / "index.html.tmp"
    page = (PAGE.replace("@@TITLE@@", "ویکی HADES OS")
                .replace("@@NAV@@", nav)
                .replace("@@H1@@", "ویکی")
                .replace("@@BODY@@", main_html)
                .replace("@@COUNT@@", str(len(pages)))
                .replace("@@STAMP@@", stamp))
    tmp.write_text(page, encoding="utf-8")
    import os
    os.replace(tmp, out)
    (SITE / "build.json").write_text(json.dumps(
        {"built_utc": stamp, "pages": len(pages), "sources": [p["rel"] for p in pages],
         "unreadable": skipped, "dead_links": 0, "machine_plane_zones_included": 0},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print("wiki built: %d pages | %d unreadable | output %s" % (len(pages), len(skipped), out.relative_to(ROOT)))
    def zone_num(rel_path):
        head = rel_path.split("/")[0]
        m = re.match(r"^(\d{2})_", head)
        return int(m.group(1)) if m else 0
    machine = [p for p in pages if zone_num(p["rel"]) > HUMAN_MAX]
    if machine:
        print("REFUSED: %d machine-plane pages leaked into the site" % len(machine))
        return 2
    print("machine-plane pages in output: 0 (checked after build)")
    if skipped:
        for s in skipped:
            print("  skipped (not UTF-8): %s" % s)
    if open_after:
        import webbrowser
        webbrowser.open(out.as_uri())
    return 0


def serve(port):
    if not (SITE / "index.html").exists():
        print("no site yet -- run: py -3.10 15_SYSTEM/scripts/wiki.py build")
        return 2

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            f = SITE / "index.html"
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.end_headers()
            self.wfile.write(data)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    print("wiki on http://127.0.0.1:%d (Ctrl+C stops it)" % port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="wiki.py")
    ap.add_argument("cmd", choices=["build", "serve"])
    ap.add_argument("--include", nargs="*", default=[],
                    help="human-plane zones to include that are skipped by default: 01_INBOX 10_ARCHIVE")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    def ok_zone(z):
        m = re.match(r"^(\d{2})_", z)
        return bool(m) and int(m.group(1)) <= HUMAN_MAX and z in human_zones()

    bad = [z for z in args.include if not ok_zone(z)]
    if bad:
        print("REFUSED: --include accepts only human-plane zones, not %s" % " ".join(bad))
        return 2
    if args.cmd == "build":
        return build(set(args.include), args.open)
    return serve(args.port)


if __name__ == "__main__":
    sys.exit(main())
