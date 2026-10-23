from maalimbus.run_metrics import summarise


def test_a_run_with_no_refusals_reports_no_rate_rather_than_zero():
    rows = [{'event': 'map_observed', 'page': 'MAP', 'floor': 1},
            {'event': 'mirror_loop_stopped', 'reason': 'loop_deadline_exceeded'}]
    s = summarise(rows)
    assert s['recovery_rate'] is None, 'a rate with no denominator is not 0'
    assert s['stops'] == 1 and s['no_progress_stops'] == 0
    assert s['floors'] == [1]


def test_an_acceptance_that_did_not_move_the_party_is_not_counted_as_movement():
    rows = [{'event': 'map_click_result', 'outcome': 'accepted',
             'reason': 'the_party_moved_after_the_click'},
            {'event': 'map_click_result', 'outcome': 'accepted',
             'reason': 'a_new_target_replaced_this_one_before_the_page_settled'},
            {'event': 'window_recovery'},
            {'event': 'window_recovery'}]
    s = summarise(rows)
    assert s['verdicts'] == {'accepted': 1, 'accepted_other': 1}
    assert s['recovery_rate'] == 1.0


def test_a_recovery_counts_only_if_the_engine_acts_again_soon():
    from maalimbus.run_metrics import recovery_effect
    acted = [{'event': 'window_recovery'}, {'event': 'map_observed'},
             {'event': 'map_click_result', 'outcome': 'rejected'}]
    silent = [{'event': 'window_recovery'}] + [{'event': 'map_observed'}] * 4
    assert recovery_effect(acted)['rate'] == 1.0
    assert recovery_effect(silent)['rate'] == 0.0, 'a recovery that never acts again is not a recovery'
    assert recovery_effect([])['rate'] is None


def test_a_recovery_that_keeps_the_same_page_advanced_nothing():
    from maalimbus.run_metrics import recovery_advanced
    busy = [{'event': 'map_observed', 'page': 'MAP'},
            {'event': 'window_recovery'},
            {'event': 'map_observed', 'page': 'MAP'},
            {'event': 'map_click_result', 'outcome': 'rejected'}]
    moved = [{'event': 'map_observed', 'page': 'MAP'},
             {'event': 'window_recovery'},
             {'event': 'map_observed', 'page': 'MAP'},
             {'event': 'map_click_result', 'outcome': 'accepted',
              'reason': 'the_party_moved_after_the_click'}]
    assert recovery_advanced(busy)['rate'] == 0.0, 'busy is not advanced'
    assert recovery_advanced(moved)['rate'] == 1.0
    assert recovery_advanced([])['rate'] is None


def test_a_run_that_died_without_a_stop_is_not_counted_as_success():
    """A crashed process writes no `mirror_loop_stopped`, so it must say so.

    `packaged-mirror-20261023-094914` produced 183 events and reached floor 1, then the
    process failed natively (`exit 3221226505`) with `stop: null`.  Every rate derived
    from stops treated that run as absent rather than as a failure.
    """
    from maalimbus import run_metrics
    crashed = [{'event': 'map_observed', 'floor': 1}, {'event': 'map_observed', 'floor': 1}]
    assert run_metrics.summarise(crashed)['ended_without_a_stop'] is True

    stopped = crashed + [{'event': 'mirror_loop_stopped', 'reason': 'a_real_stop'}]
    assert run_metrics.summarise(stopped)['ended_without_a_stop'] is False
    assert run_metrics.summarise([])['ended_without_a_stop'] is False
