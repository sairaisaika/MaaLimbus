"""Who can write a plan's reason, and who reads one.

A plan is a dict whose ``reason`` is prose a human reads, but inside the loop that
word is a *key*: the runner has 30 sites that ask ``plan.get('reason') == '<word>'``
to decide which proof a sent input owes, and the refusal vocabulary asks which kind
the same word means.  Two things follow, and only one of them was ever checked:

1. A reader may only name a word some writer can produce.  A hook for a word nobody
   writes is a verification step that can never run -- invisible, because it simply
   never fires.
2. A word's *kind* must not depend on how the word happens to be spelled.  The one
   plan the runner builds by hand (``UNKNOWN_DIALOG``, clearing a proven owned-gift
   refusal) carried no literal kind, so ``kind_of`` fell through to the prose model,
   which read "refusal" in its name and answered ``refused_by_policy`` -- an action
   of ``stop``.  The chain's plans all answer from a literal table.  Measured
   2026-10-23: that is the only hand-built plan, so the class is small today and
   silent by construction; this module is what keeps it from growing silently.

Both sides are *derived from the source* rather than restated: :func:`producers`,
:func:`consumers` and :func:`unmatched` read ``window.py`` and ``runner.py`` with
``ast``, exactly the way :func:`maalimbus.window.dispatch_facts` reads the chain.
``tests/test_plan_reasons.py`` is the gate, and it contains the counter-examples
that must fail (an invented consumer, a plan whose reason no writer produces, a
hand-built plan whose word is not in :data:`maalimbus.pages.PLANNED_REASONS`).
"""
from __future__ import annotations

import ast
import pathlib


HERE = pathlib.Path(__file__).resolve().parent
WINDOW = HERE / 'window.py'
RUNNER = HERE / 'runner.py'

# The calls that *compose* a plan in the window layer.
PLAN_CALLS = ('_plan', '_refuse', 'plan_step')

# The literals `window.step_result` itself decides, so the vocabulary also covers the
# words a plan's *verdict* carries (a reader may ask about those too).
VERDICT_REASONS = ('unexpected_successor',)


def _source(path):
    return pathlib.Path(path).read_text(encoding='utf-8')


def _constant(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _elements(node):
    """Every string constant a literal can hold.

    Covers the tuple/list/set a membership test uses, the single constant, and the
    ``'a' if flag else 'b'`` choice the shelf's two purchase rules use -- a word
    picked at runtime between two literals is still two words that can be produced.
    """
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [v for v in (_constant(e) for e in node.elts) if v is not None]
    if isinstance(node, ast.IfExp):
        return _elements(node.body) + _elements(node.orelse)
    value = _constant(node)
    return [] if value is None else [value]


def _dict_reason(node):
    """The ``reason`` a plan-shaped dict literal or ``dict(...)`` call carries."""
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if _constant(key) == 'reason':
                return _constant(value)
        return None
    if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'dict':
        for keyword in node.keywords:
            if keyword.arg == 'reason':
                return _constant(keyword.value)
        for keyword in node.keywords:
            if keyword.arg == 'plan' and isinstance(keyword.value, ast.Dict):
                return _dict_reason(keyword.value)
    return None


def _window_reasons(source=None):
    """Every word the window layer can write into a plan or a plan's verdict."""
    tree = ast.parse(source if source is not None else _source(WINDOW))
    written = set(VERDICT_REASONS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
            if name == '_plan':
                for keyword in node.keywords:
                    if keyword.arg == 'reason':
                        written.update(_elements(keyword.value))
            elif name == '_refuse' and len(node.args) >= 2:
                written.update(_elements(node.args[1]))
        elif isinstance(node, ast.Dict):
            # Every plan-shaped literal in this file counts: a table row is a dict.
            word = _dict_reason(node)
            if word:
                written.add(word)
    return written


def _runner_plans(source=None):
    """The plans the runner builds itself, as ``{name: reason}``.

    A plan the runner assembles is not passed through ``window.plan_step``, so it
    inherits none of that door's bookkeeping: no ``FORBIDDEN_CONTROLS`` check, no
    refusal classification.  The only thing this module can prove about it is that
    its word is registered, which is why the gate names them.
    """
    tree = ast.parse(source if source is not None else _source(RUNNER))
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != 'plan':
            continue
        word = _dict_reason(node.value)
        if word:
            found[word] = node.lineno
    return found


def _consumer_words(node):
    """The words one comparison of ``plan['reason']`` / ``plan.get('reason')`` names."""
    if not isinstance(node, ast.Compare):
        return []
    left, right = node.left, node.comparators[0] if node.comparators else None
    for plan_side, word_side in ((left, right), (right, left)):
        if not _reads_plan_reason(plan_side):
            continue
        words = _elements(word_side)
        if words:
            return words
    return []


def _reads_plan_reason(node):
    """True when this expression reads the reason of a *plan*.

    Deliberately narrow: ``entry.get('reason')`` is a different vocabulary (the run's
    step verdicts, which ``pages.kind_of`` already owns), and the setting named
    ``observe_only`` is neither.  A reader of the two must not be counted here, or the
    gate would demand a *plan* writer for a word no plan ever carries.
    """
    target = None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == 'get' and node.args and _constant(node.args[0]) == 'reason':
            target = node.func.value
    elif isinstance(node, ast.Subscript) and _constant(getattr(node, 'slice', None)) == 'reason':
        target = node.value
    if target is None:
        return False
    if isinstance(target, ast.Name):
        return target.id == 'plan'
    return isinstance(target, ast.Attribute) and target.attr == 'plan'


def consumers(source=None):
    """``{word: [line, ...]}`` for every ``plan['reason']`` comparison in the runner."""
    tree = ast.parse(source if source is not None else _source(RUNNER))
    found = {}
    for node in ast.walk(tree):
        for word in _consumer_words(node):
            found.setdefault(word, []).append(node.lineno)
    return {word: sorted(lines) for word, lines in found.items()}


def producers(source=None):
    """``{'window': [...], 'runner': [...]}`` -- every word a writer can produce."""
    return {'window': sorted(_window_reasons(source)), 'runner': sorted(_runner_plans(source))}


def unmatched(source=None):
    """The relation between the two sides, as data.

    ``consumers_without_producer`` is the defect this module exists for: a hook that
    names a word no writer produces.  ``producers_without_consumer`` is *not* a defect
    -- most plans owe no extra proof -- so it is reported, never gated.
    """
    written = set(producers(source)['window']) | set(producers(source)['runner'])
    read = consumers(source)
    return {
        'consumers_without_producer': sorted(set(read) - written),
        'producers_without_consumer': sorted(written - set(read)),
        'hooks': sum(len(lines) for lines in read.values()),
        'words': len(read),
    }


def main(argv=None):
    """Print the relation; exit 1 when a hook names a word nobody writes."""
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    source_runner = None
    if argv and pathlib.Path(argv[0]).is_file():
        source_runner = _source(argv[0])
    relation = unmatched(source_runner)
    written = producers(source_runner)
    print(f"plans the window can write: {len(written['window'])}")
    print(f"plans the runner writes by hand: {len(written['runner'])}"
          + (f" {written['runner']}" if written['runner'] else ''))
    print(f"reason hooks in the runner: {relation['hooks']} over {relation['words']} words")
    if relation['consumers_without_producer']:
        print('hooks that name a word nobody writes:')
        for word in relation['consumers_without_producer']:
            print(f'  {word}')
    else:
        print('hooks that name a word nobody writes: none')
    print(f"words nobody reads: {len(relation['producers_without_consumer'])}")
    return 1 if relation['consumers_without_producer'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
