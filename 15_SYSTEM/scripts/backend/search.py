"""Keyword search over the brain's own prose -- BM25-flavoured, rebuilt per call.

Moved out of `mcp_server.py` so the MCP door, the toolkit (`core.vault_search`) and any
other caller share one index implementation. The corpus is this brain's content: human
zones, the shelf's rows and reports, skills, root documents -- not its plumbing.
"""
import math
import re
from pathlib import Path

import common  # noqa: F401  (parse_frontmatter; path bootstrapped by the package)

WORD_RE = re.compile(r"\w+", re.UNICODE)
STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her", "was", "one",
    "our", "out", "day", "get", "has", "him", "his", "how", "its", "new", "now", "old",
    "see", "two", "way", "who", "did", "yes", "this", "that", "with", "from", "have",
    "what", "when", "will", "your", "which", "they", "been", "were", "than", "then",
    "into", "only", "also",
}
SEARCH_SKIP_DIRS = {
    "12_RUNTIME", "13_LAB", "15_SYSTEM", "vault-template", ".git", ".kb", ".github",
    ".cursor", ".windsurf", ".idea", ".vscode", "__pycache__", "node_modules",
}
# files inside kept directories that carry no knowledge of their own
SEARCH_SKIP_NAMES = {"LICENSE", ".gitignore"}


def corpus(root):
    """Every prose .md in the brain: human zones, the shelf's rows and reports, skills,
    the root documents. The machine infrastructure and the engine template are skipped --
    the corpus is *this* brain's content, not its plumbing."""
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        parts = rel.split("/")
        if parts[0] in SEARCH_SKIP_DIRS or parts[0].startswith(".") or path.name in SEARCH_SKIP_NAMES:
            continue
        if len(parts) > 1 and parts[1] in ("__pycache__", "backups", "generated"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        yield rel, text


def tokenize(text):
    return [w for w in WORD_RE.findall(str(text).lower()) if len(w) > 1 and w not in STOPWORDS]


def build_index(root):
    docs, df = [], {}
    for rel, text in corpus(root):
        fm, _body = common.parse_frontmatter(text)
        title = str(fm.get("title") or "")
        if not title:
            m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            title = m.group(1).strip() if m else Path(rel).stem
        toks = tokenize(text)
        docs.append({"path": rel, "title": title, "text": text, "tokens": toks,
                     "zone": rel.split("/")[0] if "/" in rel else "root"})
        for w in set(toks):
            df[w] = df.get(w, 0) + 1
    return docs, df


def vault_search(root, query, limit=5):
    """BM25-flavoured keyword search over the live corpus. Rebuilt per call on purpose:
    an index that can be stale is worse than one that costs 100 ms."""
    docs, df = build_index(root)
    wanted = tokenize(query)
    if not docs or not wanted:
        return []
    n = len(docs)
    scored = []
    for d in docs:
        tf = {}
        for w in d["tokens"]:
            tf[w] = tf.get(w, 0) + 1
        score = 0.0
        for w in wanted:
            if tf.get(w):
                score += (1.0 + math.log(tf[w])) * math.log(1.0 + n / (1.0 + df.get(w, 0)))
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda item: -item[0])
    return scored[:max(1, min(20, limit))]


def snippet(d, wanted, width=160):
    text = d["text"]
    for w in wanted:
        m = re.search(re.escape(w), text.lower())
        if m:
            s = max(0, m.start() - width // 4)
            return text[s:s + width].replace("\n", " ").strip()
    return text[:width].replace("\n", " ").strip()
