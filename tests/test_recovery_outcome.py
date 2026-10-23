"""A recovery is scored by what happened after it, never by a missing observation.

Measured regression (2026-10-23): `tools/recovery_outcome.py` paired every recovery
with the next page it could find, and when the recovery asked for *no input at all*
there was no page, so it compared `None` against the page name, counted the recovery
as a change, and reported `recompute_state` at 39/60 (65%). Twenty of those sixty
spends had no input follow them at all; the honest figure is 19/40 (48%) against
`escalate_ladder` 7/14 (50%). The policy that retired `recompute_state` cites
"0 of 51" in the same file's history, so the tool's arithmetic is not a detail: it
was the evidence a decision rested on.

These are the three shapes that must stay distinguishable -- a change, no change, and
no evidence -- plus the pairing rule that made the first version look reasonable.
"""
import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('recovery_outcome',
                                               REPO / 'tools' / 'recovery_outcome.py')
recovery_outcome = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recovery_outcome)


def _recovery(action, page='MAP', **fields):
    event = {'event': 'window_recovery', 'recovery_action': action, 'page': page}
    event.update(fields)
    return event


def _input(page=None):
    event = {'event': 'window_intent', 'page': page}
    return event


def _observed(page):
    return {'event': 'map_observed', 'page': page}


def test_a_recovery_with_no_input_is_not_evidence_of_a_change():
    events = [_recovery('recompute_state', page='MAP')]
    entry = recovery_outcome.summarise(events)[('recompute_state', 'unknown')]
    assert entry['no_evidence'] == 1
    assert entry['changed'] == 0, 'a missing observation was scored as an improvement'
    assert entry['same'] == 0
    assert entry['total'] == 1


def test_the_input_that_follows_is_the_boundary_and_the_page_after_it_is_the_verdict():
    # The page *at* the input is still the page being left; the next observation is
    # what the action produced.
    events = [
        _recovery('escalate_ladder', page='MAP'),
        _input(page='MAP'),
        _observed('SHOP'),
    ]
    entry = recovery_outcome.summarise(events)[('escalate_ladder', 'unknown')]
    assert (entry['changed'], entry['same'], entry['no_evidence']) == (1, 0, 0)


def test_a_page_that_did_not_move_is_counted_as_no_change():
    events = [
        _recovery('pan_view', page='MAP'),
        _input(page='MAP'),
        _observed('MAP'),
    ]
    entry = recovery_outcome.summarise(events)[('pan_view', 'unknown')]
    assert (entry['changed'], entry['same'], entry['no_evidence']) == (0, 1, 0)


def test_an_input_with_no_page_after_it_is_still_no_evidence():
    # A click was asked for but the run died before it read the screen: that is a
    # missing observation, not a failed recovery.
    events = [_recovery('bind_control', page='SHOP'), _input(page='SHOP')]
    entry = recovery_outcome.summarise(events)[('bind_control', 'unknown')]
    assert entry['no_evidence'] == 1
    assert entry['changed'] == 0


def test_the_kind_is_read_from_either_field_and_reported_with_the_action():
    events = [_recovery('reread_text', page='SHOP', recovery_kind='unreadable_text'),
              _input(), _observed('SHOP')]
    entry = recovery_outcome.summarise(events)[('reread_text', 'unreadable_text')]
    assert entry['same'] == 1


def test_an_empty_corpus_reports_nothing_rather_than_a_rate():
    assert recovery_outcome.summarise([]) == {}
