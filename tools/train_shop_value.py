"""Offline entry point for the shop-value scaffold: report readiness, then train.

This tool only reads reviewed sample folders and writes plain JSON.  It starts no
game, sends no input, installs nothing, and can never enable a policy: a candidate
it exports always carries ``production_enabled: false`` and runtime ranking stays
with whoever owns the runner.

    python tools/train_shop_value.py                      # readiness only
    python tools/train_shop_value.py --train              # train + export a candidate
    python tools/train_shop_value.py --synthetic          # exercise the trainer (no export)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import shop_value_training as training  # noqa: E402


def _dump(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def _modelcard(dataset, catalog, *, hidden, epochs, seed, metrics, synthetic, root, scope_list):
    # training_ready is derived from the dataset's own verification, never asserted here:
    # a card may only claim readiness when verify_episode_evidence verified the bytes.
    verification = dataset.get('verification') if isinstance(dataset.get('verification'), dict) else {}
    ready = bool(dataset.get('ready')) and verification.get('verified') is True
    return dict(
        training_ready=ready,
        synthetic=bool(synthetic),
        production_enabled=False,
        reviewed_episodes=len(scope_list),
        scopes=list(scope_list),
        dataset_root=str(root),
        samples_root=dataset.get('root'),
        rows=dataset.get('row_count'),
        vocabulary_size=len(training.gift_vocabulary(catalog)),
        keyword_vocabulary_size=len(training.keyword_vocabulary(catalog)),
        hidden=hidden,
        epochs=epochs,
        seed=seed,
        metrics=metrics,
        verification=verification,
        dataset_sha256=verification.get('dataset_sha256'),
        evidence_verified=verification.get('verified') is True,
        label_source=training.LABEL_SOURCE,
        prohibited_uses=[
            'ordering anything the purchase transaction has not already allowed and priced',
            'treating execution success as gift strength',
            'treating an unbought offer as a negative example',
            'raising the refresh cap, the reserve amount, or any spend',
        ],
        note='Candidate weights only; runtime ranking and promotion are not part of this tool.',
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description='Shop value scaffold: readiness, training, JSON export.')
    parser.add_argument('--samples', default=str(ROOT / training.DEFAULT_SAMPLES))
    parser.add_argument('--catalog', default=str(ROOT / training.DEFAULT_CATALOG))
    parser.add_argument('--ledger', default=str(ROOT / training.DEFAULT_LEDGER), help='run ledger that binds delayed evidence to a scope (always on)')
    parser.add_argument('--out', default=str(ROOT / training.DEFAULT_OUT))
    parser.add_argument('--report', default=None, help='write the readiness report to this JSON path')
    parser.add_argument('--train', action='store_true', help='fit and export a candidate when the data allows it')
    parser.add_argument('--synthetic', action='store_true', help='exercise the trainer on synthetic rows (never exportable)')
    parser.add_argument('--hidden', type=int, default=8)
    parser.add_argument('--epochs', type=int, default=400)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--test-fraction', type=float, default=0.3)
    args = parser.parse_args(argv)

    catalog = training.load_catalog(args.catalog)
    vocabulary = training.gift_vocabulary(catalog)
    keyword_vocabulary = training.keyword_vocabulary(catalog)
    report = training.readiness_report(args.samples, catalog, ledger=args.ledger)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(_dump(report) + '\n', encoding='utf-8')

    if args.synthetic:
        synthetic = training.synthetic_episodes(vocabulary, keyword_vocabulary, seed=args.seed)
        rows = [row for episode in synthetic for row in episode['rows']]
        fitted = training.fit(rows, hidden=args.hidden, epochs=args.epochs, seed=args.seed)
        card = _modelcard(dict(root='synthetic', row_count=len(rows)), catalog, hidden=args.hidden,
                          epochs=args.epochs, seed=args.seed, metrics=fitted['metrics'],
                          synthetic=True, root='synthetic',
                          scope_list=[episode['scope'] for episode in synthetic])
        refused = None
        try:
            training.export_candidate(fitted['parameters'], card, Path(args.out) / 'synthetic',
                                      vocabulary=vocabulary, keyword_vocabulary=keyword_vocabulary)
        except ValueError as error:
            refused = str(error)
        print(_dump(dict(kind='shop_value_synthetic_run', report=report, metrics=fitted['metrics'],
                         training_only=True, export_refused=refused,
                         note='Synthetic rows exercise the trainer; they are never a model of the game.')))
        return 0

    if not args.train:
        print(_dump(dict(kind='shop_value_readiness_run', report=report)))
        return 0

    if not report['training_ready']:
        print(_dump(dict(kind='shop_value_training_refused', report=report,
                         reason='insufficient reviewed independent episodes')))
        return 3

    dataset = training.load_reviewed_episodes(args.samples, catalog, ledger=args.ledger)
    train_episodes, test_episodes = training.split_by_scope(dataset['episodes'],
                                                            test_fraction=args.test_fraction, seed=args.seed)
    train_rows = [row for episode in train_episodes for row in episode['rows']]
    test_rows = [row for episode in test_episodes for row in episode['rows']]
    fitted = training.fit(train_rows, hidden=args.hidden, epochs=args.epochs, seed=args.seed)
    metrics = dict(fitted['metrics'])
    metrics['train_scopes'] = [episode['scope'] for episode in train_episodes]
    metrics['test_scopes'] = [episode['scope'] for episode in test_episodes]
    if test_rows:
        predictions = [training.forward(fitted['parameters'], row['values']) for row in test_rows]
        metrics['held_out'] = training.pairwise_accuracy(predictions, [row['target'] for row in test_rows])
    card = _modelcard(dataset, catalog, hidden=args.hidden, epochs=args.epochs, seed=args.seed,
                      metrics=metrics, synthetic=False, root=args.samples,
                      scope_list=[episode['scope'] for episode in dataset['episodes']])
    exported = training.export_candidate(fitted['parameters'], card, args.out,
                                         vocabulary=vocabulary, keyword_vocabulary=keyword_vocabulary)
    print(_dump(dict(kind='shop_value_candidate', report=report, exported=exported, metrics=metrics,
                     note='production_enabled is false; apply nothing from this file yet.')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
