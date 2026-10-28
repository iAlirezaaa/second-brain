#!/usr/bin/env python
"""Inspect registered capabilities and propose candidates without installing them."""
import argparse
import json
from pathlib import Path
from backend import capabilities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--harness-id', default='')
    parser.add_argument('--task', default='')
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    try:
        result = (capabilities.suggest(args.root, args.task, args.harness_id, args.limit)
                  if args.task else capabilities.inventory(args.root, args.harness_id))
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, 'ERROR: %s\n' % exc)


if __name__ == '__main__':
    raise SystemExit(main())
