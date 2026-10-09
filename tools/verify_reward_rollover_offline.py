"""Prepare a retained native five-module offer in temporary state; no device."""
import hashlib
import tempfile
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.paid_reward_action import prepare


def main():
    root=Path(__file__).resolve().parents[1]
    scope='4734bfe68803421c8d261dccbc9120be'
    paths=[root/'config'/name for name in ('user-reward-claim-transaction.json',
        'user-mirror-settings.json','user-run-ledger.json')]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    replay=read_json(root/'build/team-seven-reward-cost-replay.json')
    directory=Path(replay['cases'][0]['evidence'])
    frames=list(directory.glob('frame-*.json'))
    assert len(frames)==1
    record=read_json(frames[0])
    with tempfile.TemporaryDirectory(prefix='maalimbus-reward-offline-') as name:
        isolated=Path(name)
        write_json(isolated/'user-mirror-settings.json',dict(max_reward_modules=5,
            module_budget_pending=False,reward_budget_scope=scope))
        write_json(isolated/'user-run-ledger.json',read_json(paths[2]))
        old=read_json(paths[0])
        write_json(isolated/'user-reward-claim-transaction.json',old)
        target=prepare('claim',record,isolated,scope,str(frames[0]))
        data=read_json(isolated/'user-reward-claim-transaction.json')
        assert data['history']==[old] and data['reserved_modules']==5
        assert not data['reward_received'] and data['claim_sent']
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    output=root/'build/reward-rollover-offline-verification.json'
    write_json(output,dict(passed=True,device_input=False,isolated_only=True,
        native_record=str(frames[0]),claim_target=target,scope=scope,
        old_transaction_preserved=True,live_budget_changed=False,
        current_receipt_verified=False,real_private_hashes=before))
    print(output)


if __name__=='__main__':main()
