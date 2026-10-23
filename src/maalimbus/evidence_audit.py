"""Read back what the engine *did*, not what the code says it would do.

A decision table that is wired at a call site but never receives its input is
indistinguishable from one that works, unless the produced events are counted.
This module exists because that happened: `refused_kind`/`recovery_action` were
passed to the `window_recovery` note, yet 0 of 181 retained events carried them,
because the reason was read from a field the recovery path never fills.
"""
from collections import Counter

# One concept, two event names: the ladder spending a rung, and the ladder running out.
# Counting only the first made the engine's give-up case invisible to the audit.
RECOVERY_EVENTS = ('window_recovery', 'window_recovery_exhausted')


def derivable_kinds(events):
    """Kinds that can be *re-derived* for recoveries that recorded none.

    Recording is the only evidence of what the engine decided at the time.  Evidence
    written before the recorder existed still carries the three names, so it can be
    re-derived -- but that is analysis, not a recording, and the audit reports it
    separately so an old run can never look like a verified new one.
    """
    from .pages import kind_of
    counts, total = {}, 0
    for event in events:
        if event.get('event') not in RECOVERY_EVENTS:
            continue
        if event.get('refused_kind'):
            continue
        kind = kind_of(reason=event.get('reason'),
                       stopped_reason=event.get('stopped_reason'),
                       plan_reason=event.get('plan_reason'))
        if kind:
            total += 1
            counts[kind] = counts.get(kind, 0) + 1
    return {'derived': total, 'kinds': counts}


def recovery_kinds(events):
    """Count the recovery events, and how many of them name their decision."""
    kinds = Counter()
    actions = Counter()
    total = 0
    for event in events:
        if not isinstance(event, dict) or event.get('event') not in RECOVERY_EVENTS:
            continue
        total += 1
        if event.get('refused_kind') is not None:
            kinds[event['refused_kind']] += 1
        if event.get('recovery_action') is not None:
            actions[event['recovery_action']] += 1
    named = sum(kinds.values())
    return {'total': total, 'named': named, 'kinds': dict(kinds),
            'actions': dict(actions),
            # A recovery that ran with no kind spent the full ladder blindly.
            'covers_the_decision_table': bool(total) and named == total}


def silent_recoveries(report):
    """How many recoveries ran without naming their decision (0 is the goal)."""
    return int(report.get('total', 0)) - int(report.get('named', 0))


def inconsistent_decisions(events, table=None):
    """Recoveries whose recorded action disagrees with the kind's table entry.

    Presence is not correctness: an event can name a kind and still have spent a
    different action than the table allows.  The expected action comes from the
    single table, so this check never re-states the policy a second time.
    """
    if table is None:
        from .pages import REFUSAL_KINDS, recovery_for
        table = {kind: recovery_for(kind) for kind in REFUSAL_KINDS}
    wrong = []
    for event in events:
        if not isinstance(event, dict) or event.get('event') != 'window_recovery':
            continue
        kind = event.get('refused_kind')
        if kind is None:
            continue
        expected = table.get(kind, 'hold')
        if event.get('recovery_action') != expected:
            wrong.append({'kind': kind, 'recorded': event.get('recovery_action'),
                          'expected': expected, 'page': event.get('page')})
    return wrong

def frozen_build(root=None):
    """Which build produced the packaged evidence, when the tree still has it.

    A tally like `named 0 of 184` is only interpretable next to the commit that
    wrote those events: evidence produced by an older freeze says nothing about
    a fix that landed later.  Missing file is reported as unknown, never as a
    match.
    """
    import json
    import pathlib
    base = pathlib.Path(root) if root is not None else pathlib.Path(__file__).resolve().parents[2]
    path = base / 'dist' / 'MaaLimbus' / 'build-info.json'
    try:
        info = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'commit': 'unknown', 'dirty': None}
    return {'commit': str(info.get('source_commit') or 'unknown'), 'dirty': info.get('dirty')}

