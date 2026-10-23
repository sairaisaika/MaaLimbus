from maalimbus.click_trace import classify


def test_no_click_yet_is_not_a_fault():
    assert classify(seconds_since_click=None, heartbeat_seen=False)['action'] == 'keep_waiting'


def test_a_young_click_is_still_within_its_window():
    verdict = classify(seconds_since_click=12.0, limit=60.0, heartbeat_seen=False)
    assert verdict['kind'] == 'within_the_trace_window'
    assert verdict['action'] == 'keep_waiting'


def test_a_heartbeat_after_the_click_proves_the_loop_is_alive():
    verdict = classify(seconds_since_click=300.0, heartbeat_seen=True)
    assert verdict['kind'] == 'the_loop_is_alive'
    assert verdict['action'] == 'keep_waiting'


def test_the_live_case_stops_with_a_name():
    """The real run: RESUME_DIALOG click, 420 s harness budget, no heartbeat."""
    verdict = classify(seconds_since_click=420.0, limit=60.0,
                       heartbeat_seen=False, page='RESUME_DIALOG')
    assert verdict['kind'] == 'the_click_left_no_trace'
    assert verdict['action'] == 'stop'
    assert verdict['reason'] == 'the_click_left_no_trace'


def test_the_window_is_inclusive_at_its_edge():
    assert classify(seconds_since_click=60.0, limit=60.0,
                    heartbeat_seen=False)['action'] == 'stop'
