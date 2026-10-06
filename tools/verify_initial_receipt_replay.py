"""Maa free-gift acknowledgement replay; transition fixture explicitly derived."""
import argparse
import json
import os
import time
from pathlib import Path
import cv2
from verify_star_replay import ROOT, Replay, Library, Resource, Tasker, Journal, LimbusRecognition, LimbusTerminal, wait_job, wait_task, write_json
from recognition import InitialReceiptProof
from maalimbus.storage import read_json


class ReceiptReplay(Replay):
    def click(self,x,y):
        assert 935<x<1058 and 783<y<817
        self.clicks.append([x,y])
        if self.after is not None:self.frame=self.after.copy()
        return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--frame',required=True)
    p.add_argument('--last',action='store_true')
    args=p.parse_args();Library.open(args.binary,agent_server=False)
    original=cv2.imread(args.frame);assert original is not None
    derived=original.copy();derived[602:727,489:743]=(0,0,210)
    cv2.putText(derived,'Little and To-be-',(492,653),cv2.FONT_HERSHEY_SIMPLEX,.66,(235,235,235),2,cv2.LINE_AA)
    cv2.putText(derived,'Naughty Plushie',(497,686),cv2.FONT_HERSHEY_SIMPLEX,.66,(235,235,235),2,cv2.LINE_AA)
    results=[]
    cases=('unchanged','derived_unknown','changed_icon','missing_name','missing_confirm','wrong_order','pending','changed_proof','foreground_changed') if args.last else ('unchanged','derived_next','changed_icon','missing_name','missing_confirm','wrong_order','pending','changed_proof','foreground_changed')
    for case in cases:
        frame=original.copy();directory=ROOT/f'evidence/runtime/initial-receipt-replay-{time.time_ns()}-{case}'
        journal=Journal(directory);data=directory/'private-config';os.environ['MAALIMBUS_DATA_PATH']=str(data)
        if case=='changed_icon':frame[340:551,520:720]=0
        if case=='missing_name':frame[603:727,489:743]=0
        if case=='missing_confirm':frame[765:831,820:1108]=0
        progress=read_json(ROOT/'config/initial-gift-progress.json')
        if case=='wrong_order':progress['acknowledged']=[] if args.last else [progress['selected'][0]]
        if case=='pending':progress['receipt_pending']={'unknown':True}
        if case=='changed_proof':
            source=Path(progress['proof']);copy=directory/'changed-source.png';copy.write_bytes(source.read_bytes())
            metadata=read_json(source.with_suffix('.json'));metadata['image_sha256']='00'
            write_json(copy.with_suffix('.json'),metadata);progress['proof']=str(copy)
        write_json(data/'initial-gift-progress.json',progress)
        after=derived if case=='derived_next' else original*0 if case=='derived_unknown' else None
        rec=LimbusRecognition('en',journal);resource=Resource();controller=ReceiptReplay(frame,after)
        if case=='foreground_changed':
            def reject():raise RuntimeError('Foreground changed')
            rec.input_validator=reject
        resource.register_custom_recognition('limbus_scene',rec)
        resource.register_custom_action('limbus_terminal',LimbusTerminal(rec))
        resource.register_custom_action('limbus_initial_receipt_proof',InitialReceiptProof(rec))
        wait_job(resource.post_bundle(ROOT/'assets/resource/base'),timeout=20)
        wait_job(resource.post_bundle(ROOT/'assets/resource/en'),timeout=20)
        wait_job(controller.post_connection(),timeout=5);controller.set_screenshot_target_long_side(1920)
        tasker=Tasker();assert tasker.bind(resource=resource,controller=controller)
        result=wait_task(tasker,tasker.post_task('InitialReceipt',{'InitialReceipt':{'timeout':1000}}),deadline=time.monotonic()+8)
        positive=case in ('unchanged','derived_next','derived_unknown','changed_icon')
        assert len(controller.clicks)==int(positive),(case,controller.clicks,directory)
        events=[json.loads(l) for l in (directory/'events.jsonl').read_text().splitlines()]
        observations=[e for e in events if e['event']=='initial_receipt_ack_observation']
        assert bool(observations and observations[-1]['verified'])==(case=='derived_next'),(case,events)
        results.append(dict(case=case,clicks=controller.clicks,observations=observations,
            derived=case in ('derived_next','derived_unknown'),device_input=False,stop_confirmed=result['stop_confirmed']))
    report='initial-last-receipt-replay-verification.json' if args.last else 'initial-receipt-replay-verification.json'
    write_json(ROOT/'build'/report,dict(passed=True,cases=results,
        scope='retained Maa replay; patched next modal is synthetic, not actual gift receipt'))
    print(json.dumps(results))


if __name__=='__main__':main()
