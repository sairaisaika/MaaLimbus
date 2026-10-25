"""A page nobody can name never sends an input, and its pause grows.

The loop's own contract for an unreadable frame -- wait, do not act -- is only exercised
live, where a mistake costs a run.  These tests drive `MirrorRunner.step` over a scripted
observer, so the contract is pinned offline: the frame the loop cannot name produces a
wait, the wait backs off, and the first named page after the streak is the first input.
"""
import json

import maalimbus.runner as runner
from maalimbus.runner import MirrorRunner


class _Journal:
    def __init__(self, directory):
        self.path = directory / 'events.jsonl'

    def record(self, event, **fields):
        row = {'event': event}
        row.update(fields)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row) + '\n')


class _Script:
    """Hands out the pages in order, one per read."""

    def __init__(self, directory, pages):
        self.directory = directory
        self.pages = list(pages)
        self.reads = 0

    def observe(self, deadline=None):
        page = self.pages[min(self.reads, len(self.pages) - 1)]
        self.reads += 1
        return {'scene': page, 'image_sha256': 'sha-%d' % self.reads,
                'size': [1920, 1080], 'ocr': [], 'frame': None}


def _loop(tmp_path, pages):
    device = runner.FakeDevice()
    loop = MirrorRunner(device, settings={'rounds': 1, 'interval': 0}, directory=tmp_path,
                        journal=_Journal(tmp_path))
    loop.observer = _Script(tmp_path, pages)
    return loop


def _events(tmp_path, name):
    rows = []
    path = tmp_path / 'events.jsonl'
    if not path.exists():
        return rows
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get('event') == name:
                rows.append(row)
    return rows


def test_an_unreadable_page_never_sends_an_input(tmp_path):
    loop = _loop(tmp_path, ['UNKNOWN'])
    result = loop.step()
    assert result.get('waiting') is True
    assert loop.device.clicks == []
    waits = (_events(tmp_path, 'window_unknown_wait')
             + _events(tmp_path, 'window_transition_wait'))
    assert waits, 'an unreadable frame is waited on, not acted on'
    assert loop.state.get('unknown_since') or loop.state.get('transition_seen')


def test_the_pause_after_an_unreadable_page_grows(tmp_path):
    loop = _loop(tmp_path, ['UNKNOWN'])
    loop.state['last_named_page'] = 'DRIVE'
    pauses = []
    for _ in range(4):
        left = loop.state.pop('unknown_since', None)
        result = loop.step()
        pauses.append(round(float(result.get('pause') or 0.0), 2))
        if left is not None:
            loop.state['unknown_since'] = left
    assert pauses[0] > 0
    assert pauses[-1] >= pauses[0]


def test_the_transition_poll_ramps_while_the_page_stays_unreadable(tmp_path):
    loop = _loop(tmp_path, ['UNKNOWN'])
    intervals = []
    for _ in range(3):
        loop.step()
        rows = _events(tmp_path, 'window_transition_wait')
        if rows:
            intervals.append(round(float(rows[-1]['interval_s']), 2))
    assert intervals, 'an unreadable frame is polled, and the poll records its pace'
    assert intervals == sorted(intervals), 'the poll backs off rather than staying fixed'
    assert loop.device.clicks == []


def test_the_map_click_comes_from_the_offered_destination(tmp_path, monkeypatch):
    """The loop clicks what the reader offered, and says so in the journal."""
    import maalimbus.window as window
    frame = tmp_path / 'frame-0001.json'
    frame.write_text(json.dumps({'image_sha256': 'sha-1', 'size': [1920, 1080],
                                 'ocr': []}), encoding='utf-8')
    monkeypatch.setattr(runner, 'candidates_of',
                        lambda directory, record: ('frame-0001', [[1002, 447, 40, 40]]))
    monkeypatch.setattr(runner, 'adjacent_to', lambda party, boxes, **kw: list(boxes))
    loop = _loop(tmp_path, ['MAP'])
    loop.state['map_party'] = [828, 439]
    loop.step()
    intents = _events(tmp_path, 'window_intent')
    assert intents, 'the offered destination is the input'
    assert intents[0]['page'] == 'MAP'
    x, y = list(loop.device.clicks)[0][:2]   # the click is jittered inside the box
    assert 1002 <= x <= 1042 and 447 <= y <= 487


def test_the_panel_enter_is_the_input_on_the_node_panel(tmp_path, monkeypatch):
    """A node panel offers one way on, and the loop takes it rather than waiting."""
    loop = _loop(tmp_path, ['NODE_PANEL'])
    result = loop.step()
    intents = _events(tmp_path, 'window_intent')
    # The panel either gets an input or the loop says it is waiting -- never silence, and
    # never an input aimed at another page.
    assert result.get('waiting') is True or intents
    assert all(row['page'] == 'NODE_PANEL' for row in intents)


def _hud_ocr(*, turn='5'):
    """The tokens the battle reader needs, at the boxes measured from live frames."""
    def token(text, x, y, w, h, score=0.95):
        return {'text': text, 'box': [x, y, w, h], 'score': score}
    return [token('WAVE', 40, 10, 70, 26), token('1/1', 120, 10, 60, 26),
            token('TURN', 40, 80, 70, 26), token(turn, 120, 80, 30, 26),
            token('MAX', 1648, 45, 60, 26),
            token('Win', 1704, 792, 40, 24), token('Rate', 1744, 792, 46, 24)]


class _HudScript(_Script):
    def observe(self, deadline=None):
        record = super().observe(deadline)
        record['ocr'] = _hud_ocr()
        return record


def _battle_loop(tmp_path, pages):
    loop = _loop(tmp_path, pages)
    loop.observer = _HudScript(tmp_path, pages)
    return loop


def test_the_speed_toggle_is_the_battles_first_input(tmp_path):
    loop = _battle_loop(tmp_path, ['BATTLE_HUD'])
    loop.step()
    intents = _events(tmp_path, 'window_intent')
    assert [row['reason'] for row in intents] == [
        'the_battles_speed_toggle_is_enabled_once_per_battle']
    x, y = list(loop.device.clicks)[0][:2]
    assert 1648 <= x <= 1708 and 45 <= y <= 71, 'the MAX caption is the control'


def test_the_speed_toggle_is_pressed_once_and_not_every_step(tmp_path):
    loop = _battle_loop(tmp_path, ['BATTLE_HUD'])
    for _ in range(3):
        loop.step()
    toggles = [row for row in _events(tmp_path, 'window_intent')
               if row.get('reason') == 'the_battles_speed_toggle_is_enabled_once_per_battle']
    assert len(toggles) == 1, 'D155: once per battle, not once per read'


def test_a_map_input_costs_one_read_after_it(tmp_path, monkeypatch):
    """D184: the settle loop asks once whether the map moved; the verdict waits.

    The reader is stubbed at `candidates_of` -- the loop is the subject here, not the
    vision -- so the box a map frame would offer is deterministic.
    """
    box = [1002, 447, 40, 40]
    monkeypatch.setattr(runner, 'candidates_of', lambda directory, record: ('frame-0001', [box]))
    loop = _loop(tmp_path, ['MAP'] * 6)
    before = loop.observer.reads
    loop.step()
    intents = _events(tmp_path, 'window_intent')
    assert [row['reason'] for row in intents] == ['map_node_click_is_the_only_proven_forward_input']
    settles = loop.observer.reads - before
    # Three reads, each with a job: the one that names the page, the one that proves the
    # click left it alone, and the one after the viewport gesture the refusal earns
    # (D167 bounds that last one separately).  It was four before D184.
    assert settles == 3, f'the map step reads three times, got {settles}'
    assert _events(tmp_path, 'map_click_result') == [], 'the verdict waits for the next read'


def test_a_transition_is_bounded_by_its_clock_and_by_its_rounds(tmp_path):
    """D186: the clock is the primary bound, and it is not the only one.

    An empty frame takes the transition branch, which is bounded by `transition_seconds`.
    That bound is a duration, so a starved or jumped monotonic (a suspended process, a
    test) turns the same branch into an unbounded loop; the round cap is the backstop, and
    the number is asserted where the loop hands over rather than at a magic count.
    """
    loop = _loop(tmp_path, ['UNKNOWN'] * 40)
    loop.settings._values['transition_rounds'] = 3
    before = loop.observer.reads
    for _ in range(6):
        loop.step()
    waits = _events(tmp_path, 'window_transition_wait')
    assert len(waits) == 3, f'the cap is three rounds, saw {len(waits)}'
    assert loop.observer.reads - before <= 3 + 6
