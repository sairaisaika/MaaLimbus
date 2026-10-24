"""A torn-down task takes the controller binding with it (D82)."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

import maalimbus.runner as runner  # noqa: E402


class _Job:
    done = True
    succeeded = True


class _Controller:
    """A controller whose id still looks alive after the task was torn down."""

    id = 'still-non-empty'

    def __init__(self):
        self.posted = []

    def set_screenshot_target_long_side(self, _size):
        return None

    def post_click(self, x, y):
        self.posted.append(('click', x, y))
        return _Job()

    def post_swipe(self, *args):
        self.posted.append(('swipe',) + tuple(args))
        return _Job()

    def post_key(self, code):
        self.posted.append(('key', code))
        return _Job()


def _device():
    return runner.MaaDevice(_Controller())


def test_a_lost_binding_is_named_before_the_handle_is_trusted_again():
    device = _device()
    assert device.binding_lost is None
    device.note_binding_lost(runner.BINDING_GONE_AFTER_A_TORN_TASK)
    assert device.binding_lost == runner.BINDING_GONE_AFTER_A_TORN_TASK
    # The first reason is the one that happened first; a later note must not overwrite.
    device.note_binding_lost('something else')
    assert device.binding_lost == runner.BINDING_GONE_AFTER_A_TORN_TASK


@pytest.mark.parametrize('call', [lambda d: d.click(10, 20),
                                  lambda d: d.swipe(1, 2, 3, 4, 100),
                                  lambda d: d.key(4)])
def test_every_input_door_refuses_after_the_binding_is_gone(call):
    device = _device()
    device.note_binding_lost(runner.BINDING_GONE_AFTER_A_TORN_TASK)
    with pytest.raises(RuntimeError) as caught:
        call(device)
    assert runner.BINDING_GONE_AFTER_A_TORN_TASK in str(caught.value)
    assert device.controller.posted == []


def test_a_live_binding_still_posts():
    device = _device()
    device.click(10, 20)
    assert device.controller.posted == [('click', 10, 20)]


def test_the_reason_is_the_one_the_ending_and_the_kind_table_use():
    import maalimbus.pages as pages

    assert runner.BINDING_GONE_AFTER_A_TORN_TASK in pages.STOP_KINDS
    assert pages.kind_of(stopped_reason=runner.BINDING_GONE_AFTER_A_TORN_TASK) == 'refused_by_policy'


def test_a_torn_task_closes_input_and_keeps_reading(tmp_path):
    """The D74 continue path may read on; the next input must name the ending."""

    class _FailingTasker:
        def post_task(self, name):
            class _Done:
                done = True
                succeeded = False
            return _Done()

        def post_stop(self):
            class _Done:
                done = True
                succeeded = True
            return _Done()

    class _Device:
        tasker = _FailingTasker()

        def __init__(self):
            self.ended = None
            self.binding_lost = None
            self.posted = []

        def note_binding_lost(self, reason):
            if self.binding_lost is None:
                self.binding_lost = reason

        def end_session(self, reason):
            if self.ended is None:
                self.ended = reason

        def click(self, x, y):
            self.posted.append((x, y))

    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.device = _Device()
    loop.observer = None
    loop.state = {'page': 'MAP'}
    loop.notes = []
    # The page moved, which is what made D74 continue instead of ending.
    loop._page_after_a_failed_node = lambda page: 'MAP'
    loop.note = lambda name, **fields: loop.notes.append((name, fields))
    loop.artifacts = {}
    loop.deadline = None
    loop.ended = None
    loop.end_session = lambda reason, **fields: setattr(loop, 'ended', reason)

    verdict = loop._act('MirrorDrive')
    assert verdict['task_succeeded'] is False
    assert loop.device.ended is None, 'the loop may still read (D74)'
    assert loop.device.binding_lost == runner.BINDING_GONE_AFTER_A_TORN_TASK
    names = [name for name, _ in loop.notes]
    assert names[-2:] == ['node_action_unconfirmed', 'the_task_ended_but_the_page_moved']
