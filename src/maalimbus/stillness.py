"""Why the screen stopped changing -- three different problems, one symptom.

``window_stall`` used to fire whenever no new frame was stored for 300 s.  But a
frame is only stored when the pixels change (`runner.latest_frame`), so "no new
frame" means *the screen is static*, which conflates three realities with three
different correct responses:

* a static interstitial (loading art, a transition card) -- wait longer;
* a page that answers re-reads with new pixels -- alive, keep going;
* a page that is frozen and answers nothing -- stop and keep the evidence.

Classifying before acting is the whole point: the old code always chose "stop".
"""
from __future__ import annotations

INTERSTITIAL_PAGES = frozenset({
    'LOADING', 'NOW_LOADING', 'TRANSITION', 'UNKNOWN',
})

MOVING = 'moving'
INTERSTITIAL = 'static_interstitial'
ALIVE = 'the_page_still_answers_a_reread'
WAITING = 'waiting_for_a_page_that_never_comes'
FROZEN = 'frozen_page'

KEEP_WAITING = 'keep_waiting'
STOP = 'stop'


def classify(*, still_seconds: float, limit: float, page: str | None,
             probe_changed: bool | None = None,
             last_event: str | None = None) -> dict:
    """Name what the stillness is, and say what to do about it.

    ``probe_changed`` is the result of one bounded re-read: True when the re-read
    produced different pixels, False when it produced the same ones, None when no
    probe was possible.  ``None`` is not evidence of death.
    """
    if still_seconds < limit:
        return {'kind': MOVING, 'action': KEEP_WAITING,
                'reason': 'the_screen_is_still_changing'}
    if probe_changed is True:
        return {'kind': ALIVE, 'action': KEEP_WAITING,
                'reason': 'a_reread_produced_new_pixels'}
    if page in INTERSTITIAL_PAGES:
        return {'kind': INTERSTITIAL, 'action': KEEP_WAITING,
                'reason': 'the_page_is_expected_to_be_static'}
    if probe_changed is False and last_event:
        return {'kind': WAITING, 'action': STOP,
                'reason': 'an_intent_was_sent_and_the_page_never_answered'}
    return {'kind': FROZEN, 'action': STOP,
            'reason': 'the_page_is_frozen_and_answered_nothing'}


MAX_GRACE = 2


def should_exit(*, action: str, grace_used: int, max_grace: int = MAX_GRACE) -> dict:
    """Whether a classified stillness may stop the process.

    ``keep_waiting`` buys a *bounded* number of grace extensions -- waiting is not
    a licence for an infinite retry, so the third time the same verdict arrives the
    run still stops and keeps its evidence.
    """
    if action == KEEP_WAITING and grace_used < max_grace:
        return {'exit': False, 'reason': 'the_stillness_is_a_wait_not_a_stop',
                'grace_used': grace_used + 1}
    if action == KEEP_WAITING:
        return {'exit': True,
                'reason': 'the_wait_was_extended_beyond_its_bound',
                'grace_used': grace_used}
    return {'exit': True, 'reason': 'the_page_is_frozen', 'grace_used': grace_used}
