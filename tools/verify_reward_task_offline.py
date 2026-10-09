"""Audit retained task execution with isolated state and zero device input."""
from pathlib import Path
import copy
import hashlib
import sys
import tempfile
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus import runner
from maalimbus.reward_task import execute,finish
from maalimbus.storage import read_json,write_json


def main():
    config=ROOT/'config'
    names=['user-run-ledger.json','user-reward-claim-transaction.json','user-mirror-settings.json','user-team-profiles.json']
    hashes={n:hashlib.sha256((config/n).read_bytes()).hexdigest() for n in names}
    with tempfile.TemporaryDirectory(prefix='maalimbus-reward-task-') as temporary:
        isolated=Path(temporary)
        for n in names:write_json(isolated/n,read_json(config/n))
        frame=ROOT/'evidence/runtime/window-20261009-093211/frame-0313.json'
        observer=SimpleNamespace(directory=frame.parent,observe=lambda **k:read_json(frame))
        clicks=[]
        old=runner.frame_file
        runner.frame_file=lambda directory:frame
        try:
            blocked=execute(isolated,frame.parent,observer,
                SimpleNamespace(click=lambda *p:clicks.append(p)),
                SimpleNamespace(record=lambda *a,**k:None))
        finally:runner.frame_file=old
        assert not blocked['passed'] and not blocked['input_sent'] and not clicks
        assert 'not authorized' in blocked['reason']
        assert all(hashlib.sha256((isolated/n).read_bytes()).hexdigest()==hashes[n] for n in names)
        tx=read_json(isolated/'user-reward-claim-transaction.json')
        scope=tx['scope'];assert scope=='d7c1499436f647208adc50860692a5c2'
        tx['completed']=False
        paths={'claim':'final-reward-authorized-claim-live','confirm':'final-reward-authorized-confirm-live',
               'receipt':'final-reward-receipt-ack-live','pass':'final-pass-receipt-ack-live'}
        tx['task_input_reports']={k:str(ROOT/f'build/{v}-20261008.json') for k,v in paths.items()}
        ledger=read_json(isolated/'user-run-ledger.json')
        ledger['active']=copy.deepcopy(next(r for r in ledger['receipts'] if r['id']==scope))
        ledger['active'].update(reward=False,events={})
        ledger.update(receipts=[],completed_runs=0)
        write_json(isolated/'user-run-ledger.json',ledger)
        write_json(isolated/'user-reward-claim-transaction.json',tx)
        complete=finish(isolated,scope,ROOT/'evidence/runtime/window-20261008-172705/frame-0001.json')
        assert complete['passed'] and read_json(isolated/'user-run-ledger.json')['completed_runs']==1
    assert all(hashlib.sha256((config/n).read_bytes()).hexdigest()==hashes[n] for n in names)
    proof=dict(passed=True,current_scope_budget_refused=blocked,isolated_retained_chain=complete,
               private_hashes=hashes,private_hashes_unchanged=True,device_input=False,
               native_gui_dispatch_verified=False,current_team_seven_payout_verified=False)
    write_json(ROOT/'build/reward-task-offline-real-verification.json',proof)
    print('Retained current-budget refusal and isolated task bookkeeping passed; zero device input.')

if __name__=='__main__':main()
