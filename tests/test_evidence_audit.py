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


def test_a_superseded_action_is_judged_by_the_build_that_wrote_it():
    """Archived evidence is not re-litigated every time the policy moves.

    `bad_saved_state` recorded `reset_state`, then `recompute_state`, then
    `escalate_ladder` (3 / 60 / 21 events).  All three are consistent with the policy
    of their own build, so the audit must not call the first two contradictions --
    while anything NOT in ``SUPERSEDED_ACTIONS`` must still fail, or the exemption
    would swallow the check it exists to keep honest.
    """
    from maalimbus import pages
    from maalimbus.evidence_audit import inconsistent_decisions
    table = {kind: pages.recovery_for(kind) for kind in pages.REFUSAL_KINDS}
    assert table['bad_saved_state'] == 'escalate_ladder'
    old = [_event('bad_saved_state', 'reset_state'),
           _event('bad_saved_state', 'recompute_state'),
           _event('bad_saved_state', 'escalate_ladder')]
    assert inconsistent_decisions(old, table) == []
    invented = _event('bad_saved_state', 'pan_view')
    wrong = inconsistent_decisions(old + [invented], table)
    assert [entry['recorded'] for entry in wrong] == ['pan_view']
    # The exemption is per kind: an old action recorded under a different kind is
    # still a contradiction.
    moved = _event('attempts_exhausted', 'recompute_state')
    assert inconsistent_decisions([moved], table) != []


def test_a_silent_event_is_not_counted_as_a_wrong_decision():
    # Missing evidence is reported by recovery_kinds, not duplicated here.
    from maalimbus.evidence_audit import inconsistent_decisions
    assert inconsistent_decisions([_event()], {'no_candidate': 'pan_view'}) == []


def test_frozen_build_reports_unknown_rather_than_a_match():
    from maalimbus.evidence_audit import frozen_build
    report = frozen_build('/nonexistent-root')
    assert report['commit'] == 'unknown'
    assert report['dirty'] is None


def test_the_give_up_event_is_counted_too():
    from maalimbus.evidence_audit import recovery_kinds

    events = [
        {'event': 'window_recovery', 'refused_kind': 'no_candidate', 'recovery_action': 'pan_view'},
        {'event': 'window_recovery_exhausted', 'refused_kind': 'bad_saved_state',
         'recovery_action': 'recompute_state'},
    ]
    report = recovery_kinds(events)
    assert report['total'] == 2 and report['named'] == 2
    assert set(report['kinds']) == {'no_candidate', 'bad_saved_state'}


def test_a_parent_directory_expands_into_every_run(tmp_path):
    from maalimbus.evidence_audit import evidence_directories

    (tmp_path / 'packaged-mirror-a').mkdir()
    (tmp_path / 'packaged-mirror-b').mkdir()
    (tmp_path / 'unrelated').mkdir()
    found = evidence_directories(str(tmp_path))
    assert sorted(p.rsplit('\\', 1)[-1].rsplit('/', 1)[-1] for p in found) == [
        'packaged-mirror-a', 'packaged-mirror-b']


def test_a_run_directory_is_not_expanded_again(tmp_path):
    from maalimbus.evidence_audit import evidence_directories

    run = tmp_path / 'packaged-mirror-a'
    run.mkdir()
    assert evidence_directories(str(run)) == [str(run)]


def test_a_corpus_without_the_recorded_field_is_untested_not_failed():
    """'named == 0' must not be read as 'the fix failed' on old evidence.

    The recorder writes `refused_kind` on every recovery it sees, even with a null
    value; a run that predates the recorder has no such key.  Without this signal the
    audit reported 196 silent recoveries and called the decision table dead, when the
    truth was that none of that evidence came from a build that records anything.
    """
    from maalimbus import evidence_audit
    old = [{'event': 'window_recovery', 'reason': 'something'}]
    report = evidence_audit.recovery_kinds(old)
    assert report['named'] == 0
    assert report['recorder_writes_the_field'] is False

    fixed = [{'event': 'window_recovery', 'refused_kind': None, 'recovery_action': 'hold'}]
    report = evidence_audit.recovery_kinds(fixed)
    assert report['recorder_writes_the_field'] is True
