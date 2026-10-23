"""Read back what the engine *did*, not what the code says it would do.

A decision table that is wired at a call site but never receives its input is
indistinguishable from one that works, unless the produced events are counted.
This module exists because that happened: `refused_kind`/`recovery_action` were
passed to the `window_recovery` note, yet 0 of 181 retained events carried them,
because the reason was read from a field the recovery path never fills.
"""
from collections import Counter

def recovery_kinds(events):
    """Count the recovery events, and how many of them name their decision."""
    kinds = Counter()
    actions = Counter()
    total = 0
    for event in events:
        if not isinstance(event, dict) or event.get('event') != 'window_recovery':
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
