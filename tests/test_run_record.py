"""A run's cause must never be empty: event first, exit code second."""

from tools import run_record


def test_a_recorded_stop_wins_over_the_exit_code():
    events = [{'event': 'mirror_loop_stopped', 'reason': 'the_five_floors_cleared'}]
    out = run_record.summarise(events, 3221226505)
    assert out['stop'] == 'the_five_floors_cleared'


def test_a_native_death_is_named_from_the_exit_code():
    out = run_record.summarise([], 3221226505)
    assert out['stop'] == 'the_controller_crashed_inside_a_click'


def test_a_clean_exit_without_events_has_no_invented_cause():
    out = run_record.summarise([], 0)
    assert out['stop'] is None
    assert out['events'] == 0 and out['floors'] == []


def test_floors_and_floor_five_are_read_from_the_events():
    events = [{'event': 'map_observed', 'floor': 2}, {'event': 'map_observed', 'floor': 5},
              {'event': 'map_observed', 'floor': None}]
    out = run_record.summarise(events, 0)
    assert out['floors'] == [2, 5] and out['reached_floor_5'] is True
