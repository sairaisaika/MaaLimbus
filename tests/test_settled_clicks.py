"""One click is one verdict, not two rows (D198)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src')]

from maalimbus.run_metrics import settled_clicks


def _row(outcome, **extra):
    return dict(event='map_click_result', outcome=outcome, **extra)


def test_an_unjudged_row_and_its_answer_are_one_click():
    rows = [_row('unjudged'), _row('accepted'), _row('unjudged'), _row('rejected')]
    found = settled_clicks(rows)
    assert [r['outcome'] for r in found['settled']] == ['accepted', 'rejected']
    assert found['pending'] == []


def test_a_click_with_no_answer_stays_pending():
    rows = [_row('accepted'), _row('unjudged')]
    found = settled_clicks(rows)
    assert len(found['settled']) == 1 and len(found['pending']) == 1


def test_a_superseded_click_is_a_verdict_of_its_own():
    rows = [_row('superseded')]
    assert len(settled_clicks(rows)['settled']) == 1


def test_other_rows_are_ignored():
    rows = [dict(event='map_observed'), _row('accepted')]
    assert len(settled_clicks(rows)['settled']) == 1
