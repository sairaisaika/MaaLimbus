"""Where the seconds go: the whole run's time, split by the line that owned it.

`mean_seconds` says a run took 276.6 s and nothing said which line cost it. Every journal
row carries its own `utc`, so the gap from a row to the next stamped row is the time that
row cost; D66 folded those gaps into groups, and D68 added the second half -- each
observation writer now says how long the read itself took, so the reads group can be split
into the node's own work and the loop around it.

Exit 0 when there is a corpus, 2 when nothing was read. `--json` prints the whole report.
"""
import json
import pathlib
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    json_out = '--json' in args
    root = None
    if '--root' in args:
        root = pathlib.Path(args[args.index('--root') + 1])

    here = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(here / 'src'))
    from maalimbus import run_metrics

    directories = None
    if root is not None:
        directories = sorted(path.parent for path in root.glob('*/events.jsonl'))
    report_of = run_metrics.portfolio(directories)
    if not report_of['runs']:
        print('no run wrote a journal under evidence/runtime')
        return 2
    report = report_of['time']
    if json_out:
        print(json.dumps(report_of, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    value = report['value']
    print(f'runs read: {len(report_of["runs"])}')
    if value is None:
        print(f'time budget: not measured -- {report["note"]}')
        return 0
    print(f'attributed seconds: {value["attributed_seconds"]:.0f} '
          f'of {value["total_seconds"]:.0f} in total')
    print('')
    for group, entry in value['groups'].items():
        share = '   n/a' if entry['share'] is None else f'{entry["share"]:6.1%}'
        print(f'{group:<9} {entry["seconds"]:8.0f} s {share}  n={entry["n"]}')
    print('')
    print('the lines that own the time:')
    for event, entry in value['per_event'].items():
        share = '   n/a' if entry['share'] is None else f'{entry["share"]:6.1%}'
        print(f'  {event:<26} {entry["seconds"]:8.0f} s {share}  '
              f'n={entry["n"]:<6} {entry["mean"]:.2f} s each  [{entry["group"]}]')
    print('')
    print(f'basis: {report["basis"]}')
    reads = report_of.get('reads') or {}
    split = report_of.get('split') or {}
    print('')
    print(f'reads that say how long they took: {reads.get("basis")}')
    if reads.get('value'):
        measured = reads['value']
        print(f'  node time: {measured["seconds"]:.0f} s over {measured["measured"]} '
              f'read(s), mean {measured["mean"]:.2f} s')
        for event, entry in measured['by_event'].items():
            print(f'  {event:<26} {entry["seconds"]:8.0f} s  n={entry["n"]:<6} '
                  f'mean {entry["mean"]:.2f} s')
        phases = measured.get('phases') or {}
        if phases.get('measured'):
            mean = phases['mean']
            print(f'  of which, per read: full-frame OCR {mean["ocr_seconds"]:.2f} s, '
                  f'ROI re-reads {mean["roi_seconds"]:.2f} s, '
                  f'classification {mean["classify_seconds"]:.2f} s '
                  f'({phases["measured"]} read(s) split their own time)')
        else:
            print('  the split is not measured: no read carries ocr_seconds/roi_seconds/'
                  'classify_seconds, because the writers that record them are newer (D70)')
    else:
        print(f'  not measured -- {reads.get("note")}')
    print('')
    print(f'node versus wrapper: {split.get("basis")}')
    if split.get('value'):
        measured = split['value']
        print(f'  the node itself: {measured["node_seconds"]:.0f} s '
              f'({measured["node_mean"]:.2f} s per read)')
        print(f'  the reads group: {measured["reads_group_seconds"]:.0f} s')
        print(f'  everything else: {measured["overhead_seconds"]:.0f} s')
    else:
        print(f'  not measured -- {split.get("note")}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
