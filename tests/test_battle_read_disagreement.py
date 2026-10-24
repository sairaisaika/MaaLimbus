"""The battle reader may refine a named board; it may not demote it to UNKNOWN.

`evidence/runtime/packaged-mirror-20261024-084701` spent 180 s in 19
`window_transition_wait` rounds at `loop step 0`, `clicks_sent: 0`, on a battle that
was readable half the time: the map node named `BATTLE_HUD`, the battle node that runs
straight after it read `UNKNOWN`, and the observer replaced the named page with the
unreadable one. Every later branch then saw UNKNOWN.
"""
import json
import pathlib

from maalimbus.runner import MaaObserver


class _Journal:
    def __init__(self, directory):
        self.directory = pathlib.Path(directory)

    def record(self, event, **fields):
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(dict(event=event, **fields)) + '\n')


def _written_rows(directory, event):
    path = pathlib.Path(directory) / 'events.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip() and json.loads(line)['event'] == event]


class _Context:
    """A tasker that writes one row per node, in the shape the reader consumes."""

    def __init__(self, directory, *, map_scene, battle_scene=None):
        self.directory = pathlib.Path(directory)
        self.journal = _Journal(directory)
        self.map_scene = map_scene
        self.battle_scene = battle_scene
        self.tasker = self
        self.posted = []

    def post_task(self, name, override=None):
        self.posted.append(name)
        scene = self.map_scene if name == 'WindowMapObserve' else self.battle_scene
        event = 'map_observed' if name == 'WindowMapObserve' else 'battle_observed'
        self.journal.record(event, scene=scene, image_sha256='sha-' + name,
                            size=[1920, 1080], ocr=[])
        return _Job()

    def post_stop(self):
        return _Job(done=True)


class _Job:
    done = True
    succeeded = True


def test_an_unreadable_battle_frame_does_not_demote_a_named_board(tmp_path):
    observer = MaaObserver(_Context(tmp_path, map_scene='BATTLE_HUD',
                                    battle_scene='UNKNOWN'), tmp_path, read_tries=1)
    record = observer.observe()
    assert record['scene'] == 'BATTLE_HUD'
    assert record['battle_scene'] == 'UNKNOWN'
    assert record['battle_read'] == 'unreadable'


def test_the_battle_reader_still_refines_a_board_it_can_name(tmp_path):
    observer = MaaObserver(_Context(tmp_path, map_scene='BATTLE_HUD',
                                    battle_scene='BATTLE_HUD'), tmp_path, read_tries=1)
    record = observer.observe()
    assert record['scene'] == 'BATTLE_HUD'
    assert 'battle_read' not in record


def test_a_non_battle_page_never_runs_the_battle_reader(tmp_path):
    context = _Context(tmp_path, map_scene='MAP')
    observer = MaaObserver(context, tmp_path, read_tries=1)
    assert observer.observe()['scene'] == 'MAP'
    assert 'WindowBattleObserve' not in context.posted
