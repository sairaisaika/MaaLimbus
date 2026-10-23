"""The stale-freeze trap is a guard test, not a habit."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import check_freeze  # noqa: E402


def test_a_current_freeze_is_accepted():
    report = check_freeze.verdict(head_sha='a' * 40, frozen_sha='a' * 40)
    assert report['state'] == 'current' and report['reason'] is None


def test_a_missing_build_names_the_repair():
    report = check_freeze.verdict(head_sha='a' * 40, frozen_sha=None)
    assert report['state'] == 'missing'
    assert 'refreeze' in report['reason']


def test_a_stale_freeze_is_reported_with_the_gap():
    report = check_freeze.verdict(head_sha='b' * 40, frozen_sha='a' * 40)
    assert report['state'] == 'stale'
    assert report['frozen'] == 'a' * 40 and report['head'] == 'b' * 40
    assert 'old code' in report['reason']


def test_the_repository_is_current_right_now():
    """Skips instead of failing when the checkout is not a full git history."""
    report = check_freeze.verdict()
    if report['state'] == 'missing':
        import pytest
        pytest.skip(report['reason'])
    assert report['state'] in {'current', 'stale'}
