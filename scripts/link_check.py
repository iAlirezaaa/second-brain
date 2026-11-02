#!/usr/bin/env python
"""Zero-broken-links enforcer (AGENTS.md rule 1), plus edge confidence and a graph readout.

Usage: python scripts/link_check.py [--vault path] [--confidence | --readout]
Default (gate): exit 0 = clean, exit 1 = broken links found. Also prints the measured shape of
              the graph (components, degree-0, bridges, ambiguity) next to its verdict, so a
              green link gate always says what it looked at and not only what it rejected.
--confidence: print the label count for every edge and name every `ambiguous` edge
              (source, target) — an uncertain edge is escalated, never counted healthy.
--readout:    the graph-health gate `health.py` runs after the link gate — it prints degree-0
              notes, bridge notes and the god-node signal, then refuses while any `ambiguous`
              edge is escalated. A graph the tool cannot settle is not a healthy graph, and
              "OK" over an edge it had to guess at is the silent gate this repo exists to kill.

Why the labels exist (ROADMAP phase 44, taken from graphify's `EXTRACTED | INFERRED |
AMBIGUOUS` edge schema): an edge is labelled by *how it came to exist*, and the label must be
checkable from the source text — no model, no embedding, no graph library.

  extracted  the author wrote a wikilink whose text names exactly one file literally; the
             resolver added nothing, it just opened the file the author pointed at.
  inferred   the resolver had to *deduce* the target — it normalised the author's text
             (folded case, turned backslashes into slashes, appended `.md`) to reach a file
             the author did not name character-for-character. The link is still a real,
             followable connection, but a machine decided the target, not the author's words.
  ambiguous  the link cannot be trusted to have one meaning, so it is escalated to a human
             instead of kept quiet — graphify's third label is literally "Uncertain — flagged
             in the report for manual review". Two cases produce it here: the target lives
             under `14_CANDIDATES/` (a row that waits for a verdict), or the link text matches
             a *colliding stem* that more than one file shares, so "which file did the author
             mean?" is a question the text alone cannot answer.

The old resolver answered the collision question by accident: `files_by_stem = {p.stem.lower():
p for p in targets}` kept whichever path sorted first and silently bound the link to it. That
silent binding is the defect this labels `ambiguous` — a guessed target is not a healthy edge.

The readout answers a *navigation* question, not a retrieval one (correction to the ROADMAP
row): full-text search (`scripts/kb.py`, FTS5) reaches every indexed note whether or not
anything links it, so a degree-0 note is not unreachable by *search*; it is a page no reader
or agent following wikilinks can *arrive at*. The graph is undirected over the vault's notes,
built with a dict and a BFS — no NetworkX, no Leiden, no embeddings, stdlib only.
"""
import argparse
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import SNAPSHOT_ROOT
from common import WIKILINK_RE, find_root, iter_markdown, iter_notes

# every gate prints its verdict in UTF-8: an em dash that dies on a Windows console turns a
# refusal into mojibake, and nobody reads a message they cannot read
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

LABELS = ("extracted", "inferred", "ambiguous")

# one link the parser produced. `path` is the resolved file for extracted/inferred and for a
# candidate-target ambiguous edge; it is None for a colliding-stem ambiguous edge, whose
# `reason` names every file that shares the stem (there is no single target to name).
Edge = namedtuple("Edge", "source target label reason path")


# prose contract files are not notes; their example links are documentation, not data
# the name list lives in common.is_prose so both vault gates agree on what a note is


def in_recorded_base(path, vault):
    """True when this markdown sits inside a known-good base recorded by `scripts/base.py`.

    A recorded base is a byte-for-byte copy of the vault taken so the owner can roll back; it is
    not a second file the author could have meant. `iter_markdown` is deliberately unfiltered — a
    candidate row is not a note but is still a legitimate link target — so the copies arrive in
    the stem index here and must be dropped again, or every live note reads as a stem collision
    and the graph the author drew collapses into 0 edges and one island per note.

    The test is vault-relative, not absolute: judge a base as its own vault and its own links
    resolve, because the exclusion asks "is this inside the plane being judged a copy of?".
    """
    rel = Path(path).relative_to(Path(vault)).as_posix()
    return rel == SNAPSHOT_ROOT or rel.startswith(SNAPSHOT_ROOT + "/")


def link_targets(vault):
    """Every markdown file a wikilink could name: the whole tree, minus the recorded bases."""
    return sorted(p for p in iter_markdown(vault) if not in_recorded_base(p, vault))


def build_index(targets, vault):
    """{(stem lower): [paths]} and {(rel posix lower): path} for every markdown target.

    The stem map keeps *every* file that shares a stem instead of collapsing to the first
    (the old dict's silent behaviour), because the collision list is exactly what makes an
    edge ambiguous rather than extracted.
    """
    stem_to_files = {}
    rel_to_file = {}
    for path in targets:
        stem_to_files.setdefault(path.stem.lower(), []).append(path)
        rel_to_file[path.relative_to(vault).as_posix().lower()] = path
    return stem_to_files, rel_to_file


def resolve_link(target, vault, stem_to_files, rel_to_file):
    """Classify one wikilink text into (label, reason, resolved path or None).

    Resolution order, and the label each outcome earns. A wikilink names a note by its stem,
    so the stem is tried first (it is what `[[Name]]` means); a text containing a slash or a
    `.md` suffix is read as a path only when no single file carries that stem.

      1. a bare stem: extracted when it literally equals the *one* file's stem, inferred when
         case-folding reached the one file, ambiguous when several files share it (the author's
         text cannot say which they meant);
      2. a path (slashes, or a `.md` suffix): a path is unique, so it names the target —
         extracted when the characters match the file exactly, inferred when normalising
         (case, slash, appended `.md`) did the matching;
      3. any resolved target under `14_CANDIDATES/` is ambiguous regardless of how it was
         reached — it is a row waiting on a human, not a settled edge;
      4. nothing matches — `broken` (the link is missing, not uncertain).
    """
    target = target.strip()
    if not target:
        return "broken", "empty link", None

    candidates = stem_to_files.get(target.lower())
    if candidates:
        if len(candidates) > 1:
            named = ", ".join(sorted(p.relative_to(vault).as_posix() for p in candidates))
            return "ambiguous", ("colliding stem %s matches %d files, which one the author "
                                 "meant is unreadable from the link: %s" % (target.lower(),
                                                                            len(candidates),
                                                                            named)), None
        path = candidates[0]
        if target == path.stem:
            return _finalise("extracted", "author named a stem that is unique: %s" % path.stem,
                             path, vault)
        return _finalise("inferred", "stem case-folded %s -> %s" % (target, path.stem),
                         path, vault)

    posix = target.replace("\\", "/")
    lowered = posix.lower()
    key = lowered if lowered.endswith(".md") else lowered + ".md"
    if key in rel_to_file:
        path = rel_to_file[key]
        rel = path.relative_to(vault).as_posix()
        if target == rel:
            return _finalise("extracted", "author named the exact path %s" % rel, path, vault)
        return _finalise("inferred", "path normalised %s -> %s" % (target, rel), path, vault)

    return "broken", "no file matches [[%s]]" % target, None


def _finalise(label, reason, path, vault):
    """A resolved target under `14_CANDIDATES/` is a human-pending row, never a healthy edge."""
    rel = path.relative_to(vault).as_posix()
    if rel.startswith("14_CANDIDATES/"):
        return "ambiguous", "target is a candidate row awaiting a verdict: %s" % rel, path
    return label, reason, path


def classify_links(vault):
    """Every wikilink in the vault's notes, as (edges, broken).

    `edges` holds every link that resolved to something — `extracted`, `inferred` or
    `ambiguous`; `broken` holds the missing ones as (source, target) pairs, exactly the shape
    the gate has always reported. Ambiguous edges are returned (so they can be named), but the
    graph readout deliberately does not treat them as navigable.

    A note can be a link source or a link target, and the two questions have different answers:
    the sources are the author's notes (`iter_notes`, prose excluded), while the targets are every
    file a link could name — except the copies made by `scripts/base.py --save`, which a recorded
    known-good base is full of. See `link_targets`.
    """
    vault = Path(vault)
    targets = link_targets(vault)
    stem_to_files, rel_to_file = build_index(targets, vault)
    edges = []
    broken = []
    for path in iter_notes(vault):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in WIKILINK_RE.finditer(text):
            target = match.group(1).split("|")[0].strip()
            label, reason, resolved = resolve_link(target, vault, stem_to_files, rel_to_file)
            if label == "broken":
                broken.append((path, target))
            else:
                edges.append(Edge(path, target, label, reason, resolved))
    return edges, broken


def check_vault(vault):
    """The link gate this module has always exported: the list of broken (source, target)."""
    _edges, broken = classify_links(vault)
    return broken


def graph_from_edges(edges, vault):
    """Undirected adjacency over the *notes* — only resolved, non-ambiguous links count.

    An ambiguous edge is escalated, not silently kept in the graph (graphify's law), so it is
    excluded here; a degree/bridge computed through a guessed or human-pending link would dress
    an uncertain relation up as structure. Self-links (a note that points at itself) add no
    navigation, so they are dropped too.
    """
    notes = list(iter_notes(vault))
    note_set = set(notes)
    adj = {note: set() for note in notes}
    for edge in edges:
        if edge.label not in ("extracted", "inferred"):
            continue
        target = edge.path
        if target is None or target not in note_set or target == edge.source:
            continue
        adj[edge.source].add(target)
        adj[target].add(edge.source)
    return adj


def connected_component_count(adj):
    """How many islands of linked notes there are (isolated notes count as islands of one)."""
    seen = set()
    count = 0
    for node in adj:
        if node in seen:
            continue
        count += 1
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adj[cur] - seen)
    return count


def degree_zero(adj):
    """Notes no wikilink touches in either direction — arrival-by-links is impossible.

    This is the corrected reading of the ROADMAP row: it is a *navigation* defect (a reader or
    agent following links cannot get here), not a retrieval one (kb.py's FTS5 still returns it).
    """
    return sorted(node for node in adj if not adj[node])


def edge_pairs(adj):
    """Each undirected edge once, as an ordered (a, b) pair of paths."""
    pairs = set()
    for source, targets in adj.items():
        for target in targets:
            pairs.add((source, target) if source < target else (target, source))
    return sorted(pairs)


def find_bridges(adj):
    """Cut edges — the single links whose removal splits a component into two.

    Found the plain way the row demands: for each edge, delete it, recount components with a
    BFS, and put it back. If the count rises, that link was the only thing joining two
    otherwise separate clusters. No graph library, no Leiden.
    """
    base = connected_component_count(adj)
    bridges = []
    for left, right in edge_pairs(adj):
        adj[left].discard(right)
        adj[right].discard(left)
        if connected_component_count(adj) > base:
            bridges.append((left, right))
        adj[left].add(right)
        adj[right].add(left)
    return bridges


def god_nodes(adj):
    """The most-connected note(s): the vault's hubs, the degree signal behind god-node ranking."""
    degrees = {node: len(adj[node]) for node in adj}
    top = max(degrees.values()) if degrees else 0
    return top, sorted(node for node in adj if degrees[node] == top and top > 0)


def graph_readout(root):
    """The link-graph readout `health.py` imports: degree-0 notes, bridge notes, god nodes.

    Returns a dict that names the file behind every measurement — the notes it scanned, the
    edges per label, and each degree-0 / bridge / god-node path — so an empty result always
    says *what it looked at* and an invisible file cannot masquerade as health. Ambiguous
    edges are carried out for escalation, never folded into the structure.
    """
    root = Path(root)
    edges, broken = classify_links(root)
    counts = dict((label, 0) for label in LABELS)
    for edge in edges:
        counts[edge.label] += 1
    adj = graph_from_edges(edges, root)
    bridges = find_bridges(adj)
    bridge_notes = sorted(set(node for pair in bridges for node in pair))
    top, gods = god_nodes(adj)
    return {
        "root": root,
        "notes_scanned": sorted(n.relative_to(root).as_posix() for n in adj),
        "label_counts": counts,
        "broken": sorted((s.relative_to(root).as_posix(), t) for s, t in broken),
        "ambiguous": [e for e in edges if e.label == "ambiguous"],
        "components": connected_component_count(adj),
        "degree0": sorted(n.relative_to(root).as_posix() for n in degree_zero(adj)),
        "bridges": sorted((a.relative_to(root).as_posix(), b.relative_to(root).as_posix())
                          for a, b in bridges),
        "bridge_notes": [n.relative_to(root).as_posix() for n in bridge_notes],
        "god_degree": top,
        "god_nodes": [n.relative_to(root).as_posix() for n in gods],
    }


def print_confidence(vault):
    """Report mode: measured counts per label, then every ambiguous edge by name."""
    edges, _broken = classify_links(vault)
    counts = dict((label, 0) for label in LABELS)
    for edge in edges:
        counts[edge.label] += 1
    print("edge confidence over %s" % vault)
    print("  %d edge(s) classified from %d wikilink(s)" % (len(edges), len(edges)))
    for label in LABELS:
        print("  %-10s %d" % (label, counts[label]))
    ambiguous = [e for e in edges if e.label == "ambiguous"]
    if ambiguous:
        print("ESCALATED — ambiguous edge(s), named for a human; not counted as healthy:")
        for edge in ambiguous:
            src = edge.source.relative_to(Path(vault)).as_posix()
            dst = edge.path.relative_to(Path(vault)).as_posix() if edge.path else "(no one target)"
            print("  AMBIGUOUS  %s -> [[%s]]  (target: %s)" % (src, edge.target, dst))
            print("             reason: %s" % edge.reason)
    else:
        print("no ambiguous edge — every link names one settled target (nothing escalated).")
    return counts


def print_readout(vault):
    """Report mode: the navigation structure, each line naming the file it judged."""
    data = graph_readout(vault)
    root = data["root"]
    print("link-graph readout over %s" % root)
    print("  notes scanned: %d (every note iter_notes found; this denominator is the proof "
          "the pass was not silence)" % len(data["notes_scanned"]))
    counts = data["label_counts"]
    print("  edges: %d extracted, %d inferred, %d ambiguous, %d broken"
          % (counts["extracted"], counts["inferred"], counts["ambiguous"], len(data["broken"])))
    print("  connected components (islands of linked notes): %d" % data["components"])
    print("  god-node: max degree %d — %d hub note(s)" % (data["god_degree"],
                                                          len(data["god_nodes"])))
    for name in data["god_nodes"]:
        print("    HUB  %s" % name)
    print("  degree-0 notes: %d — no wikilink reaches these; unreadable by following links, "
          "though kb.py full-text search still returns them" % len(data["degree0"]))
    for name in data["degree0"]:
        print("    ISOLATED  %s" % name)
    print("  bridge notes: %d — notes touched by a single link that joins two clusters"
          % len(data["bridge_notes"]))
    for left, right in data["bridges"]:
        print("    BRIDGE  %s <-> %s" % (left, right))
    if data["ambiguous"]:
        print("  escalated (ambiguous, excluded from the structure):")
        for edge in data["ambiguous"]:
            print("    %s -> [[%s]]" % (edge.source.relative_to(root).as_posix(), edge.target))
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None, help="vault dir (default: repo's vault-template)")
    parser.add_argument("--confidence", action="store_true",
                        help="print edge-label counts and name every ambiguous edge")
    parser.add_argument("--readout", action="store_true",
                        help="print the link-graph readout (degree-0, bridges, god nodes) and "
                             "refuse while an ambiguous edge is escalated")
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault = Path(args.vault) if args.vault else root / "vault-template"

    if args.confidence:
        print_confidence(vault)
        return 0

    # one pass over the notes: the broken list and the graph shape are the same measurement,
    # and a gate that scanned the vault twice could print two different answers
    data = graph_readout(vault)
    if args.readout:
        print_readout(vault)
        if data["ambiguous"]:
            print("REFUSED — %d ambiguous edge(s) escalated: the readout will not call a graph "
                  "it cannot settle healthy" % len(data["ambiguous"]))
            return 1
        print("OK — link graph measured over %s: %d note(s), %d component(s), %d degree-0, "
              "%d bridge note(s), 0 ambiguous"
              % (vault, len(data["notes_scanned"]), data["components"], len(data["degree0"]),
                 len(data["bridge_notes"])))
        return 0

    broken = data["broken"]
    if broken:
        for path, target in broken:
            print("BROKEN  %s: [[%s]]" % (path, target))
        print("\n%d broken link(s) — fix before anything else ships." % len(broken))
        return 1
    counts = data["label_counts"]
    print("OK — 0 broken links in %s" % vault)
    # the shape of the graph rides with the verdict, so `health.py` shows what a green link
    # gate does *not* claim: an isolated note is still findable by search, just not by links
    print("  graph: %d note(s), %d extracted, %d inferred, %d component(s), %d degree-0, "
          "%d bridge note(s), %d ambiguous"
          % (len(data["notes_scanned"]), counts["extracted"], counts["inferred"],
             data["components"], len(data["degree0"]), len(data["bridge_notes"]),
             counts["ambiguous"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
