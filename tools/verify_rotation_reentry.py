"""Verify actual prior payout, Team7 header, once-only entry and independent successor."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import write_json
from maalimbus.team_vision import selected_saved_team
from maalimbus.vision import Text


def frame(path):
    path=Path(path);d=json.loads(path.read_text())
    assert hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()==d['image_sha256']
    return d


def main():
    prior=json.loads((ROOT/'build/final-reward-real-verification-20261008.json').read_text())
    ledger=json.loads((ROOT/'config/user-run-ledger.json').read_text());active=ledger['active']
    assert active['id']=='4734bfe68803421c8d261dccbc9120be' and active['team']==7 and active['phase']=='entered'
    assert ledger['rotation']==5 and ledger['completed_runs']==2
    receipt=next(r for r in ledger['receipts'] if r['id']=='d7c1499436f647208adc50860692a5c2')
    assert receipt['reward'] and receipt['victory'] and receipt['floors']==[1,2,3,4,5] and receipt['team']==2
    entry=active['entry'];before=frame(entry['before']);successor=frame(entry['successor'])
    assert selected_saved_team([Text(x['text'],tuple(x['box']),x['score']) for x in before['ocr']],before['size'])==7
    assert successor['scene']=='STAR_GRACES' and entry['successor_page']=='STAR_GRACES'
    confirmation=json.loads((ROOT/'evidence/runtime/window-20261008-190636/result.json').read_text())
    warning=json.loads((ROOT/'evidence/runtime/window-20261008-191203/result.json').read_text())
    for result,reason in ((confirmation,'dungeon_team_confirm_brings_the_chosen_team_in'),
                          (warning,'the_level_warning_proceeds_with_the_rotation_team')):
        assert result['clicks_sent']==1 and len(result['steps'])==1
        step=result['steps'][0];assert step['plan']['reason']==reason
        x,y,w,h=step['plan']['target'];px,py=step['click_point']
        assert x<=px<x+w and y<=py<y+h and 350<=step['delay_ms']<=750
    assert warning['run_ledger']['run']==active['id'] and entry['warning_sent']
    readonly=json.loads((Path(entry['successor']).parent/'result.json').read_text())
    assert readonly['clicks_sent']==0 and readonly['reason']=='stop_page_reached'
    assert readonly['run_ledger']['run']==active['id']
    report=dict(passed=True,device_input=False,prior_receipted_scope=receipt['id'],new_scope=active['id'],
        saved_rotation=5,previous_team=2,selected_team=7,reentry_proven=True,
        entry_page='STAR_GRACES',new_run_hard_mode_proven=False,
        new_floors_verified=[],new_reward_received=False,new_resource_consumption=0,
        old_scope_bug_preserved=True,scope_migration='build/rotation-entry-intent-real-verification-20261008.json',
        selected_png_sha256=before['image_sha256'],entry_png_sha256=successor['image_sha256'])
    write_json(ROOT/'build/rotation-reentry-real-verification-20261008.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
