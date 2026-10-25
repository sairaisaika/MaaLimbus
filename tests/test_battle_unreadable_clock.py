"""A battle whose frames stay unreadable is a stop with a name (2026-10-25).

Measured on `packaged-mirror-20261025-013933`: 40 transition waits, every one after
`BATTLE_HUD`, 36 of them followed by another unreadable frame and 42 of 71 battle frames
carrying no turn badge -- ~144 s of a 300 s budget spent waiting for a picture that never
resolved.  The clock is the answer; the counter-examples are a page that resolves in time
and a non-battle page, which keeps D163's own clock.

D216 adds the second counter-example: a battle is not a page name, it is a screen that
prints its own captions.  Measured on `packaged-mirror-20261025-015256`, the screen had
stopped being a battle while the name still said `BATTLE_HUD`, and the clock counted
twelve rounds of a page that could no longer answer.
"""

import json

import maalimbus.runner as runner


def test_the_ending_has_a_name_and_a_kind():
    import maalimbus.pages as pages
    assert runner.BATTLE_UNREADABLE == 'the_battle_stayed_unreadable'
    assert pages.kind_of(reason=runner.BATTLE_UNREADABLE) == 'unreadable_text'
    assert pages.STOP_KINDS[runner.BATTLE_UNREADABLE] == 'unreadable_text'


def test_the_clock_is_far_below_a_run_budget():
    settings = runner.settings()
    limit = float(getattr(settings, 'battle_unreadable_seconds', 30.0))
    assert 5.0 <= limit <= 60.0


def test_a_named_battle_page_clears_nothing_by_itself():
    state = runner._fresh_state(runner.settings())
    assert 'battle_unknown_since' not in state


class _Journal:
    """One row per line, which is the shape the audits read."""

    def __init__(self, path):
        self.path = path

    def record(self, event, **fields):
        row = {'event': event}
        row.update(fields)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row) + '\n')


class _Pages:
    """A battle first, then a screen that is not one."""

    def __init__(self, directory):
        self.directory = directory
        self.reads = 0

    def observe(self, deadline=None):
        self.reads += 1
        if self.reads == 1:
            return {'scene': 'BATTLE_HUD', 'image_sha256': 'battle',
                    'size': [1920, 1080],
                    'ocr': [{'text': 'MAX', 'box': [1650, 50, 40, 20], 'score': 0.99},
                            {'text': 'Win', 'box': [1600, 800, 40, 20], 'score': 0.99},
                            {'text': 'Rate', 'box': [1600, 812, 40, 20], 'score': 0.99}],
                    'frame': None}
        return {'scene': 'UNKNOWN', 'image_sha256': 'sha-%d' % self.reads,
                'size': [1920, 1080],
                'ocr': [{'text': 'a fragment', 'box': [10, 10, 40, 20], 'score': 0.6}],
                'frame': None}


def test_a_frame_without_the_board_captions_is_not_a_battle(tmp_path):
    events = tmp_path / 'events.jsonl'
    loop = runner.MirrorRunner(runner.FakeDevice(),
                               settings={'rounds': 1, 'interval': 0,
                                         'battle_unreadable_seconds': 0.01},
                               directory=tmp_path, journal=_Journal(events))
    loop.observer = _Pages(tmp_path)
    loop.run(steps=3, interval=0, round_limit=9)
    rows = [json.loads(line) for line in
            events.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert any(row['event'] == 'battle_frame_without_its_controls' for row in rows)
    assert not [row for row in rows if row.get('reason') == runner.BATTLE_UNREADABLE]
