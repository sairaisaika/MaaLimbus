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


def _elements(node, local=None):
    """Every string constant a literal can hold.

    Covers the tuple/list/set a membership test uses, the single constant, the
    ``'a' if flag else 'b'`` choice the shelf's two purchase rules use, and the
    ``state.get('reason') or 'the_default_word'`` fallback the initial-gift plan uses
    (D57: without the ``or`` the fallback word was invisible, so a plan that is a pixel
    proof looked like a plan with no proof at all).
    """
    if node is None:
        return []
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [v for v in (_constant(e) for e in node.elts) if v is not None]
    if isinstance(node, ast.IfExp):
        return _elements(node.body) + _elements(node.orelse)
    if isinstance(node, ast.BoolOp):
        found = []
        for value in node.values:
            found.extend(_elements(value))
        return found
    if isinstance(node, ast.Name) and local:
        # ``name, reason = ('a', 'b')`` then ``reason=reason``: a word chosen at runtime
        # between two literals is still a word the plan can produce (D57).
        return list(local.get(node.id) or ())
    value = _constant(node)
    return [] if value is None else [value]


def _dismissal(node):
    """True when an ``expect`` value admits :data:`maalimbus.window.ANY`.

    ``ANY`` is a proof, just a weak one: it says the page must *change*, without
    naming where to.  D49 counted only string constants here, so ``expect=(ANY,)``
    read as *no* expectation and eighteen words were declared unprovable when they
    carried a proof.  Measured 2026-10-23 against the retained archive: 28 declared,
    10 with nothing at all.
    """
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return any(getattr(element, 'id', None) == 'ANY' for element in node.elts)
    return getattr(node, 'id', None) == 'ANY'


def _advances(node):
    """True when an ``_plan``/row says ``advance=True`` -- its proof is the pixels.

    An advance plan is one whose own page is *expected* to stay (the tutorial overlay
    walks card after card), so `window.step_result` accepts a changed frame as proof.
    The page label therefore cannot judge it, which matters to
    :mod:`maalimbus.plan_outcomes`: a word whose page never moved may be perfectly
    judged if it advances.
    """
    return node is not None and getattr(node, 'value', None) is True


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


REFUSAL_ACTION = 'record'


def _locals(scope):
    """String constants bound to local names inside one scope (not its functions).

    ``name, reason = ('gift_search.refuse_button', 'the_player_asked...')`` is how two
    words reach one ``_plan`` call; without this the plan looked nameless to the index
    while the archive recorded it sending input (D57).  The map must be per scope: a
    module-wide map lets a name reused in three branches collect three words, which made
    a refusal's word look like a click's.
    """
    found = {}

    def take(target, value):
        if isinstance(target, ast.Name):
            values = _elements(value)
            if values and values != [target.id]:
                found.setdefault(target.id, []).extend(values)
        elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
            if len(target.elts) != len(value.elts):
                return
            for name, element in zip(target.elts, value.elts):
                if isinstance(name, ast.Name):
                    word = _constant(element)
                    if word is not None:
                        found.setdefault(name.id, []).append(word)

    def walk(statements):
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                take(statement.targets[0], statement.value)
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(statement, field, None)
                if isinstance(inner, list):
                    walk([node for node in inner if isinstance(node, ast.stmt)])
            for handler in getattr(statement, 'handlers', []) or []:
                walk(handler.body)

    walk(getattr(scope, 'body', []))
    return found


def _plan_index(node, local=None):
    """The reason, action and named successors of one ``_plan``/``_refuse`` call.

    The successor set is kept as *names*, not as a count: whether an observed page
    satisfies a plan depends on which names the plan stated (D57), and a count cannot
    answer that -- ``expect=('SHOP', 'SHOP_PURCHASE', 'UNKNOWN')`` accepts the page the
    plan acted from, while ``expect=('SHOP_PURCHASE',)`` does not.
    """
    if not isinstance(node, ast.Call):
        return []
    name = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
    if name == '_refuse' and len(node.args) >= 2:
        words = _elements(node.args[1])
        return [(word, REFUSAL_ACTION, [], False, False) for word in words]
    if name != '_plan':
        return []
    keywords = {keyword.arg: keyword.value for keyword in node.keywords}
    words = _elements(keywords['reason'], local) if 'reason' in keywords else []
    if not words:
        return []
    action = None
    if len(node.args) >= 2:
        action = _constant(node.args[1]) or getattr(node.args[1], 'id', None)
    names = _elements(keywords['expect'], local) if 'expect' in keywords else []
    dismissal = _dismissal(keywords['expect']) if 'expect' in keywords else False
    advance = _advances(keywords.get('advance'))
    return [(word, action or '?', names, dismissal, advance) for word in words]


def _row_facts(node):
    """One ``STEP_ROWS`` row as ``(word, action, expectation count)``.

    A row is a plan even though ``_plan`` is only called by the executor with the row's
    own values: the table is data, so its expectation lives in the data.
    """
    if not isinstance(node, ast.Dict):
        return []
    fields = {}
    for key, value in zip(node.keys, node.values):
        name = _constant(key)
        if name:
            fields[name] = value
    word = _constant(fields.get('reason'))
    if not word:
        return []
    action = _constant(fields.get('action')) or 'click'
    names = _elements(fields['expect']) if 'expect' in fields else []
    dismissal = _dismissal(fields['expect']) if 'expect' in fields else False
    advance = _advances(fields.get('advance'))
    return [(word, action, names, dismissal, advance)]


def acting_plans(source=None):
    """``{word: {'actions', 'expects', 'dismissal', 'advance', 'hooked'}}`` for sent input.

    A plan whose action is ``record`` refuses, so nothing was sent and nothing is owed.
    Every other action sends input, and then the plan states what *disproves* it: either
    an ``expect`` set (judged by :func:`maalimbus.window.step_result`) or a hook in the
    runner that reads the word back.  A word with neither cannot be told apart from a
    swallowed tap -- the run simply carries on and discovers the damage later, which is
    the shape of the retained failures.
    """
    window_source = source if source is not None else _source(WINDOW)
    tree = ast.parse(window_source)
    found = {}

    def take(word, action, names, hooked, dismissal=False, advance=False):
        entry = found.setdefault(
            word, {'actions': set(), 'sync': set(), 'dismissal': False,
                   'advance': False, 'hooked': False})
        if action:
            entry['actions'].add(action)
        entry['sync'].update(names or ())
        entry['dismissal'] = entry['dismissal'] or dismissal
        entry['advance'] = entry['advance'] or advance
        entry['hooked'] = entry['hooked'] or hooked

    read = set(consumers())
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def scope_of(node):
        parent = parents.get(node)
        while parent is not None and not isinstance(
                parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            parent = parents.get(parent)
        return parent

    scoped = {}
    for node in ast.walk(tree):
        scope = scope_of(node)
        local = scoped.get(id(scope))
        if local is None:
            local = scoped[id(scope)] = _locals(scope)
        for word, action, names, dismissal, advance in _row_facts(node) + _plan_index(node, local):
            take(word, action, names, word in read, dismissal, advance)
        if isinstance(node, ast.Assign) and any(
                getattr(target, 'id', None) == 'STEP_ROWS' for target in node.targets):
            if isinstance(node.value, ast.Dict):
                for row in node.value.values:
                    for word, action, names, dismissal, advance in _row_facts(row):
                        take(word, action, names, word in read, dismissal, advance)

    for name in _runner_plans(source=source):
        # A hand-built plan names its own action and expectation, and no caller can add
        # to it: measure it from the runner's own literal.
        runner_tree = ast.parse(_source(RUNNER))
        for node in ast.walk(runner_tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name) or target.id != 'plan':
                continue
            if _dict_reason(node.value) != name:
                continue
            action, names, dismissal = _hand_plan_facts(node.value)
            take(name, action, names, name in read, dismissal)

    return {
        word: {'actions': sorted(entry['actions']),
               'expects': len(entry['sync']),
               'expect_names': sorted(entry['sync']),
               'dismissal': entry['dismissal'],
               'advance': entry['advance'],
               'hooked': entry['hooked']}
        for word, entry in sorted(found.items())
        if entry['actions'] - {REFUSAL_ACTION}
    }


def _hand_plan_facts(node):
    """``(action, named successors, dismissal)`` of a plan the runner builds itself."""
    if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'dict':
        fields = {keyword.arg: keyword.value for keyword in node.keywords}
    elif isinstance(node, ast.Dict):
        fields = {_constant(key): value for key, value in zip(node.keys, node.values)}
    else:
        return (None, [], False)
    action = _constant(fields.get('action'))
    names = _elements(fields['expect']) if 'expect' in fields else []
    dismissal = _dismissal(fields['expect']) if 'expect' in fields else False
    return (action, names, dismissal)


def unproven(source=None):
    """The acting words whose result nothing can judge.

    A dismissal is a judgement: ``expect=(ANY,)`` fails when the page did not change.
    Only a word with no expectation, no dismissal and no hook is unprovable.
    """
    plans = acting_plans(source)
    return sorted(word for word, facts in plans.items()
                  if not facts['expects'] and not facts['dismissal'] and not facts['hooked'])


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
    plans = acting_plans(source_runner)
    naked = unproven(source_runner)
    print(f"acting plans: {len(plans)}"
          f"  with an expectation: {sum(1 for f in plans.values() if f['expects'])}"
          f"  named by a hook: {sum(1 for f in plans.values() if f['hooked'])}")
    print(f"acting plans whose result nothing can judge: {len(naked)}")
    if naked:
        from maalimbus import pages
        for word in naked:
            declared = pages.PLANS_WITHOUT_PROOF.get(word)
            print(f"  {word}: {declared or 'UNDECLARED'}")
    return 1 if relation['consumers_without_producer'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
