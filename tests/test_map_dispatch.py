"""The MAP naming question and the one bookkeeping rule that follows a click."""
from maalimbus import map_dispatch


def test_the_map_page_is_named_in_one_place():
    assert map_dispatch.is_map('MAP') is True
    assert map_dispatch.is_map('NODE_PANEL') is False
    assert map_dispatch.is_map(None) is False


def test_a_settled_node_panel_answers_a_pending_probe():
    state = {'navigation_probe_pending': True}
    assert map_dispatch.after_settle(state, 'MAP', 'NODE_PANEL') is True
    assert state['navigation_probe_pending'] is False


def test_nothing_is_recorded_when_no_probe_was_pending():
    state = {'navigation_probe_pending': False}
    assert map_dispatch.after_settle(state, 'MAP', 'NODE_PANEL') is False
    assert state['navigation_probe_pending'] is False


def test_another_page_cannot_clear_a_map_probe():
    """A shop frame that happens to follow a MAP click proves nothing about the map."""
    state = {'navigation_probe_pending': True}
    assert map_dispatch.after_settle(state, 'SHOP', 'NODE_PANEL') is False
    assert state['navigation_probe_pending'] is True


def test_a_map_frame_without_the_panel_leaves_the_probe_alone():
    """The party standing still is not evidence the probe was answered."""
    state = {'navigation_probe_pending': True}
    assert map_dispatch.after_settle(state, 'MAP', 'MAP') is False
    assert state['navigation_probe_pending'] is True


def test_the_ratchet_sees_fewer_inline_map_checks_than_before():
    from maalimbus import pages
    assert pages.INLINE_RUNNER['MAP'] <= 20
