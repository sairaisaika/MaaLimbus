"""Label the recorded shop purchases from the runs' own later observations, then train.

Usage:
    python tools/shop_value_review.py [--review-only] [--json]

The label of a purchase is the return the same journey observed *after* it (floor clears,
rewards, victories) — already hash-bound to that scope by the run ledger.  Nothing here
invents a benefit: a folder with no bound later observation stays pending and is counted.
The trainer then decides, from its own held-out ordering, whether the candidate may
reorder the offers the gift plan already approved or must stay a shadow.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import shop_value_training as training  # noqa: E402

# Where the frozen application loads its candidate from.  Installing is a copy of the two
# facts the runtime re-verifies on every load (weights.json and modelcard.json), never a
# silent promotion: the modelcard carries the participation the trainer decided.
RUNTIME_ROOT = Path('assets/resource/base/model/shop-value')


def install(artefact, root):
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for key, name in (('weights', 'weights.json'), ('modelcard', 'modelcard.json')):
        source = Path(artefact[key])
        target = root / name
        target.write_bytes(source.read_bytes())
        written.append(str(target))
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', default=str(ROOT / training.DEFAULT_SAMPLES))
    parser.add_argument('--catalog', default=str(ROOT / training.DEFAULT_CATALOG))
    parser.add_argument('--ledger', default=str(ROOT / training.DEFAULT_LEDGER))
    parser.add_argument('--out', default=str(ROOT / training.DEFAULT_OUT))
    parser.add_argument('--epochs', type=int, default=400)
    parser.add_argument('--hidden', type=int, default=8)
    parser.add_argument('--min-episodes', type=int, default=1)
    parser.add_argument('--review-only', action='store_true')
    parser.add_argument('--install', action='store_true',
                        help='copy the trained candidate into the runtime model root')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    samples = Path(args.samples)
    reviewed = skipped = 0
    problems = {}
    folders = sorted(path for path in samples.iterdir() if path.is_dir()) if samples.is_dir() else []
    for folder in folders:
        derived, problem = training.review_sample(folder)
        if derived is None:
            skipped += 1
            problems[problem] = problems.get(problem, 0) + 1
        else:
            reviewed += 1
    report = dict(kind='shop_value_review', samples_root=str(samples), folders=len(folders),
                  reviewed=reviewed, skipped=skipped, skip_reasons=problems, label_source=training.OBJECTIVE_LABEL_SOURCE)
    if not args.review_only:
        report['training'] = training.train_and_export(samples, args.catalog, args.out,
                                                       ledger=args.ledger, hidden=args.hidden,
                                                       epochs=args.epochs,
                                                       min_episodes=args.min_episodes)
        if args.install and report['training'].get('trained'):
            report['installed'] = install(report['training']['artefact'], ROOT / RUNTIME_ROOT)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    print('以运行自身的后续观测标注：%d 个样本已核，%d 个仍待核（共 %d 个目录）'
          % (reviewed, skipped, len(folders)))
    for reason, count in sorted(problems.items()):
        print('  待核原因 %s：%d' % (reason, count))
    attempt = report.get('training')
    if attempt is None:
        return 0
    print('已核样本：%d 局 / %d 行；训练=%s' % (attempt['reviewed_episodes'], attempt['reviewed_rows'],
                                       '是' if attempt['trained'] else '否'))
    if attempt['trained']:
        held = attempt['held_out'] or {}
        accuracy = held.get('pairwise_accuracy')
        print('  参与方式=%s（留出 %d 对，准确率=%s）' % (attempt['participation'], held.get('pairs') or 0,
                                              '未知' if accuracy is None else '%.2f' % accuracy))
        print('  留出账本=%s' % (held.get('held_out_scopes') or []))
        print('  产物=%s' % attempt['artefact']['modelcard'])
        if report.get('installed'):
            print('  已安装到运行目录=%s' % report['installed'])
    else:
        print('  未训练原因=%s' % attempt.get('reason'))
        for blocker in attempt['blockers']:
            print('  阻塞=%s' % blocker)
    if attempt['exclusion_reasons']:
        print('  排除原因=%s' % json.dumps(attempt['exclusion_reasons'], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
