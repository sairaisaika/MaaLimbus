"""A click that leaves no trace in the journal is a failure, not a wait.

Evidence: ``evidence/runtime/packaged-mirror-20261023-105851`` ends with a
``window_intent`` for ``RESUME_DIALOG`` at ``15:01:05`` and **no event after
it**; the MaaFW log at the same second carries ``controller not found
[req.controller_id=]`` for that click's reverse request.  The loop kept
running until the harness killed it, so a dead click looked like a slow run.

This names that state before anything else spends time on it.
"""

TRACE_WINDOW = 60.0


def classify(*, seconds_since_click, limit=TRACE_WINDOW, heartbeat_seen, page=None):
    """Return ``{'kind', 'action', 'reason'}`` for an outstanding click.

    ``heartbeat_seen`` is what the journal says: a heartbeat written *after*
    the click proves the loop is alive even when the page did not change.
    """
    if seconds_since_click is None:
        return {'kind': 'no_click_outstanding', 'action': 'keep_waiting',
                'reason': 'nothing_was_clicked_yet'}
    if seconds_since_click < limit:
        return {'kind': 'within_the_trace_window', 'action': 'keep_waiting',
                'reason': 'the_click_had_not_had_time_to_show_an_effect'}
    if heartbeat_seen:
        return {'kind': 'the_loop_is_alive', 'action': 'keep_waiting',
                'reason': 'the_loop_wrote_a_heartbeat_after_the_click'}
    return {'kind': 'the_click_left_no_trace', 'action': 'stop',
            'reason': 'the_click_left_no_trace'}
