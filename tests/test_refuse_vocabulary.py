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
