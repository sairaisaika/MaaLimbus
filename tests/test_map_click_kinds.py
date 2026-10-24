"""A refused map click has to say what kind of box it was (D75).

`map_clicks` returns nine kinds of detected box.  `gold_badge_node` and `lattice_step`
arrive as 190x190 tiles whose centre is often empty space, while `lit_icon` arrives as
the 40x40 glyph the game marks its accepted step with -- and until D75 the verdict named
the refused box but not its kind, so "which kind lands" was unanswerable from the
archive.  These tests pin the writer, the reader, and the run that fills them.
"""

import importlib.util
import pathlib
import types

import pytest

import maalimbus.run_metrics as run_metrics
import maalimbus.runner as runner

REPO = pathlib.Path(__file__).resolve().parents[1]
PAST = '2026-10-23T10:00:00'


def _row(event, kind=None, outcome=None, **extra):
    row = {'event': event, 'utc': PAST}
    if kind is not None:
        row['kind'] = kind
    if outcome is not None:
        row['outcome'] = outcome
    row.update(extra)
    return row


def _click(directory, *rows):
    (directory / 'events.jsonl').write_text(
        '\n'.join(__import__('json').dumps(row) for row in rows) + '\n', encoding='utf-8')
    return directory


def _states():
    return [
        _row('map_click_result', 'gold_badge_node', 'rejected'),
        _row('map_click_result', 'gold_badge_node', 'rejected'),
        _row('map_click_result', 'gold_badge_node', 'accepted'),
        _row('map_click_result', 'lit_icon', 'accepted'),
    ]


def test_every_verdict_is_counted_under_the_kind_it_names(tmp_path):
    _click(tmp_path, *_states())
    kinds = run_metrics.click_kinds([tmp_path])
    assert kinds['sent'] == 4 and kinds['declared'] == 4
    assert kinds['by_kind']['gold_badge_node'] == {'sent': 3, 'accepted': 1, 'rejected': 2,
                                                   'superseded': 0}
    assert kinds['by_kind']['lit_icon']['accepted'] == 1


def test_a_verdict_without_a_kind_is_not_dropped_it_is_unrecorded(tmp_path):
    _click(tmp_path, _row('map_click_result', outcome='rejected'))
    kinds = run_metrics.click_kinds([tmp_path])
    assert kinds['sent'] == 1 and kinds['declared'] == 0
    assert list(kinds['by_kind']) == ['unrecorded']


def test_the_table_says_which_kind_lands(tmp_path):
    _click(tmp_path, *_states())
    report = run_metrics.click_kind_report(run_metrics.click_kinds([tmp_path]))
    rows = {row['kind']: row for row in report['rows']}
    assert report['measured'] is True
    assert report['basis'] == '4 of 4 click verdicts name a candidate kind'
    assert rows['gold_badge_node']['rate'] == 0.33
    assert rows['lit_icon']['rate'] == 1.0
    # The widest kind comes first, so a table scanned from the top reads the runs' habit.
    assert report['rows'][0]['kind'] == 'gold_badge_node'


def test_a_rate_needs_a_verdict_and_not_only_a_click(tmp_path):
    _click(tmp_path, _row('map_click_result', 'lit_icon', 'superseded'))
    report = run_metrics.click_kind_report(run_metrics.click_kinds([tmp_path]))
    assert report['rows'][0]['rate'] is None


def test_an_archive_that_never_named_a_kind_is_not_measured(tmp_path):
    _click(tmp_path, _row('map_click_result', outcome='accepted'))
    report = run_metrics.click_kind_report(run_metrics.click_kinds([tmp_path]))
    assert report['measured'] is False
    assert 'D75' in report['note']


def test_candidates_of_keeps_the_kind_of_the_boxes_it_offers(tmp_path, monkeypatch):
    import numpy as np
    monkeypatch.setattr(runner, 'latest_frame', lambda directory: (np.zeros((10, 10, 3), np.uint8),
                                                                  'frame-0001'))
    monkeypatch.setattr(runner, 'map_clicks', lambda image, template=None: [
        {'box': [10, 10, 190, 190], 'kind': 'gold_badge_node'},
        {'box': [200, 200, 40, 40], 'kind': 'lit_icon'},
    ])
    monkeypatch.setattr(runner, 'header_chrome', lambda record: None)
    monkeypatch.setattr(runner, 'party_point', lambda image: (100, 100))
    # The adjacency filter is not what this test is about: it keeps one box and the
    # kinds must still line up with the boxes that survived.
    monkeypatch.setattr(runner, 'adjacent_to', lambda party, boxes: [boxes[1]])
    record = {'scene': 'MAP'}
    name, boxes = runner.candidates_of(tmp_path, record)
    assert name == 'frame-0001' and boxes == [[200, 200, 40, 40]]
    assert record['map_candidate_kinds']['200,200,40,40'] == 'lit_icon'
    assert record['map_candidate_kinds']['10,10,190,190'] == 'gold_badge_node'
    # The dict travels into the loop's state and the final result, so it has to be
    # JSON-serializable -- a tuple key ended a live run with `callback_failed` (D75).
    import json as _json
    _json.dumps(record['map_candidate_kinds'])


def test_the_verdict_names_the_kind_of_the_box_it_judged():
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.state = {'map_candidate_kinds': {'678,353,40,40': 'lit_icon'}}
    seen = []
    loop.note = lambda name, **fields: seen.append((name, fields))
    loop._map_verdict(target=[678, 353, 40, 40], page='MAP', outcome='rejected',
                      reason='the_page_stayed_on_the_map_after_the_click')
    assert seen[0][1]['kind'] == 'lit_icon'
    assert seen[0][1]['outcome'] == 'rejected'


def test_a_verdict_for_a_box_the_offer_never_named_stays_unknown():
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.state = {}
    seen = []
    loop.note = lambda name, **fields: seen.append((name, fields))
    loop._map_verdict(target=[1, 2, 3, 4], page='MAP', outcome='rejected',
                      reason='a_new_target_replaced_this_one_before_the_page_settled')
    assert 'kind' not in seen[0][1] or seen[0][1]['kind'] is None


def test_the_audit_prints_the_table_and_refuses_an_empty_corpus(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location('audit_map_clicks',
                                                  REPO / 'tools' / 'audit_map_clicks.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    _click(tmp_path, *_states())
    assert tool.main(['--root', str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert 'gold_badge_node' in out and 'lit_icon' in out
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert tool.main(['--root', str(empty)]) == 2


def test_the_marked_step_is_tried_before_a_badge_tile(tmp_path, monkeypatch):
    """D75's live evidence: two `gold_badge_node` clicks were refused while the one
    `bright_lit_icon` box sat fourth in the list and was never reached."""
    import numpy as np
    monkeypatch.setattr(runner, 'latest_frame', lambda directory: (np.zeros((10, 10, 3), np.uint8),
                                                                  'frame-0001'))
    monkeypatch.setattr(runner, 'map_clicks', lambda image, template=None: [
        {'box': [755, 238, 190, 190], 'kind': 'gold_badge_node'},
        {'box': [1002, 447, 40, 40], 'kind': 'lit_icon'},
        {'box': [545, 239, 190, 190], 'kind': 'gold_badge_node'},
    ])
    monkeypatch.setattr(runner, 'header_chrome', lambda record: None)
    monkeypatch.setattr(runner, 'party_point', lambda image: (900, 450))
    # Adjacency is not the question here: the ordering is applied to whatever survived it.
    monkeypatch.setattr(runner, 'adjacent_to', lambda party, boxes: list(boxes))
    record = {'scene': 'MAP'}
    _, boxes = runner.candidates_of(tmp_path, record)
    assert boxes[0] == [1002, 447, 40, 40]
    assert [record['map_candidate_kinds'][runner.box_key(box)] for box in boxes] == [
        'lit_icon', 'gold_badge_node', 'gold_badge_node']


def test_an_unknown_kind_is_kept_at_the_end_and_not_dropped(tmp_path, monkeypatch):
    import numpy as np
    monkeypatch.setattr(runner, 'latest_frame', lambda directory: (np.zeros((10, 10, 3), np.uint8),
                                                                  'frame-0001'))
    monkeypatch.setattr(runner, 'map_clicks', lambda image, template=None: [
        {'box': [1, 1, 40, 40], 'kind': 'something_new'},
        {'box': [80, 80, 40, 40], 'kind': 'lit_node'},
    ])
    monkeypatch.setattr(runner, 'header_chrome', lambda record: None)
    monkeypatch.setattr(runner, 'party_point', lambda image: (50, 50))
    monkeypatch.setattr(runner, 'adjacent_to', lambda party, boxes: list(boxes))
    _, boxes = runner.candidates_of(tmp_path, {'scene': 'MAP'})
    assert boxes == [[80, 80, 40, 40], [1, 1, 40, 40]]


def test_the_kind_survives_a_click_the_loop_replaced(tmp_path):
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.state = {'map_candidate_kinds': {}, 'map_pending': [678, 353, 40, 40],
                  'map_pending_kind': 'bright_lit_icon'}
    seen = []
    loop.note = lambda name, **fields: seen.append((name, fields))
    loop._map_verdict(target=[678, 353, 40, 40], page='MAP', outcome='rejected',
                      reason='a_new_target_replaced_this_one_before_the_page_settled')
    assert seen[0][1]['kind'] == 'bright_lit_icon'
