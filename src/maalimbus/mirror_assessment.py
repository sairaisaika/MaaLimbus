"""Read-only completion scoring; never substitute predicted scores for receipts."""
from pathlib import Path
from .storage import read_json
from .learning_dataset import local_file,digest
from .run_summary import completed_hard_summary


def assess(root,ledger,proof):
    root=Path(root).resolve();run=read_json(local_file(root,ledger))['active']
    if not isinstance(run,dict):raise ValueError('An active evidence-backed run is required')
    evidence=read_json(local_file(root,proof))
    if evidence.get('scope')!=run.get('id') or evidence.get('team')!=run.get('team'):
        raise ValueError('Assessment scope/team mismatch')
    summary=evidence.get('summary',{})
    floors=run.get('floors')
    if (not isinstance(floors,list) or floors!=list(range(1,len(floors)+1)) or
        any(type(f) is not int for f in floors) or len(floors)>5 or summary.get('floors')!=floors or
        summary.get('difficulty')!='hard'):
        raise ValueError('Verified ordered Hard floors required')
    bindings=evidence.get('proofs',[])
    if not bindings:raise ValueError('Retained actual frame proof required')
    observed_summary=None
    for item in bindings:
        frame=local_file(root,item['frame']);image=local_file(root,str(frame.with_suffix('.png')))
        if digest(image)!=item.get('png_sha256') or read_json(frame).get('image_sha256')!=digest(image):
            raise ValueError('Actual assessment frame binding differs')
        actual=completed_hard_summary(read_json(frame))
        if actual is not None:observed_summary=actual
    if observed_summary!=summary:
        raise ValueError('Independent native Hard summary does not match assessment')
    victory=run.get('victory') is True and len(floors)==5 and summary.get('progress')==100
    # This verifier only proves completion; a separate receipt-chain audit must
    # supply payout. Never turn the summary's offer into an acquired reward.
    reward=False
    return dict(version=1,scope=run['id'],team=run['team'],difficulty='hard',
        progression_score=70*len(floors)/5+20*int(victory)+10*int(reward),
        components=dict(floors=len(floors),victory_verified=victory,reward_verified=reward),
        efficiency_score=None,survival_score=None,gift_causal_benefit=None,
        censored=True,strategy_training_eligible=False,
        limitation='Completion proof only; payout/HP/time/cost require separate independent evidence',
        evidence_sha256=digest(local_file(root,proof)),ledger_sha256=digest(local_file(root,ledger)),
        input_authorized=False,state_modified=False)
