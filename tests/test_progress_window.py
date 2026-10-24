"""The progress watch must be able to fire inside the budgets this project uses (D89)."""

from maalimbus import runner


def test_the_progress_window_is_shorter_than_the_budgets_the_harness_uses():
    best = min(runner.MirrorRunner.PROGRESS_SECONDS, 90.0)
    assert runner.MirrorRunner.PROGRESS_SECONDS <= 120.0
    assert runner.MirrorRunner.PROGRESS_SECONDS <= best


def test_the_measured_silences_justify_the_window():
    # D89's measurement: p99 9.27 s over 25 880 inter-row gaps, and every gap over 60 s in
    # the corpus was a wedge.  The window must sit above the p99 with room, and below the
    # shortest gap a wedge ever showed (421 s).
    assert 30.0 <= runner.MirrorRunner.PROGRESS_SECONDS <= 120.0


def test_the_window_is_still_clamped_by_the_run_it_protects():
    import time

    finite = runner.bounded_limit(runner.MirrorRunner.PROGRESS_SECONDS,
                                  time.monotonic() + 5.0)
    assert finite <= 5.0
    assert runner.bounded_limit(runner.MirrorRunner.PROGRESS_SECONDS, None) == \
        runner.MirrorRunner.PROGRESS_SECONDS


def test_a_short_run_still_gets_a_positive_window():
    import time

    assert runner.bounded_limit(runner.MirrorRunner.PROGRESS_SECONDS,
                                time.monotonic() + 0.5) >= 1.0
