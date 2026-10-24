"""The map's progress panel is the last answer, not the first (D91).

Live run packaged-mirror-20261024-040640: one refused node click offered the
progress control, the panel left the exploration, the entry dialog resumed it and
the next click was refused exactly as before -- 70 s spent without a single
recovery rung. The ladder is what a refused click should spend first.
"""
import json
import types

import maalimbus.runner as runner


class _Journal:
    def __init__(self, directory):
        self.path = directory / 'events.jsonl'
        self.path.write_text('', encoding='utf-8')

    def record(self, event, **details):
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'event': event, **details}, ensure_ascii=False) + '\n')


def _events(tmp_path, name):
    rows = [json.loads(line) for line in (tmp_path / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    return [row for row in rows if row['event'] == name]


def test_a_fresh_map_does_not_want_the_panel():
    assert runner.map_escape_wanted({}) is False


def test_the_ladder_answers_the_first_two_refusals():
    assert runner.map_escape_wanted({'map_refused_streak': 1}) is False
    assert runner.map_escape_wanted({'map_refused_streak': 2}) is False


def test_the_third_refusal_is_the_one_the_streak_names():
    assert runner.MAP_ESCAPE_REFUSALS == 3
    assert runner.map_escape_wanted({'map_refused_streak': 3}) is True
    assert runner.map_escape_wanted({'map_refused_streak': 9}) is True


def test_a_stale_or_missing_count_is_not_a_streak():
    assert runner.map_escape_wanted({'map_refused_streak': None}) is False
    assert runner.map_escape_wanted({'map_refused_streak': '2'}) is False


def test_the_third_refusal_also_names_the_unresumed_case(tmp_path):
    state = {}
    notes = []
    for _ in range(3):
        runner.map_refusal_streak(state, lambda name, **fields: notes.append((name, fields)))
    assert state['map_refused_streak'] == 3
    assert [name for name, _ in notes] == ['map_clicks_refused_while_the_exploration_may_be_unresumed']
    assert runner.map_escape_wanted(state) is True


def test_the_step_asks_the_helper_instead_of_counting_itself():
    text = open(runner.__file__, encoding='utf-8').read()
    assert "if page=='MAP' and map_escape_wanted(state):" in text
    assert "if page=='MAP' and int(state.get('map_refused_streak') or 0)>=1:" not in text
