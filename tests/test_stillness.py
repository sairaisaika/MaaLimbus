import pytest
from maalimbus import stillness as S


def test_a_still_changing_screen_is_not_a_stall():
    out = S.classify(still_seconds=5, limit=300, page='MAP')
    assert out['kind'] == S.MOVING and out['action'] == S.KEEP_WAITING


def test_a_reread_that_produces_pixels_keeps_the_run_alive():
    out = S.classify(still_seconds=301, limit=300, page='MAP', probe_changed=True)
    assert out['kind'] == S.ALIVE and out['action'] == S.KEEP_WAITING


def test_a_known_static_page_is_waited_out_not_killed():
    for page in ('LOADING', 'TRANSITION'):
        out = S.classify(still_seconds=301, limit=300, page=page, probe_changed=False)
        assert out['kind'] == S.INTERSTITIAL and out['action'] == S.KEEP_WAITING


def test_an_intent_that_never_answered_is_named_as_waiting():
    """The live case: RESUME_DIALOG + resume intent + 303 s of identical pixels."""
    out = S.classify(still_seconds=303.1, limit=300, page='RESUME_DIALOG',
                     probe_changed=False, last_event='resume_rejoins_the_run')
    assert out['kind'] == S.WAITING
    assert out['action'] == S.STOP
    assert out['reason'] == 'an_intent_was_sent_and_the_page_never_answered'


def test_no_probe_is_not_evidence_of_death():
    out = S.classify(still_seconds=301, limit=300, page='MAP', probe_changed=None)
    assert out['kind'] == S.FROZEN


def test_a_static_interstitial_never_wins_over_real_evidence():
    """A probe that saw change outranks the page's name."""
    out = S.classify(still_seconds=301, limit=300, page='LOADING', probe_changed=True)
    assert out['kind'] == S.ALIVE
