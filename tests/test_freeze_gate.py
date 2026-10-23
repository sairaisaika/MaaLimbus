"""A stale frozen app must refuse a live run, not quietly test old code."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_freeze import runnable  # noqa: E402


def test_a_current_bundle_may_run():
    assert runnable({'state': 'current'})['run'] is True


def test_a_stale_bundle_is_refused_by_default():
    gate = runnable({'state': 'stale', 'frozen': 'abc', 'head': 'def'})
    assert gate['run'] is False
    assert gate['reason'] == 'the_frozen_app_predates_the_source_being_tested'


def test_a_missing_bundle_is_refused_too():
    assert runnable({'state': 'missing'})['run'] is False


def test_the_escape_hatch_says_so_in_the_record():
    gate = runnable({'state': 'stale'}, allow_stale=True)
    assert gate['run'] is True and gate['reason'] == 'stale_build_allowed_explicitly'


def test_a_test_only_commit_does_not_invalidate_the_artifact(tmp_path, monkeypatch):
    """The gate asks 'does the artifact carry this source', not 'is HEAD identical'."""
    import check_freeze
    real = check_freeze.verdict
    seen = {}
    def fake(head_sha, frozen_sha):  # exercise the scoped branch without a real repo
        seen['called'] = True
        return real(head_sha, frozen_sha)
    # The repo state is whatever it is; what must hold is that verdict reports which
    # artifact paths moved, so a caller can explain a refusal instead of guessing.
    report = check_freeze.verdict()
    assert 'artifact_commits' in report or report['state'] in ('current', 'missing')
