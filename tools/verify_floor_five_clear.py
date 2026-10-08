"""Check real summary and reward modal hashes; no inputs or paid claim."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.run_summary import completed_hard_summary

def main():
    directory=ROOT/'evidence/runtime/window-20261008-144554'
    result=json.loads((directory/'result.json').read_text())
    ledger=json.loads((ROOT/'config/user-run-ledger.json').read_text())
    assert result['run_ledger']['run']==ledger['active']['id']
    assert result['run_ledger']['team']==ledger['active']['team']==2
    assert result['reason']=='reward_module_budget_pending'
    proofs=[]
    for index in (457,458,459):
        path=directory/f'frame-{index:04}.json';data=json.loads(path.read_text())
        sha=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()
        assert sha==data['image_sha256'];proofs.append(dict(frame=str(path),png_sha256=sha))
        if index==457:
            summary=completed_hard_summary(data);assert summary
    assert ledger['active']['floors']==[1,2,3,4,5] and ledger['active']['victory']
    assert not ledger['active']['reward']
    output=ROOT/'build/floor-five-real-verification-20261008.json'
    output.write_text(json.dumps(dict(scope=ledger['active']['id'],team=2,
        summary=summary,proofs=proofs,device_input=False,final_payout_verified=False),indent=2)+'\n')
    print(output)

if __name__=='__main__':main()
