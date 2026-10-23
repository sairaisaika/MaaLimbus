"""An empty controller id is refused before the request is made.

Live case: `evidence/runtime/packaged-mirror-20261023-160749` -- MaaFW answered
`controller not found [req.controller_id=]` for a click at (937,595).  The loop had a
controller object, so every lower layer believed input was possible.
"""

from maalimbus.jobs import EMPTY_CONTROLLER_REASON, controller_ready


class Fake:
    def __init__(self, ident):
        self.controller_id = ident


def test_an_empty_id_is_not_ready():
    verdict = controller_ready(Fake(''))
    assert verdict['ready'] is False
    assert verdict['reason'] == EMPTY_CONTROLLER_REASON


def test_a_whitespace_id_is_not_ready():
    assert controller_ready(Fake('   '))['ready'] is False


def test_a_missing_attribute_is_unknown_not_empty():
    class Bare:
        pass

    verdict = controller_ready(Bare())
    assert verdict['ready'] is True, 'unknown must not be read as unroutable'
    assert verdict['reason'] == 'the_controller_id_is_not_exposed'


def test_a_real_id_is_ready():
    verdict = controller_ready(Fake('ctrl-1234'))
    assert verdict['ready'] is True
    assert verdict['controller_id'] == 'ctrl-1234'


def test_dispatch_refuses_an_empty_id_before_sending():
    """The request is never made, so the framework cannot answer `controller not found`."""
    import pytest

    from maalimbus import jobs

    sent = []

    class Job:
        done = False

        def wait(self, *a, **k):
            sent.append('sent')
            return None

    with pytest.raises(jobs.InputLost) as caught:
        jobs.dispatch(Fake(''), Job(), timeout=1)
    assert jobs.EMPTY_CONTROLLER_REASON in str(caught.value)
    assert sent == [], 'an unroutable request must not reach the device'
