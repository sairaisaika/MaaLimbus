"""Replay native MXU option patches through Maa resources, with zero device input."""
import json
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from maa.library import Library
from maa.resource import Resource
from maalimbus.jobs import wait_job
from maalimbus.global_settings import collect_builds, apply_builds
from maalimbus.storage import SINNERS, ProfileStore, write_json
from maalimbus.policies import Team


def main():
    pi = json.loads((ROOT/'assets/interface.json').read_text(encoding='utf-8'))
    Library.open(ROOT/'dist/MaaLimbus/maafw', agent_server=False)
    resource = Resource()
    wait_job(resource.post_bundle(ROOT/'assets/resource/base'), timeout=30)
    patches = []
    expected = {}
    for slot, order in ((2, tuple(reversed(SINNERS))), (5, SINNERS)):
        prefix = f'global_team_{slot}'
        keys = [(prefix, 'edit'), (prefix+'_systems', 'Charge+Tremor')]
        keys += [(prefix+f'_order_{n}', sinner) for n, sinner in enumerate(order, 1)]
        for key, chosen in keys:
            option = pi['option'][key]
            case = next(c for c in option['cases'] if c['name'] == chosen)
            patches.append(case['pipeline_override'])
        name = f'Native team {slot}'
        patch = json.loads(json.dumps(pi['option'][prefix+'_name']['pipeline_override']).replace('{name}', name))
        patches.append(patch)
        expected[str(slot)] = dict(edit=True, name=name, keywords=['Charge','Tremor'],
                                   deployment={str(n): s for n,s in enumerate(order,1)})
    # Use sequential overrides just like ordinary MXU tasks. Multiple contributions
    # to one custom_action_param would erase each other; distinct nodes avoid that.
    for patch in patches:
        assert resource.override_pipeline(patch)
    actual = collect_builds(resource.get_node_data)
    assert actual == expected
    with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
        directory = Path(folder)
        store = ProfileStore(directory/'user-team-profiles.json')
        old = Team(2, frozenset({'Bleed'}), allow=frozenset({'Golden Urn'}))
        store.save([old])
        assert apply_builds(directory, actual) == [2,5]
        assert store.load()[0].allow == old.allow
        before = store.path.read_bytes()
        broken = json.loads(json.dumps(actual))
        broken['5']['deployment']['12'] = SINNERS[0]
        try:
            apply_builds(directory, broken)
        except ValueError:
            pass
        else:
            raise AssertionError('Duplicate sinner was accepted')
        assert store.path.read_bytes() == before
    for slot in (2,5):
        assert resource.override_pipeline({f'Global_global_team_{slot}':
                                           {'attach':{'global_build':{'edit':False}}}})
    assert collect_builds(resource.get_node_data) == {}
    proof = dict(passed=True, controller_created=False, device_input=False,
                 edited_slots=[2,5], independent_native_patches=len(patches),
                 unknown_or_duplicate_rejected=True, gui_verified=False)
    write_json(ROOT/'build/global-settings-native-verification.json', proof)
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
