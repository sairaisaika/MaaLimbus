"""Drop the purchase records a shop decision context used to embed.

A purchase's decision context records what the run had already bought so the value model
can see it.  It used to record the whole purchase records, and every record carries its
own decision context, so each purchase embedded the previous ones: ``config/user-shop-
<scope>.json`` reached 2,464,332 bytes after seven purchases and the next live run could
not start at all -- ``MaaLimbus`` raised ``Configuration/state exceeds 2 MiB`` while
reading its own shop store (live ``pi-20261014-082856``, 0 steps, ``mirror_loop_error``).

``src/maalimbus/runner.py`` now stores the names.  This tool rewrites the state a previous
version left behind: it replaces ``owned_bought`` with the names it held and touches
nothing else.  It is idempotent, refuses a shape it does not recognise, and reports the
size it removed.

    python tools/prune_shop_state.py --dry-run
    python tools/prune_shop_state.py
    python tools/prune_shop_state.py --path config/user-shop-<scope>.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.storage import read_json, write_json  # noqa: E402


def _names(value):
    """The names a context field held, or None when it is a shape this tool must not touch."""
    if value is None:
        return None, False
    if not isinstance(value, list):
        return None, False
    names = []
    for row in value:
        if isinstance(row, str):
            names.append(row)
        elif isinstance(row, dict) and isinstance(row.get('name'), str) and row['name']:
            names.append(row['name'])
        else:
            return None, False
    return names, any(isinstance(row, dict) for row in value)


def prune_context(context):
    """Return (context, changed) with ``owned_bought`` reduced to names."""
    if not isinstance(context, dict):
        return context, False
    names, changed = _names(context.get('owned_bought'))
    if not changed:
        return context, False
    out = dict(context)
    out['owned_bought'] = names
    return out, True


def prune_store(data):
    """Return (store, changed_fields) with every nested decision context reduced."""
    if not isinstance(data, dict):
        raise ValueError('Shop state is not a JSON object')
    out = copy.deepcopy(data)
    changed = 0
    rows = out.get('bought')
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                context, done = prune_context(row.get('decision_context'))
                if done:
                    row['decision_context'] = context
                    changed += 1
    pending = out.get('pending')
    if isinstance(pending, dict):
        context, done = prune_context(pending.get('decision_context'))
        if done:
            pending['decision_context'] = context
            changed += 1
    return out, changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--root', default=str(ROOT), help='repository root (default: %(default)s)')
    parser.add_argument('--path', action='append', default=None,
                        help='one state file; default: every config/user-shop-*.json')
    parser.add_argument('--dry-run', action='store_true', help='report without writing')
    args = parser.parse_args(argv)
    root = Path(args.root)
    paths = [Path(p) for p in args.path] if args.path else sorted((root / 'config').glob('user-shop-*.json'))
    if not paths:
        print('no shop state files under %s' % (root / 'config'))
        return 0
    for path in paths:
        before = path.stat().st_size
        data = read_json(path, limit=64 * 1024 * 1024)
        pruned, changed = prune_store(data)
        after = len(json.dumps(pruned, ensure_ascii=False).encode('utf-8')) if changed else before
        line = '%s: %d -> %d bytes, %d context(s)' % (path, before, after, changed)
        if changed and not args.dry_run:
            write_json(path, pruned)
        print(line + (' [dry-run]' if args.dry_run else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
