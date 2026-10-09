"""Actual native option parsing and isolated current-run budget application."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maa.library import Library
from maa.resource import Resource
from maalimbus.jobs import wait_job
from maalimbus.reward_task_budget import apply
from maalimbus.storage import read_json,write_json


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=30)
    pi=read_json(ROOT/'assets/interface.json')
    task=next(t for t in pi['task'] if t['name']=='rewards')
    assert task['option']==['reward_module_budget'] and not task['default_check']
    assert resource.get_node_data('RewardModuleBudget')['attach']['maximum']=='saved'
    names=['user-run-ledger.json','user-reward-claim-transaction.json','user-mirror-settings.json','user-team-profiles.json']
    hashes={n:hashlib.sha256((ROOT/'config'/n).read_bytes()).hexdigest() for n in names}
    parsed=[]
    with tempfile.TemporaryDirectory(prefix='maalimbus-reward-budget-') as temporary:
        config=Path(temporary)
        for name in names:write_json(config/name,read_json(ROOT/'config'/name))
        policy=read_json(config/'user-mirror-settings.json')
        scope=read_json(config/'user-run-ledger.json')['active']['id']
        for case in pi['option']['reward_module_budget']['cases']:
            assert resource.override_pipeline(case['pipeline_override'])
            selected=resource.get_node_data('RewardModuleBudget')['attach']['maximum']
            before=(config/'user-mirror-settings.json').read_bytes()
            apply(config,selected)
            actual=read_json(config/'user-mirror-settings.json')
            if selected=='saved':assert (config/'user-mirror-settings.json').read_bytes()==before
            else:
                assert actual==dict(policy,reward_budget_scope=scope,max_reward_modules=selected,module_budget_pending=selected==0)
            assert resource.get_node_data('RewardsTask')['action']['param']['custom_action_param']['task']=='rewards'
            assert resource.get_node_data('MirrorBattleAssignment')['attach']['mode']=='saved'
            parsed.append(dict(case=case['name'],maximum=selected))
    assert all(hashlib.sha256((ROOT/'config'/name).read_bytes()).hexdigest()==hashes[name] for name in names)
    proof=dict(passed=True,native_cases=parsed,private_hashes=hashes,private_hashes_unchanged=True,
               isolated_scope=scope,device_controller=False,input_sent=False,installed_gui_verified=False,
               source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                   'assets/interface.json','assets/resource/base/pipeline/mirror.json','src/maalimbus/reward_task_budget.py')})
    write_json(ROOT/'build/reward-task-budget-native-verification.json',proof)
    print(json.dumps(proof))

if __name__=='__main__':main()
