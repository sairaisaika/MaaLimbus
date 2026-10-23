"""The same kind must reach the same action whatever page it came from."""
from maalimbus.pages import kind_of, ladder_for, recovery_for

# One sample per family, deliberately written on different pages of the game loop.
SAMPLES = {
    'shop_offer_unaffordable': 'refused_by_policy',
    'skill_sinner_unknown': 'unreadable_text',
    'gift_blocked': 'refused_by_policy',
    'unverified_rotation': 'bad_saved_state',
    'current_position_not_proven': 'bad_saved_state',
    'the_page_is_frozen': 'attempts_exhausted',
    'caption_not_read': 'unreadable_text',
    'auto_assign_buttons_not_present': 'missing_control',
}

LADDER = ('pinch_out', 'drag_down', 'drag_up', 'pan_left', 'pan_right', 'wait')


def test_every_failure_name_reaches_an_action_not_a_hold():
    for name in SAMPLES:
        kind = kind_of(reason=name)
        assert kind is not None, f'{name} reached no kind, so the engine would hold'
        assert recovery_for(kind) != 'hold', f'{name} -> {kind} holds instead of acting'


def test_one_kind_one_action_across_pages():
    by_kind = {}
    for name in SAMPLES:
        kind = kind_of(reason=name)
        by_kind.setdefault(kind, set()).add(recovery_for(kind))
    assert all(len(actions) == 1 for actions in by_kind.values()), by_kind


def test_a_policy_refusal_stops_and_never_spends_a_gesture():
    assert recovery_for('refused_by_policy') == 'stop'
    assert ladder_for('stop', LADDER) == ()


def test_an_unclassified_name_still_holds_rather_than_guessing():
    assert kind_of(reason='something_nobody_classified') is None
    assert recovery_for(None) == 'hold'
