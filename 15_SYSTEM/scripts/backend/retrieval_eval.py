"""Measure retrieval on an explicitly supplied, independently curated query set.

`run` and `compare` measure; `claim` publishes. A published improvement is only an
IMPROVEMENT when every repeat improved both mean recall and MRR by at least a positive
margin on the same cases and corpus, and when `scripts/base.py --save` recorded the state
the change started from -- the report then carries the exact `--recover` line that undoes
it. NO_IMPROVEMENT and REGRESSION are honest verdicts, never a bare "better"; a claim
without a measured baseline and a way back is refused outright.
"""
import hashlib
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from . import sources

# the journal `scripts/base.py --save` appends to; read here, never written here --
# recording a base is the owner's act behind the health gates, measuring one is not
BASES_JOURNAL = Path('14_CANDIDATES') / 'loop' / 'bases.jsonl'
CLAIM_NOTE = 'undo the change measured by compare-benchmarks --claim'


def _hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _corpus_hash(root):
    index = Path(root) / sources.DATA / 'index.sqlite'
    if not index.is_file():
        raise ValueError('index missing; run rebuild first')
    with closing(sqlite3.connect(str(index))) as db:
        rows = db.execute('SELECT id, kind, origin, filename, imported_at, body FROM sources ORDER BY id').fetchall()
    return _hash(rows)


def run(root, cases, limit=10):
    if not isinstance(cases, list) or not cases or not 1 <= limit <= 100:
        raise ValueError('a nonempty list of cases and a limit from 1 to 100 are required')
    corpus = _corpus_hash(root)
    results = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('query'), str) or not case['query'].strip():
            raise ValueError('each case needs a nonempty query')
        expected = case.get('expected_ids')
        if not isinstance(expected, list) or not expected or not all(
                isinstance(item, str) and len(item) == 64 and all(c in '0123456789abcdef' for c in item)
                for item in expected):
            raise ValueError('each case needs nonempty expected source IDs')
        expected = set(expected)
        hits = sources.search(root, case['query'], limit)
        ids = [hit['id'] for hit in hits]
        matching = expected.intersection(ids)
        ranks = [rank for rank, identity in enumerate(ids, 1) if identity in expected]
        results.append({'query': case['query'], 'expected_ids': sorted(expected), 'retrieved_ids': ids,
                        'recall': len(matching) / len(expected),
                        'reciprocal_rank': 1.0 / min(ranks) if ranks else 0.0})
    canonical_cases = [{'query': row['query'], 'expected_ids': row['expected_ids']} for row in results]
    if _corpus_hash(root) != corpus:
        raise ValueError('indexed corpus changed during benchmark')
    return {'version': 1, 'cases': len(results), 'limit': limit,
            'case_set_sha256': _hash(canonical_cases), 'corpus_sha256': corpus,
            'mean_recall': sum(row['recall'] for row in results) / len(results),
            'mean_reciprocal_rank': sum(row['reciprocal_rank'] for row in results) / len(results),
            'results': results}


def compare(baseline, candidate):
    """Compare only reports generated from identical cases, limits and indexed corpus."""
    for report in (baseline, candidate):
        if not isinstance(report, dict) or report.get('version') != 1:
            raise ValueError('unsupported benchmark report')
        rows = report.get('results')
        if not isinstance(rows, list) or not rows or report.get('cases') != len(rows):
            raise ValueError('invalid benchmark results')
        try:
            canonical = [{'query': row['query'], 'expected_ids': row['expected_ids']} for row in rows]
            for row in rows:
                expected = set(row['expected_ids'])
                ids = row['retrieved_ids']
                if not expected or not isinstance(ids, list) or len(ids) != len(set(ids)):
                    raise ValueError('invalid benchmark case')
                if not all(isinstance(row[key], (int, float)) and not isinstance(row[key], bool)
                           and math.isfinite(row[key]) for key in ('recall', 'reciprocal_rank')):
                    raise ValueError('invalid benchmark metrics')
                ranks = [rank for rank, identity in enumerate(ids, 1) if identity in expected]
                if (abs(row['recall'] - len(expected.intersection(ids)) / len(expected)) > 1e-12 or
                        abs(row['reciprocal_rank'] - (1.0 / min(ranks) if ranks else 0.0)) > 1e-12):
                    raise ValueError('benchmark case metrics are inconsistent')
            recall = sum(row['recall'] for row in rows) / len(rows)
            rank = sum(row['reciprocal_rank'] for row in rows) / len(rows)
            if not all(isinstance(report[key], (int, float)) and not isinstance(report[key], bool)
                       and math.isfinite(report[key]) for key in ('mean_recall', 'mean_reciprocal_rank')):
                raise ValueError('invalid benchmark aggregate metrics')
            if (abs(recall - report['mean_recall']) > 1e-12 or
                    abs(rank - report['mean_reciprocal_rank']) > 1e-12):
                raise ValueError('benchmark aggregate metrics are inconsistent')
        except (KeyError, TypeError) as exc:
            raise ValueError('invalid benchmark results') from exc
        if _hash(canonical) != report.get('case_set_sha256'):
            raise ValueError('benchmark report is inconsistent')
    for field in ('case_set_sha256', 'corpus_sha256', 'limit'):
        if not baseline.get(field) or baseline.get(field) != candidate.get(field):
            raise ValueError('benchmark reports differ in %s' % field)
    delta_recall = candidate['mean_recall'] - baseline['mean_recall']
    delta_rank = candidate['mean_reciprocal_rank'] - baseline['mean_reciprocal_rank']
    verdict = ('regressed' if delta_recall < 0 or delta_rank < 0 else
               'improved' if delta_recall > 0 or delta_rank > 0 else 'unchanged')
    return {'verdict': verdict, 'delta_mean_recall': delta_recall,
            'delta_mean_reciprocal_rank': delta_rank,
            'case_set_sha256': baseline['case_set_sha256'], 'corpus_sha256': baseline['corpus_sha256'],
            'note': 'Retrieval metrics only; this does not approve or apply a system change.'}


def known_good_base(root):
    """The newest recorded base {stamp, fingerprint} from base.py's journal, or None.

    A base exists only if `scripts/base.py --save` ran while every health gate was green;
    this reads that record, it cannot make one.
    """
    path = Path(root) / BASES_JOURNAL
    if not path.is_file():
        return None
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get('stamp') and row.get('fingerprint'):
            rows.append(row)
    if not rows:
        return None
    return {'stamp': str(rows[-1]['stamp']), 'fingerprint': str(rows[-1]['fingerprint'])}


def recover_command(stamp, note=CLAIM_NOTE):
    """The exact line that undoes the change this verdict measured, back to base `stamp`."""
    return 'python scripts/base.py --recover --stamp %s --note "%s"' % (stamp, note)


def claim(baselines, candidates, margin, base):
    """Publish or refuse an improvement: repeats, a positive margin, and a way back or nothing.

    Every pair is compared with the full rigour of `compare` (shared case set, limit and
    corpus hash; inconsistent reports raise). On top of that:
      * REGRESSION -- any repeat lost recall or MRR; failing the comparison is the point;
      * NO_IMPROVEMENT -- no loss, but some repeat gained nothing or the gain did not clear
        the margin in every repeat, so it was one lucky run, not a repeatable result;
      * IMPROVEMENT -- every repeat improved both metrics and every gain is at least the
        margin, and only publishable when `base` is the state `scripts/base.py --save`
        recorded, so the report carries the exact `--recover` line that undoes the change.
    A claim with no saved base is refused before any verdict is printed.
    """
    if (not isinstance(baselines, list) or not baselines or not isinstance(candidates, list)
            or len(candidates) != len(baselines)):
        raise ValueError('a claim needs an equal, nonempty number of baseline and candidate reports (the repeats)')
    if (isinstance(margin, bool) or not isinstance(margin, (int, float))
            or not math.isfinite(margin) or margin <= 0):
        raise ValueError('a claim needs a positive margin (a finite number above 0): '
                         'a bare "better" is one lucky run wearing a verdict')
    if not isinstance(base, dict) or not base.get('stamp') or not base.get('fingerprint'):
        raise ValueError('REFUSED: no known-good base is recorded, so this change has no measured '
                         'baseline and no way back -- run python scripts/base.py --save while every '
                         'health gate is green, then re-run the claim')
    comparisons = []
    for index in range(len(baselines)):
        comparisons.append(compare(baselines[index], candidates[index]))
    fingerprints = {(report['case_set_sha256'], report['corpus_sha256'], report['limit'])
                    for report in baselines + candidates}
    if len(fingerprints) != 1:
        raise ValueError('the repeats do not measure one case set, limit and corpus; '
                         'comparing runs across worlds is not a claim')
    deltas_recall = [row['delta_mean_recall'] for row in comparisons]
    deltas_rank = [row['delta_mean_reciprocal_rank'] for row in comparisons]
    if any(delta < 0 for delta in deltas_recall + deltas_rank):
        verdict = 'REGRESSION'
    elif (all(delta > 0 for delta in deltas_recall + deltas_rank)
          and min(deltas_recall) >= margin and min(deltas_rank) >= margin):
        verdict = 'IMPROVEMENT'
    else:
        verdict = 'NO_IMPROVEMENT'
    return {'version': 1, 'verdict': verdict, 'margin': margin, 'repeats': len(comparisons),
            'mean_delta_mean_recall': sum(deltas_recall) / len(deltas_recall),
            'mean_delta_mean_reciprocal_rank': sum(deltas_rank) / len(deltas_rank),
            'min_delta_mean_recall': min(deltas_recall),
            'min_delta_mean_reciprocal_rank': min(deltas_rank),
            'case_set_sha256': baselines[0]['case_set_sha256'],
            'corpus_sha256': baselines[0]['corpus_sha256'], 'limit': baselines[0]['limit'],
            'base': base, 'recover': recover_command(base['stamp']),
            'reports': {'baseline': baselines, 'candidate': candidates},
            'comparisons': comparisons,
            'note': 'Retrieval metrics only; IMPROVEMENT means every repeat cleared the margin '
                    'on this eval and the base it can be undone to is named. It never certifies '
                    'a model, a dataset or a system change.'}
