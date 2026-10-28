#!/usr/bin/env python
"""Plan or explicitly apply an approved local skill installation."""
import argparse
import json
from pathlib import Path
from backend import install_skill


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan')
    plan.add_argument('--skill-id', required=True)
    plan.add_argument('--harness-id', required=True)
    plan.add_argument('--destination', type=Path, required=True)
    apply = sub.add_parser('apply')
    apply.add_argument('plan', type=Path)
    apply.add_argument('--approve', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            result = install_skill.plan(args.root, args.skill_id, args.harness_id, args.destination)
        else:
            result = install_skill.apply(args.root, json.loads(args.plan.read_text(encoding='utf-8')), args.approve)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, 'ERROR: %s\n' % exc)


if __name__ == '__main__':
    raise SystemExit(main())
