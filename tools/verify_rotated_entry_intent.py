"""Adopt the one retained Team7 confirmation after the old empty-scope bug; no input."""
import copy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import write_json
from maalimbus.team_vision import selected_saved_team
from maalimbus.vision import Text


def retained(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    assert hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()==data['image_sha256']
    return data


def main():
    directory=ROOT/'evidence/runtime/window-20261008-190636'
    result=json.loads((directory/'result.json').read_text())
    assert result['pid']==63464 and result['clicks_sent']==1 and len(result['steps'])==1
    step=result['steps'][0]
    assert step['team']=={'wanted':7,'selected':7}
    assert step['plan']['reason']=='dungeon_team_confirm_brings_the_chosen_team_in'
    assert step['plan']['target']==[1632,853,170,52] and step['clicks_sent']==1
    x,y,w,h=step['plan']['target'];px,py=step['click_point']
    assert x<=px<x+w and y<=py<y+h and 350<=step['delay_ms']<=750
    before_path=directory/'frame-0001.json';before=retained(before_path)
    after=retained(directory/'frame-0002.json')
    assert before['image_sha256']==step['observation']['image_sha256']
    assert after['image_sha256']==step['settled']['image_sha256']
    assert selected_saved_team([Text(r['text'],tuple(r['box']),r['score']) for r in before['ocr']],before['size'])==7
    assert after['scene']=='LEVEL_WARNING'
    current_path=ROOT/'evidence/runtime/window-20261008-190951/frame-0001.json'
    current=retained(current_path)
    assert current['scene']=='LEVEL_WARNING'
    current_result=json.loads((current_path.parent/'result.json').read_text())
    assert current_result['observe_only'] and current_result['clicks_sent']==0
    ledger_path=ROOT/'config/user-run-ledger.json'
    ledger=json.loads(ledger_path.read_text());active=ledger['active']
    assert active['id']=='4734bfe68803421c8d261dccbc9120be' and active['team']==7
    assert not active['floors'] and not active['events'] and not active['reward'] and not active['victory']
    assert ledger['rotation']==5 and ledger['completed_runs']==2
    assert any(r['id']==result['run_ledger']['run'] and str(before_path) in r.get('note','')
               for r in ledger['abandoned'])
    assert not active.get('phase') and not active.get('entry')
    backup=ROOT/'build/rotation-entry-ledger-before-migration-20261008.json'
    assert not backup.exists()
    write_json(backup,ledger)
    corrected=copy.deepcopy(ledger)
    corrected['active'].update(phase='entry_pending',entry=dict(team=7,
        before=str(before_path),before_sha256=hashlib.sha256(before_path.read_bytes()).hexdigest(),
        confirm_sent=True,adopted_original_confirmation=True,
        original_report_scope=result['run_ledger']['run'],
        migration_reason='old reconcile abandoned a preparing scope before its input',
        confirmed_successor=str(directory/'frame-0002.json'),
        confirmed_successor_sha256=after['image_sha256'],current_readonly=str(current_path)))
    write_json(ledger_path,corrected)
    report=dict(passed=True,device_input=False,scope=active['id'],team=7,
        selected_team_proven=True,confirmation_once=True,entered_dungeon_proven=False,
        current_page='LEVEL_WARNING',history_preserved=True,backup=str(backup),
        before_png_sha256=before['image_sha256'],after_png_sha256=after['image_sha256'],
        current_png_sha256=current['image_sha256'])
    write_json(ROOT/'build/rotation-entry-intent-real-verification-20261008.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
