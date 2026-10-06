"""Every scene the pipeline names must be one the agent can actually read.

Pipeline nodes hand a scene name to the `limbus_scene` custom recognition, which
the agent side resolves.  A name nobody implemented fails only on a real run,
mid-dungeon, so this test freezes the set the pipeline uses today and checks
each name is mentioned by the agent modules that own those scenes
(`agent/recognition.py` plus everything under `src/maalimbus/`, which is where
the per-scene readers such as star_vision, theme_vision and window live).

Limits worth knowing: the mention check reads source *text*, so a scene named
only in a comment would pass.  It catches the real bug class -- a renamed,
typo'd or invented scene -- not a wrong implementation of a right name.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCENES = frozenset({
    'BATTLE_HUD', 'BATTLE_PLANNING', 'DEFEAT', 'DEPLOYMENT', 'DRIVE', 'DUNGEON_TEAM',
    'ENTRY_CONFIRM', 'EXPIRED_SESSION', 'GIFT_GET', 'GIFT_SEARCH', 'GIFT_SEARCH_FORGO',
    'HOME', 'INITIAL_GIFTS', 'LEVEL_WARNING', 'MIRROR_ENTRY', 'RESOURCE_DIALOG',
    'STAR_CONFIRM', 'STAR_GRACES', 'TEAM_LIBRARY', 'THEME_PACKS', 'TUTORIAL',
})


def pipeline_scene_nodes() -> list:
    found = []
    for path in sorted((ROOT / 'assets' / 'resource').glob('**/pipeline/*.json')):
        for name, node in json.loads(path.read_text(encoding='utf-8')).items():
            if node.get('custom_recognition') != 'limbus_scene':
                continue
            found.append((path.name, name,
                          (node.get('custom_recognition_param') or {}).get('scene'),
                          node.get('action')))
    return found


def pipeline_scenes() -> set:
    return {scene for _, _, scene, _ in pipeline_scene_nodes()}


def agent_source() -> str:
    sources = [ROOT / 'agent' / 'recognition.py']
    sources += sorted((ROOT / 'src' / 'maalimbus').glob('*.py'))
    return '\n'.join(path.read_text(encoding='utf-8') for path in sources)


def test_the_pipeline_only_names_scenes_the_agent_mentions():
    source = agent_source()
    unreadable = sorted(
        scene for scene in pipeline_scenes()
        if not scene or (("'%s'" % scene) not in source and ('"%s"' % scene) not in source)
    )
    assert unreadable == [], 'scenes no agent module mentions: %s' % unreadable


def test_the_frozen_scene_list_still_matches_the_pipeline():
    assert pipeline_scenes() == set(SCENES)


def test_a_plain_click_node_carries_a_click_bound():
    """`max_hit` is what keeps a plain Click node from clicking forever.

    `Custom` and `DoNothing` nodes are exempt: their own Python callback (a
    window plan, an observe step) enforces the bound, and several of them
    deliberately route on with no `max_hit` at all.
    """
    unbounded = []
    for path in sorted((ROOT / 'assets' / 'resource').glob('**/pipeline/*.json')):
        for name, node in json.loads(path.read_text(encoding='utf-8')).items():
            if node.get('custom_recognition') != 'limbus_scene':
                continue
            if node.get('action') not in ('Click', 'Swipe', 'Key'):
                continue
            bound = node.get('max_hit')
            if not isinstance(bound, int) or isinstance(bound, bool) or bound < 1:
                unbounded.append('%s (max_hit=%r)' % (name, bound))
    assert unbounded == [], 'plain click nodes without a click bound: %s' % unbounded


def _all_nodes() -> dict:
    nodes = {}
    for path in sorted((ROOT / 'assets' / 'resource').glob('**/pipeline/*.json')):
        for name, node in json.loads(path.read_text(encoding='utf-8')).items():
            assert name not in nodes, 'node %s is defined twice' % name
            nodes[name] = node
    return nodes


def test_every_route_target_is_a_node_that_exists():
    """A `next`/`on_error` pointing at a missing node is a runtime dead end."""
    nodes = _all_nodes()
    missing = sorted({
        '%s -> %s' % (name, target)
        for name, node in nodes.items()
        for key in ('next', 'on_error')
        for target in (node.get(key) or [])
        if target not in nodes
    })
    assert missing == [], 'routes pointing at missing nodes: %s' % missing
