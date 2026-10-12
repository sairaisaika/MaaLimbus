"""Scenario preflight for script-owned Burn/Tremor formation, EGO and learning.

This report never launches a run or edits the player's party. A native-rendered
scenario is not sufficient when its requested execution capabilities are absent.
"""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.policies import Team
from maalimbus.learning_dataset import digest,local_file
from maalimbus.vision import Text,find


def check(root,frame):
    root=Path(root);path=local_file(root,frame);record=read_json(path)
    image=local_file(root,str(path.with_suffix('.png')))
    if digest(image)!=record['image_sha256']:raise ValueError('Native frame changed')
    texts=[Text(x['text'],tuple(x['box']),x['score']) for x in record['ocr']]
    selected=record['scene']=='TEAM_LIBRARY' and len(find(texts,r'^TEAMS\s*#\s*22$',
        (.15,.12,.38,.23),record['size'],.9))==1
    scenario=Team(22,frozenset({'Burn','Tremor'}),formation_keywords=frozenset({'Burn','Tremor'}),auto_team=True)
    neural=read_json(root/'assets/resource/base/neural-learning.json')
    inventory=read_json(root/'build/private-owned-inventory.json')
    ledger=read_json(root/'config/user-run-ledger.json')
    blockers=[]
    if not selected:blockers.append('fresh_team22_selection_missing')
    if not inventory.get('inventory_complete'):blockers.append('owned_identity_inventory_incomplete')
    if neural.get('model_trained') is not True:blockers.append('neural_model_untrained')
    if neural.get('production_enabled') is not True:blockers.append('neural_application_disabled')
    # Actual existing runtime has no owned EGO reader/equipment transaction.
    blockers.extend(['identity_equipment_executor_missing','owned_ego_scan_and_equipment_executor_missing'])
    if ledger.get('active') is not None:blockers.append('previous_run_scope_unsettled')
    return dict(passed=False,team=scenario.slot,systems=sorted(scenario.formation_keywords),
        selected_game_team_verified=selected,owned_inventory_complete=inventory['inventory_complete'],
        model_trained=neural['model_trained'],neural_mode=neural['mode'],blockers=blockers,
        frame=str(path),frame_sha256=digest(path),image_sha256=digest(image),
        input_sent=False,party_changed=False,run_started=False,payout_claimed=False,
        policy='All requested capabilities must pass before a live validation run')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frame',required=True)
    a=p.parse_args();result=check(ROOT,a.frame)
    write_json(ROOT/'build/team22-runtime-readiness.json',result)
    print(result)
