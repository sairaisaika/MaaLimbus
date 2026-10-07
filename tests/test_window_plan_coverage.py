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

# A few anchor page ids are shorter than the recognition page they prove, because
# the anchor name is also the file/naming stem. The driver only ever asks about the
# recognised page, so the coverage question has to be asked under that spelling.
PAGE_ALIASES = {'RUN_REWARD': 'RUN_REWARD_DIALOG'}


def _proven_pages():
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    pages = registry['pages']
    names = [p['id'] for p in pages] if isinstance(pages, list) else list(pages)
    assert len(names) >= 20, names
    return [PAGE_ALIASES.get(name.upper(), name.upper()) for name in names]


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
    # Both gaps found by the first run of this case are closed in window.py:
    #   BATTLE_RESULT - now refuses by name (battle_result_control_not_anchored)
    #     instead of answering observe-only, so the missing anchor is visible.
    #   BEFORE_ENTRY  - now shares the MIRROR_ENTRY branch; the entry page has one
    #     plan under two spellings.
    # Nothing may fall through to the generic refusal any more.
    assert offenders == [], (
        'these proven pages still fall through to the unknown-page refusal (%s): %s'
        % (fallback, offenders))
