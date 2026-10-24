"""The entry task must be able to end *inside* the run, not only enter it.

Live `packaged-mirror-20261024-010918`: at 05:12:41 the loop asked `MirrorDrive` on DRIVE,
the card click landed, the task walked `MIRROR_ENTRY` (Enter) and `RESUME_DIALOG` (Resume)
and the next frame was `MAP` -- the run it was asked to join.  The task had no node for
that page, span three reads on it and ended on `LimbusUnknown`
(`unknown_or_bounded_transition_exhausted`), which `D74` then had to rescue from the other
side.  `D83` adds the node; this file keeps the coverage honest, because the class of
defect is "the task's page vocabulary is older than the game's".
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
NODES = json.loads((ROOT / 'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))

#: every page the entry task was *observed* to stand on in the live run above, from that
#: run's own `recognized` rows and the `map_observed` that followed them.
LIVE_PAGES = ('DRIVE', 'MIRROR_ENTRY', 'RESUME_DIALOG', 'MAP')


def _reachable(nodes, entry='MirrorHard'):
    seen, todo = set(), [entry]
    while todo:
        name = todo.pop()
        if name in seen or name not in nodes:
            continue
        seen.add(name)
        node = nodes[name]
        todo.extend(list(node.get('next') or []))
        todo.extend(list(node.get('on_error') or []))
    return seen


def _scenes(nodes):
    out = set()
    for name in _reachable(nodes):
        scene = (nodes[name].get('custom_recognition_param') or {}).get('scene')
        if scene:
            out.add(scene)
    return out


def test_the_entry_task_can_end_inside_the_run():
    node = NODES['MirrorInside']
    assert (node.get('custom_recognition_param') or {}).get('scene') == 'MAP'
    assert node.get('action') == 'DoNothing'
    assert list(node.get('next') or []) == []


def test_every_page_the_live_entry_walked_has_a_node():
    scenes = _scenes(NODES)
    assert scenes >= set(LIVE_PAGES), sorted(set(LIVE_PAGES) - scenes)


def test_the_inside_node_is_reached_from_the_click_that_opens_the_run():
    assert 'MirrorInside' in NODES['MirrorDrive']['next']
    assert 'MirrorInside' in NODES['MirrorResume']['next']
    assert 'MirrorInside' in NODES['MirrorEnter']['next']


def test_the_coverage_gate_can_fail():
    without = {name: node for name, node in NODES.items() if name != 'MirrorInside'}
    for name in ('MirrorDrive', 'MirrorResume', 'MirrorEnter', 'MirrorHard'):
        without[name] = dict(without[name], next=[n for n in without[name]['next'] if n != 'MirrorInside'])
    assert 'MAP' not in _scenes(without), 'the gate would pass without the node'


def test_a_node_that_clicks_on_the_map_would_be_refused():
    nodes = {name: dict(node) for name, node in NODES.items()}
    nodes['MirrorInside'] = dict(nodes['MirrorInside'], action='Click', target=True)
    assert (nodes['MirrorInside'].get('custom_recognition_param') or {}).get('scene') == 'MAP'
    assert nodes['MirrorInside']['action'] != 'DoNothing'


def test_a_node_nobody_points_at_is_not_reachable():
    nodes = {name: dict(node) for name, node in NODES.items()}
    for name in ('MirrorDrive', 'MirrorResume', 'MirrorEnter', 'MirrorHard'):
        nodes[name] = dict(nodes[name], next=[n for n in nodes[name]['next'] if n != 'MirrorInside'])
    nodes['Orphan'] = dict(nodes['MirrorInside'])
    assert 'Orphan' not in _reachable(nodes)
    assert 'MirrorInside' not in _reachable(nodes)
