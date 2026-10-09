"""Actual independent Maa preference nodes and isolated saved profiles; zero input."""
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maa.library import Library
from maa.resource import Resource
from maalimbus.jobs import wait_job
from maalimbus.mirror_preferences import collect,apply
from maalimbus.storage import ProfileStore,write_json,SINNERS
from maalimbus.policies import Team
from maalimbus.gift_vision import GiftCatalog
from maalimbus.theme_vision import ThemeCatalog


def main():
    pi=json.loads((ROOT/'assets/interface.json').read_text(encoding='utf8'))
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=30)
    assert collect(resource.get_node_data) is None
    def choice(option,case):
        patch=next(c for c in pi['option'][option]['cases'] if c['name']==case)['pipeline_override']
        assert resource.override_pipeline(patch)
    choices=[('mirror_preferences','edit'),('mirror_preference_slot','2'),
        ('mirror_preference_allow','Golden Urn'),('mirror_preference_block','Blue Zippo Lighter'),
        ('mirror_preference_pack','Sinking Deluge'),('mirror_preference_avoid_pack','Emotional Judgment'),
        ('mirror_preference_weight','75')]
    for option,case in choices:choice(option,case)
    edit=collect(resource.get_node_data)
    gifts=GiftCatalog(ROOT/'assets/resource/base').entries
    packs=ThemeCatalog(ROOT/'assets/resource/base').names
    with tempfile.TemporaryDirectory(prefix='mirror-preferences-') as tmp:
        directory=Path(tmp);store=ProfileStore(directory/'user-team-profiles.json')
        store.save([Team(2,frozenset({'Charge'}),deployment=SINNERS,graces=('1','3'),grace_budget=100),Team(7,frozenset({'Poise'}))])
        before=store.load();after=apply(directory,edit,gifts=gifts,packs=packs)
        assert after.allow=={'Golden Urn'} and after.block=={'Blue Zippo Lighter'}
        assert dict(after.pack_weights)=={'Sinking Deluge':75,'Emotional Judgment':0}
        assert (after.deployment,after.keywords,after.graces,after.grace_budget)==(before[0].deployment,before[0].keywords,before[0].graces,before[0].grace_budget)
        assert store.load()[1]==before[1]
        write_json(directory/'user-run-ledger.json',dict(version=1,active=dict(id='isolated',team=2)))
        assert apply(directory,edit,gifts=gifts,packs=packs)==after
        choice('mirror_preference_weight','100');changed=collect(resource.get_node_data)
        original=store.path.read_bytes()
        try:apply(directory,changed,gifts=gifts,packs=packs)
        except ValueError:pass
        else:raise AssertionError('active team edit accepted')
        assert store.path.read_bytes()==original
    proof=dict(passed=True,choices=choices,resolved=edit,isolated_profiles=True,
        active_team_edit_rejected=True,other_metadata_preserved=True,
        device_controller=False,input_sent=False,installed_gui_verified=False)
    (ROOT/'build/mirror-preferences-native-verification.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    print(json.dumps(proof))


if __name__=='__main__':main()
