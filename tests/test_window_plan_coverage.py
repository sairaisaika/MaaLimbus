"""Every page the driver can meet must have its own plan, not a generic refusal.

The driver learns a page from the recognition layer and then asks
`maalimbus.window.plan_step` what single input that page allows. If a proven
page silently falls through to the same refusal an invented page gets, the
driver would stop on a page it can actually act on -- exactly the "planned but
never routed" gap that was found by hand in round 22. This case makes that gap
fail the suite instead of the device.
"""

import json
from pathlib import Path

from maalimbus.window import plan_step

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'assets' / 'resource' / 'base' / 'anchors.json'
UNKNOWN_PAGE = 'NOT_A_REAL_PAGE'


def _proven_pages():
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    pages = registry['pages']
    names = [p['id'] for p in pages] if isinstance(pages, list) else list(pages)
    assert len(names) >= 20, names
    return [name.upper() for name in names]


def test_the_fallback_refusal_is_named():
    plan = plan_step(UNKNOWN_PAGE)
    assert isinstance(plan, dict)
    assert plan.get('page') == UNKNOWN_PAGE
    assert plan.get('reason'), plan


def test_every_proven_page_gets_a_plan_of_its_own():
    fallback = plan_step(UNKNOWN_PAGE).get('reason')
    offenders = []
    for page in _proven_pages():
        plan = plan_step(page)
        assert isinstance(plan, dict), page
        assert plan.get('page') == page, (page, plan)
        if plan.get('reason') == fallback:
            offenders.append(page)
    # Known gaps, pinned rather than hidden. Both are proven pages with evidence
    # in the registry that still have no branch of their own in plan_step:
    #   BATTLE_RESULT - the victory screen; the pipeline clicks it through
    #     PostBattleObserve, but the driver would stop on it as observe-only.
    #   BEFORE_ENTRY  - the mirror-dungeon entry page, which the driver knows as
    #     MIRROR_ENTRY; the two spellings have not been reconciled.
    # Fixing either one means editing window.py, so shrink this list there.
    assert offenders == ['BATTLE_RESULT', 'BEFORE_ENTRY'], (
        'the set of proven pages falling through to the unknown-page refusal (%s) '
        'changed: %s' % (fallback, offenders))
