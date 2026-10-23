"""Every refusal must be a named, classified state -- not a fresh string per page.

`window._refuse` had 80 call sites and 77 distinct reasons; each new page added one
more, which is exactly how page-by-page patching happens.  This ratchet does not
demand that every reason be *handled*; it demands that every reason be *known*, so a
new ad-hoc string fails a test instead of silently joining the sprawl.
"""
import ast
import pathlib
import pytest

from maalimbus import pages

WINDOW = pathlib.Path('src/maalimbus/window.py')


def _refusal_reasons(path=WINDOW):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) or isinstance(fn, ast.Name)):
            continue
        name = fn.attr if isinstance(fn, ast.Attribute) else fn.id
        if name != '_refuse':
            continue
        for arg in node.args[1:]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.add(arg.value)
    return out


def test_the_scan_actually_finds_refusals():
    """A guard on the guard: an empty scan would pass vacuously."""
    assert len(_refusal_reasons()) >= 40


def test_every_refusal_reason_is_registered():
    reasons = _refusal_reasons()
    known = set(pages.REFUSALS) if hasattr(pages, 'REFUSALS') else set()
    unknown = sorted(r for r in reasons if r not in known)
    assert not unknown, (
        'unregistered refusal reason(s): %s\n'
        'Register each in maalimbus.pages.REFUSALS with the state it belongs to, or '
        'reuse an existing reason -- do not add a new page-specific string.'
        % ', '.join(unknown[:12]))


def test_every_refusal_names_one_of_the_closed_kinds():
    """A refusal's class decides what the recovery engine may do next.

    `unclassified` was the honest placeholder while the map was being built; with it
    gone, a new page-specific string cannot be added without also saying which of the
    six situations it is.  That is the whole point: the string is page-specific, the
    class is not.
    """
    from maalimbus import pages
    allowed = {'missing_control', 'no_candidate', 'attempts_exhausted',
               'unreadable_text', 'bad_saved_state', 'refused_by_policy'}
    unknown = {reason: kind for reason, kind in pages.REFUSALS.items()
               if kind not in allowed}
    assert unknown == {}, f'refusals with a kind outside the closed set: {unknown}'
    assert 'unclassified' not in set(pages.REFUSALS.values()), (
        'a refusal was left unclassified; pick one of the six kinds instead')


def test_each_kind_maps_to_exactly_one_action():
    """The kind is only worth classifying if it decides something.

    A seventh kind, or a kind without an action, would mean the recovery engine has
    a decision nobody wrote down -- so the table is asserted to cover the kinds
    exactly, and an unknown kind holds instead of guessing.

    Two kinds *may* share an action, but only on purpose: the pair is written down in
    ``pages.SHARED_ACTIONS`` next to the measurement that chose it.  What this test
    forbids is an *undeclared* share, which is how a page-specific patch would quietly
    take over another kind's recovery without anyone deciding it.  The previous form
    demanded six distinct actions and went red the moment ``bad_saved_state`` was
    moved onto ``escalate_ladder`` -- a contract that fails a deliberate decision is
    not a contract about the decision.
    """
    from maalimbus import pages
    assert set(pages.RECOVERY_BY_KIND) == set(pages.REFUSAL_KINDS)
    actions = set(pages.RECOVERY_BY_KIND.values())
    assert actions <= set(pages.RECOVERY_ACTIONS), (
        f'{sorted(actions - set(pages.RECOVERY_ACTIONS))} is not a declared action')
    groups = {}
    for kind, action in pages.RECOVERY_BY_KIND.items():
        groups.setdefault(action, []).append(kind)
    for action, kinds in groups.items():
        if len(kinds) == 1:
            continue
        declared = pages.SHARED_ACTIONS.get(action)
        assert declared is not None, (
            f'{sorted(kinds)} share {action!r}, which no decision declares')
        assert set(kinds) == set(declared), (
            f'the declared {action!r} group is {sorted(declared)}, the table has {sorted(kinds)}')
    assert pages.recovery_for('not_a_kind') == 'hold'
    assert pages.recovery_for('no_candidate') == 'pan_view'


def test_an_action_narrows_the_rungs_and_never_invents_one():
    """The action decides which rungs may be spent -- and only by narrowing.

    A text page must not be dragged (a drag on a confirmation screen can misroute the
    run), a policy refusal must not move the device at all, and an *unknown* action
    must fall back to the measured ladder rather than inventing a safer-looking one.
    """
    from maalimbus import pages
    ladder = (('pinch_out', 1), ('drag_down', 2), ('drag_up', 3), ('pan_left', 4), ('wait', 5))
    assert pages.ladder_for('stop', ladder) == ()
    for action in ('bind_control', 'reread_text', 'recompute_state'):
        assert pages.ladder_for(action, ladder) == (('wait', 5),), action
    for action in ('pan_view', 'escalate_ladder', 'hold', None):
        assert pages.ladder_for(action, ladder) == ladder, action
    invented = {rung[0] for a in pages.REFUSAL_KINDS
                for rung in pages.ladder_for(pages.recovery_for(a), ladder)}
    assert invented <= {rung[0] for rung in ladder}
