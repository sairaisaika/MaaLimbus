from maalimbus.evidence_audit import recovery_kinds, silent_recoveries


def _event(kind=None, action=None):
    event = {'event': 'window_recovery', 'page': 'MAP', 'gesture': 'wait'}
    if kind is not None:
        event['refused_kind'] = kind
    if action is not None:
        event['recovery_action'] = action
    return event


def test_the_live_regression_is_reproduced_by_the_old_events():
    # What the retained evidence actually looks like: the fields are absent.
    report = recovery_kinds([_event() for _ in range(181)])
    assert report['total'] == 181
    assert report['named'] == 0
    assert report['covers_the_decision_table'] is False
    assert silent_recoveries(report) == 181


def test_a_named_recovery_is_counted_per_kind():
    report = recovery_kinds([_event('no_candidate', 'pan_view'),
                             _event('no_candidate', 'pan_view'),
                             _event('missing_control', 'bind_control')])
    assert report['kinds'] == {'no_candidate': 2, 'missing_control': 1}
    assert report['actions'] == {'pan_view': 2, 'bind_control': 1}
    assert report['covers_the_decision_table'] is True


def test_one_silent_recovery_is_enough_to_fail_the_claim():
    report = recovery_kinds([_event('no_candidate', 'pan_view'), _event()])
    assert report['covers_the_decision_table'] is False
    assert silent_recoveries(report) == 1


def test_no_recoveries_is_not_a_pass():
    # An absence of evidence must never read as "the table is covered".
    report = recovery_kinds([{'event': 'map_observed'}])
    assert report['total'] == 0
    assert report['covers_the_decision_table'] is False


def test_an_action_that_disagrees_with_its_kind_is_reported():
    from maalimbus.evidence_audit import inconsistent_decisions
    table = {'no_candidate': 'pan_view', 'refused_by_policy': 'stop'}
    good = _event('no_candidate', 'pan_view')
    bad = _event('no_candidate', 'escalate_ladder')
    assert inconsistent_decisions([good], table) == []
    wrong = inconsistent_decisions([good, bad], table)
    assert len(wrong) == 1
    assert wrong[0]['kind'] == 'no_candidate'
    assert wrong[0]['recorded'] == 'escalate_ladder'
    assert wrong[0]['expected'] == 'pan_view'


def test_an_unregistered_kind_must_hold_rather_than_guess():
    from maalimbus.evidence_audit import inconsistent_decisions
    # `hold` is the documented fallback for a kind the table does not know.
    assert inconsistent_decisions([_event('mystery', 'hold')], {}) == []
    assert inconsistent_decisions([_event('mystery', 'pan_view')], {}) != []


def test_a_silent_event_is_not_counted_as_a_wrong_decision():
    # Missing evidence is reported by recovery_kinds, not duplicated here.
    from maalimbus.evidence_audit import inconsistent_decisions
    assert inconsistent_decisions([_event()], {'no_candidate': 'pan_view'}) == []


def test_frozen_build_reports_unknown_rather_than_a_match():
    from maalimbus.evidence_audit import frozen_build
    report = frozen_build('/nonexistent-root')
    assert report['commit'] == 'unknown'
    assert report['dirty'] is None
