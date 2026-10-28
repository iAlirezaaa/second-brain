"""Measure retrieval on an explicitly supplied, independently curated query set."""
import hashlib
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path
from . import sources


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
