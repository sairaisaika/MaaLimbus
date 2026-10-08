"""The named flows are data, so they are checked as data.

A flow is the only place in the live tools where a coordinate is written down for a
control instead of being read from the anchors registry, so the tables get their own
checks: every band inside the frame, every pattern compilable, no step allowed to
click a control that ends or refuses something the run owns.
"""
from pathlib import Path
import re

import pytest

from maalimbus.session_flow import (ACTIVITY, FLOWS, MAX_REPEAT, PACKAGE, Step, center,
                                    flow, forbidden, names, token_of, validate)

ROOT = Path(__file__).resolve().parents[1]


def test_every_flow_validates_and_unknown_names_are_refused():
    assert validate() == []
    assert set(names()) == set(FLOWS)
    with pytest.raises(KeyError):
        flow('no_such_flow')


def test_drive_flow_reads_the_retained_split_mirror_caption_inside_its_band():
    # Retained frame-0004.json from window-20261008-032510; no ignored runtime
    # file dependency in CI. The full word is separate from the noisy fragment.
    record={'size':[1920,1080],'ocr':[
        {'text':'Dungeons','box':[605,477,148,30],'score':.98},
        {'text':'geons','box':[664,478,78,28],'score':.8}]}
    step=flow('to_mirror')[1]
    hit=token_of(record['ocr'],record['size'],step)
    assert hit and hit['text']=='Dungeons'
    assert token_of([{'text':'Dungeons','box':[600,900,148,30],'score':.99}],(1920,1080),step) is None


def test_the_launch_flow_starts_the_package_activity_itself():
    steps = flow('launch')
    assert steps[0].kind == 'start_app'
    assert ACTIVITY.startswith(PACKAGE + '/')
    assert [step.kind for step in steps].count('start_app') == 1
    assert [step.id for step in steps] == ['start_app', 'title_text', 'title_touch',
                                           'home_menu', 'home_popup']


def test_the_popup_step_may_clear_a_chain_but_never_waits_forever():
    popup = flow('launch')[-1]
    assert popup.optional is True
    assert 1 < popup.repeat <= MAX_REPEAT
    assert popup.kind == 'click' and popup.pattern == r'^Confirm$'


def test_a_flow_may_never_click_a_control_that_ends_or_refuses():
    for name in names():
        for step in flow(name):
            assert forbidden(step) is None
    # the guard holds for a table nobody has written yet
    halted = Step('stop_the_run', 'click', r'^Halt Exploration$', (.4, .5, .6, .6))
    refused = Step('refuse', 'click', r'^Refuse Gift$', (.6, .7, .8, .8))
    assert 'forbidden' in forbidden(halted)
    assert 'forbidden' in forbidden(refused)
    # ...and does not fire on a step that only looks at the screen
    assert forbidden(Step('look', 'wait', r'^Halt Exploration$', (.4, .5, .6, .6))) is None
    assert validate('launch') == []


def test_every_pattern_compiles_and_every_band_is_inside_the_frame():
    for name in names():
        for step in flow(name):
            if step.pattern:
                re.compile(step.pattern)
            if step.roi:
                x0, y0, x1, y1 = step.roi
                assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1, (name, step.id)


def test_token_of_only_reads_inside_its_own_band():
    size = (1920, 1080)
    records = [
        {'text': 'TOUCH TO START', 'box': [860, 820, 240, 34], 'score': .92},
        {'text': 'TOUCH TO START', 'box': [860, 60, 240, 34], 'score': .99},
    ]
    step = Step('title', 'click', r'^TOUCH TO START$', (.36, .72, .62, .84), .70)
    hit = token_of(records, size, step)
    assert hit == {'text': 'TOUCH TO START', 'box': [860, 820, 240, 34], 'score': .92}
    # the same text at the top of the screen is a different control and is not read
    top = Step('title', 'click', r'^TOUCH TO START$', (.36, .0, .62, .12), .70)
    assert token_of(records, size, top)['box'] == [860, 60, 240, 34]
    # an empty frame, or a pattern that is not there, is not a hit
    assert token_of([], size, step) is None
    assert token_of(records, size, Step('x', 'wait', r'^NOWHERE$', (.36, .72, .62, .84))) is None


def test_center_stays_inside_the_box_it_was_given():
    for box in ([0, 0, 10, 10], [900, 810, 80, 50], [1890, 1070, 30, 10]):
        x, y, w, h = center(box)
        assert box[0] <= x and x + w <= box[0] + box[2]
        assert box[1] <= y and y + h <= box[1] + box[3]
        assert w >= 1 and h >= 1
