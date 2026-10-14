"""Record a human decision on one shop-purchase review sample.

The training scaffold refuses to export a model without reviewed episodes that carry a
human benefit label and verified delayed evidence, but nothing in the tree *writes* those
two files: every retained sample sits at ``review.json`` ``{"status": "pending"}`` and
``outcome.json`` ``training_eligible: false``. This is the missing half of that gate. It
records the decision, then re-reads the dataset through :mod:`maalimbus.shop_value_training`
so the reviewer immediately sees whether the episode became trainable or which rule still
excludes it.

It never touches the evidence. Frames, their hashes, ``sample.json`` and the
``outcome-<sha>.json`` copy are read-only here; the only writes are ``review.json`` and,
with an explicit ``--eligible``, the two eligibility flags in ``outcome.json``. That flag
is refused unless :func:`~maalimbus.shop_value_training.verify_episode_evidence` re-reads
the bytes and the run ledger and verifies them -- the same check the loader runs before a
training row may exist -- so approving cannot manufacture evidence.

Usage::

    python tools/review_shop_purchase.py --list
    python tools/review_shop_purchase.py <folder-or-scope> --approve --benefit 0.6 --note "why"
    python tools/review_shop_purchase.py <folder-or-scope> --approve --benefit 0.6 --eligible --note "why"
    python tools/review_shop_purchase.py <folder-or-scope> --reject --note "why"
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import shop_value_training as training  # noqa: E402

DEFAULT_SAMPLES = ROOT / training.DEFAULT_SAMPLES


def read_json(path):
    """(payload, None) or (None, 'missing'|'invalid')."""
    try:
        return json.loads(Path(path).read_text(encoding='utf-8')), None
    except FileNotFoundError:
        return None, 'missing'
    except (OSError, ValueError, UnicodeDecodeError):
        return None, 'invalid'


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def folders(root):
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(folder for folder in root.iterdir() if folder.is_dir())


def describe(folder):
    """What one sample folder claims about itself, without judging it."""
    folder = Path(folder)
    sample, sample_problem = read_json(folder / 'sample.json')
    review, review_problem = read_json(folder / 'review.json')
    outcome, outcome_problem = read_json(folder / 'outcome.json')
    sample = sample if isinstance(sample, dict) else {}
    review = review if isinstance(review, dict) else {}
    outcome = outcome if isinstance(outcome, dict) else {}
    return dict(
        folder=folder.name, path=str(folder), sample_problem=sample_problem,
        scope=sample.get('scope'), name=sample.get('name'), price=sample.get('price'),
        coins_before=sample.get('coins_before'), coins_after=sample.get('coins_after'),
        review_status=(review.get('status') if review else review_problem),
        benefit=review.get('benefit'), notes=review.get('notes') or '',
        outcome_problem=outcome_problem, outcome_eligible=outcome.get('training_eligible'),
        outcome_approved=outcome.get('human_approved'), outcome_reason=outcome.get('reason'),
        objective=outcome.get('objective'), category=outcome.get('category'),
        outcome_count=len(outcome.get('outcomes') or []),
    )


def find_folder(root, key):
    """A folder by exact or leading name, or by the scope its sample records."""
    for folder in folders(root):
        if folder.name == key or folder.name.startswith(key):
            return folder
        sample, _ = read_json(folder / 'sample.json')
        if isinstance(sample, dict) and sample.get('scope') == key:
            return folder
    return None


def decide(folder, *, approve=False, reject=False, benefit=None, eligible=False, note='',
           reviewed_by='human', ledger=None):
    """Write the decision, and return the folder's new description."""
    folder = Path(folder)
    if approve == reject:
        raise ValueError('pass exactly one of --approve or --reject')
    if not isinstance(note, str) or not note.strip():
        raise ValueError('a decision needs --note: the reason is the record')
    if reject and (benefit is not None or eligible):
        raise ValueError('--benefit and --eligible belong to --approve only')
    if approve and (type(benefit) is bool or not isinstance(benefit, (int, float))
                    or not 0.0 <= float(benefit) <= 1.0):
        raise ValueError('--benefit must be a number in 0..1')
    sample, sample_problem = read_json(folder / 'sample.json')
    if not isinstance(sample, dict):
        raise ValueError('sample.json is %s' % (sample_problem or 'invalid'))
    review, _ = read_json(folder / 'review.json')
    review = review if isinstance(review, dict) else {}
    outcome, outcome_problem = read_json(folder / 'outcome.json')
    if not isinstance(outcome, dict):
        raise ValueError('outcome.json is %s' % (outcome_problem or 'invalid'))
    if eligible:
        # Judge the bytes first, with the flags provisionally set: verify_episode_evidence
        # only returns verified for evidence whose hashes and run-ledger binding hold.
        ledger_state, ledger_problem = training._resolve_ledger(
            training.DEFAULT_LEDGER if ledger is None else ledger)
        provisional = dict(outcome, human_approved=True, training_eligible=True)
        verdict = training.verify_episode_evidence(folder, sample, provisional,
                                                  ledger=ledger_state, ledger_problem=ledger_problem)
        if not verdict.get('verified'):
            raise ValueError('refusing --eligible: the evidence does not verify (%s)' % verdict.get('reason'))
    review.update(dict(status='approved' if approve else 'rejected', notes=note.strip(),
                       reviewed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                       reviewed_by=reviewed_by))
    if approve:
        review['benefit'] = float(benefit)
    else:
        review.pop('benefit', None)
    if eligible:
        outcome['human_approved'] = True
        outcome['training_eligible'] = True
    write_json(folder / 'review.json', review)
    if eligible:
        write_json(folder / 'outcome.json', outcome)
    return describe(folder)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Record a human decision on one shop-purchase review sample.')
    parser.add_argument('folder', nargs='?', default=None, help='sample folder name, its prefix, or its scope')
    parser.add_argument('--root', default=str(DEFAULT_SAMPLES))
    parser.add_argument('--catalog', default=str(ROOT / training.DEFAULT_CATALOG))
    parser.add_argument('--list', action='store_true', help='list every sample and what it is waiting for')
    parser.add_argument('--approve', action='store_true')
    parser.add_argument('--reject', action='store_true')
    parser.add_argument('--benefit', type=float, default=None, help='the human label for an approved episode, 0..1')
    parser.add_argument('--eligible', action='store_true',
                        help='also mark outcome.json human_approved and training_eligible, if the evidence verifies')
    parser.add_argument('--note', default='', help='why this label; required for a decision')
    parser.add_argument('--reviewed-by', default='human')
    parser.add_argument('--json', default=None, help='write the result to this path')
    args = parser.parse_args(argv)

    root = Path(args.root)
    payload = dict(kind='shop_purchase_review', root=str(root), samples=[])

    if args.list or args.folder is None:
        for folder in folders(root):
            item = describe(folder)
            payload['samples'].append(item)
            print('%-14s scope=%-16s %-28s review=%-8s benefit=%-5s outcome=%s reason=%s' % (
                item['folder'][:12], str(item['scope'])[:16], str(item['name'])[:28],
                item['review_status'], item['benefit'], item['outcome_eligible'], item['outcome_reason']))
        if not payload['samples']:
            print('no sample folders under %s' % root)

    if args.approve or args.reject:
        if args.folder is None:
            raise SystemExit('a decision needs the folder or scope to decide about')
        folder = find_folder(root, args.folder)
        if folder is None:
            raise SystemExit('no sample folder matches %r under %s' % (args.folder, root))
        decided = decide(folder, approve=args.approve, reject=args.reject, benefit=args.benefit,
                         eligible=args.eligible, note=args.note, reviewed_by=args.reviewed_by)
        payload['decided'] = decided
        print(json.dumps(decided, ensure_ascii=False, sort_keys=True))
        report = training.readiness_report(root, training.load_catalog(args.catalog))
        payload['readiness'] = report
        print(json.dumps(dict(reviewed_episodes=report['reviewed_episodes'],
                              review_status_counts=report['review_status_counts'],
                              exclusion_reasons=report['exclusion_reasons'],
                              training_ready=report['training_ready'],
                              blockers=report['blockers']), ensure_ascii=False, sort_keys=True))
    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
