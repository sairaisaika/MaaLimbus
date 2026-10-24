"""An exemption allows an input to repeat; it does not allow it to repeat forever (D102).

Live `evidence/runtime/packaged-mirror-20261024-070705` sent 43 identical
`the_skill_detail_popup_is_dismissed_off_the_board` clicks on `BATTLE_TIP`, with every
frame different because the overlay animates, and no guard claimed it: the reason is on
`LOOP_GUARD_EXEMPT` and that list was read as "may repeat", not "may repeat forever".
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus import runner as runner_module  # noqa: E402


class _Journal:
    def __init__(self, directory):
        self.directory = directory
        self.rows = []

    def record(self, event, **details):
        self.rows.append(dict(details, event=event))

    def named(self, name):
        return [row for row in self.rows if row['event'] == name]


class _Observer:
    def __init__(self):
        self.record = {'scene': 'BATTLE_TIP', 'image_sha256': 'frame',
                       'size': [1920, 1080], 'ocr': []}
        self.directory = None

    def observe(self, deadline=None):
        return self.record


def _loop(tmp_path, **settings):
    loop = runner_module.MirrorRunner(_FakeDevice(), settings=dict(settings),
                                      directory=tmp_path, journal=_Journal(tmp_path))
    loop.observer = _Observer()
    return loop


class _FakeDevice:
    controller = type('C', (), {'id': 'abc'})()

    def frame_file(self, *args, **kwargs):
        return None

    def click(self, *args, **kwargs):
        return True


def test_an_exempt_reason_may_repeat_up_to_its_budget(tmp_path):
    loop = _loop(tmp_path, exempt_rounds=3)
    reason = 'the_skill_detail_popup_is_dismissed_off_the_board'
    verdicts = [loop._exempt_step('BATTLE_TIP', reason) for _ in range(4)]
    assert verdicts == ['allow', 'allow', 'allow', 'exhausted']
    # after the ladder gets its turn the count starts again
    loop.state['exempt_steps'].pop(('BATTLE_TIP', reason), None)
    assert loop._exempt_step('BATTLE_TIP', reason) == 'allow'


def test_a_different_page_forgets_the_count(tmp_path):
    loop = _loop(tmp_path, exempt_rounds=2)
    reason = 'victory_confirm_clears_the_result_and_carries_the_rewards'
    assert [loop._exempt_step('BATTLE_RESULT', reason) for _ in range(2)] == ['allow', 'allow']
    assert loop._exempt_step('RUN_CLAIM', reason) == 'allow'


def test_the_budget_is_a_setting_with_a_default():
    assert runner_module.settings().exempt_rounds == 6
    assert runner_module.settings({'exempt_rounds': 30}).exempt_rounds == 30
    with pytest.raises(ValueError):
        runner_module.settings({'exempt_rounds': 0})


def test_the_new_ending_has_a_kind():
    from maalimbus import pages
    assert pages.STOP_KINDS['the_exempt_input_repeated_without_progress'] == 'attempts_exhausted'
    assert pages.recovery_for('attempts_exhausted') == 'escalate_ladder'
