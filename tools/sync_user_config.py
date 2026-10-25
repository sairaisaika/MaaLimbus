"""Copy user preferences from the checkout into an installed tree, and say what moved.

The packaged agent resolves ``data_directory`` from its own root, so a preference
edited in the checkout never reaches a packaged run (D282).  This tool reports the
difference and copies only the preference files ``runtime_paths.CONFIG_FILES``
names: ledgers, transactions and journals stay where they are.

    python tools/sync_user_config.py                      # config -> dist copy
    python tools/sync_user_config.py --dry-run            # report only
    python tools/sync_user_config.py --target <dir>
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.runtime_paths import CONFIG_FILES, apply_sync, plan_sync  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=str(ROOT / 'config'))
    parser.add_argument('--target', default=str(ROOT / 'dist' / 'MaaLimbus' / 'config'))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    rows = plan_sync(args.source, args.target) if args.dry_run else apply_sync(args.source, args.target)
    for row in rows:
        print(f"{row['action']:>7}  {row['name']}")
    copied = sum(1 for row in rows if row['action'] == 'copied')
    print(f"source {args.source}")
    print(f"target {args.target}")
    print(f"copied {copied} of {len(CONFIG_FILES)} preference file(s)"
          + (' (dry run)' if args.dry_run else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
