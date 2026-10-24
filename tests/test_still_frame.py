"""D104: the same picture read again and again is a frozen device, not a page rule.

Measured on `evidence/runtime/packaged-mirror-20261024-072236`: 97 reads, **one
distinct frame**, 48 clicks sent at it, and the run ended on the caller's clock.  The
read layer is where that has to end: a frozen screen must cost reads and no inputs.
"""
import types

import pytest

from maalimbus import pages, runner


class _Observer:
    """Hands back the same picture until ``change_at``, then a different one."""

    def __init__(self, directory, change_at=None, scene='BATTLE_TIP'):
        self.directory = directory
        self.change_at = change_at
        self.scene = scene
        self.reads = 0

    def observe(self, deadline=None):
        self.reads += 1
        if self.change_at is not None and self.reads >= self.change_at:
            sha = 'frame-%d' % self.reads
        else:
            sha = 'frame-frozen'
        return {'scene': self.scene, 'image_sha256': sha, 'size': [1920, 1080], 'ocr': []}


def _loop(tmp_path, observer, **settings):
    loop = runner.MirrorRunner(runner.FakeDevice(),
                               settings=dict({'rounds': 1, 'interval': 0}, **settings),
                               directory=tmp_path, observer=observer)
    return loop


def test_a_frozen_screen_ends_with_its_own_reason(tmp_path):
    observer = _Observer(tmp_path)
    loop = _loop(tmp_path, observer, still_frames=4)
    result = loop.run(steps=20, interval=0, round_limit=1)
    assert result is not None
    assert loop.state['session_ended'] == runner.STILL_FRAME_REASON
    assert loop.state['same_frames'] >= 4


def test_a_screen_that_changes_is_not_frozen(tmp_path):
    observer = _Observer(tmp_path, change_at=2)
    loop = _loop(tmp_path, observer, still_frames=3)
    loop.run(steps=2, interval=0, round_limit=1)
    assert loop.state.get('same_frames', 0) < 3


def test_the_frozen_ending_has_a_kind(tmp_path):
    assert pages.kind_of(reason=runner.STILL_FRAME_REASON) == 'unreadable_text'
    assert pages.recovery_for('unreadable_text') in pages.RECOVERY_ACTIONS


def test_the_budget_is_a_setting_with_bounds(tmp_path):
    assert runner.settings().still_frames == 10
    assert runner.settings({'still_frames': 1}).still_frames == 1
    for bad in (0, 201):
        with pytest.raises(ValueError):
            runner.settings({'still_frames': bad})
