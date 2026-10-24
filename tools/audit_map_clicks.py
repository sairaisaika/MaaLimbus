"""Which kind of detected box does a map click actually take?

`map_clicks` returns nine kinds of box; the loop clicks the first of them and the map
refuses.  The archive can answer "which kind lands" only if the verdict names the kind,
which is what D75 wired.  Exit 0 when the table is measured and nothing was sent in
vain, 2 when there is nothing to read.
"""

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import run_metrics  # noqa: E402


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = None
    if '--root' in argv:
        root = pathlib.Path(argv[argv.index('--root') + 1])
    # An explicit root is the corpus.  Falling back to the default archive when the
    # named root has no journal would answer a question nobody asked about a corpus
    # nobody named -- and an audit that prints 388 real clicks for an empty directory
    # is exactly the "silently measured the wrong thing" defect this series is about.
    directories = None
    if root is not None:
        if (root / 'events.jsonl').exists():
            directories = [root]
        else:
            directories = sorted(path.parent
                                 for path in root.glob('packaged-mirror-*/events.jsonl'))
    kinds = run_metrics.click_kinds(directories)
    report = run_metrics.click_kind_report(kinds)
    if not kinds['sent']:
        print('nothing to read: no map_click_result row in this corpus')
        return 2
    print('click verdicts: %d' % kinds['sent'])
    print('%-22s %5s %8s %8s %11s %6s' % ('kind', 'sent', 'accepted', 'rejected',
                                          'superseded', 'rate'))
    for row in report['rows']:
        print('%-22s %5d %8d %8d %11d %6s' % (
            row['kind'], row['sent'], row['accepted'], row['rejected'],
            row['superseded'], 'n/a' if row['rate'] is None else '%.2f' % row['rate']))
    print('basis: %s' % report['basis'])
    if report['note']:
        print('note: %s' % report['note'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
