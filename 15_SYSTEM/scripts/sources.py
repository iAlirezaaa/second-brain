#!/usr/bin/env python
"""Import explicitly selected local sources and search the rebuildable local index."""
import argparse
import json
from pathlib import Path
from backend import sources, source_sync, learning, retrieval_eval, batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    add = sub.add_parser('import')
    add.add_argument('file', type=Path)
    add.add_argument('--kind', choices=sources.KINDS, required=True)
    add.add_argument('--origin', required=True, help='source URL or descriptive identifier')
    add.add_argument('--format', choices=sources.FORMATS, default='text')
    bulk = sub.add_parser('batch', help='preview or apply an explicit source manifest')
    bulk.add_argument('manifest', type=Path)
    bulk.add_argument('--apply', action='store_true')
    bulk.add_argument('--plan-id', default='')
    sub.add_parser('rebuild')
    find = sub.add_parser('search')
    find.add_argument('query')
    find.add_argument('--limit', type=int, default=10)
    sync = sub.add_parser('transfer', help='preview or copy source records between data directories')
    sync.add_argument('source', type=Path)
    sync.add_argument('destination', type=Path)
    sync.add_argument('--apply', action='store_true')
    sync.add_argument('--allow-conflicts', action='store_true')
    sync.add_argument('--include-approvals', action='store_true', help='trust and copy approval receipts')
    verify = sub.add_parser('verify-copy', help='verify sources and private learning in a copy')
    verify.add_argument('source', type=Path)
    verify.add_argument('destination', type=Path)
    proposal = sub.add_parser('propose', help='propose a lesson grounded in a source quote')
    proposal.add_argument('--source-id', required=True)
    proposal.add_argument('--quote', required=True)
    proposal.add_argument('--lesson', required=True)
    proposal.add_argument('--query', required=True)
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('id')
    approve = sub.add_parser('approve')
    approve.add_argument('id')
    approve.add_argument('--approve', action='store_true', help='explicitly approve this lesson')
    recall = sub.add_parser('recall')
    recall.add_argument('query')
    recall.add_argument('--limit', type=int, default=10)
    benchmark = sub.add_parser('benchmark', help='evaluate retrieval against labeled queries')
    benchmark.add_argument('cases', type=Path)
    benchmark.add_argument('--limit', type=int, default=10)
    compare = sub.add_parser('compare-benchmarks', help='compare reports with matching cases and corpus')
    compare.add_argument('baseline', type=Path)
    compare.add_argument('candidate', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'import':
            result = sources.ingest(args.root, args.file, args.kind, args.origin, args.format)
        elif args.command == 'batch':
            result = batch.run(args.root, args.manifest, args.apply, args.plan_id)
        elif args.command == 'rebuild':
            result = {'indexed': sources.rebuild(args.root)}
        elif args.command == 'search':
            result = sources.search(args.root, args.query, args.limit)
        elif args.command == 'transfer':
            result = source_sync.transfer(args.source, args.destination, args.apply, args.allow_conflicts,
                                          args.include_approvals)
        elif args.command == 'verify-copy':
            result = source_sync.verify_copy(args.source, args.destination)
        elif args.command == 'propose':
            result = learning.propose(args.root, args.source_id, args.quote, args.lesson, args.query)
        elif args.command == 'evaluate':
            result = learning.evaluate(args.root, args.id)
        elif args.command == 'approve':
            result = learning.approve(args.root, args.id, args.approve)
        elif args.command == 'recall':
            result = learning.recall(args.root, args.query, args.limit)
        elif args.command == 'benchmark':
            cases = json.loads(args.cases.read_text(encoding='utf-8'))
            result = retrieval_eval.run(args.root, cases, args.limit)
        else:
            baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
            candidate = json.loads(args.candidate.read_text(encoding='utf-8'))
            result = retrieval_eval.compare(baseline, candidate)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        failed = isinstance(result, dict) and bool(result.get('error'))
        return 1 if (args.command == 'verify-copy' and not result['verified']) or failed else 0
    except (OSError, ValueError, UnicodeError, KeyError) as exc:
        parser.exit(2, 'ERROR: %s\n' % exc)


if __name__ == '__main__':
    raise SystemExit(main())
