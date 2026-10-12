"""Bounded Maa capture/OCR and optional single Sinners-menu touch; no team/gameplay task."""
import argparse,hashlib,json,random,sys,time
from datetime import datetime,timezone
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'agent')]
from maa.library import Library
from maa.toolkit import Toolkit
from maa.resource import Resource
from maa.tasker import Tasker
from maa.pipeline import JRecognitionType,JOCR,JActionType,JLongPress,JClick
from maalimbus.controller_lease import ControllerLease
from maalimbus.adb_device import discover,build,foreground_of
from maalimbus.jobs import wait_job
from maalimbus.storage import read_json,write_json
from maalimbus.vision import Text,classify,inset_box
from maalimbus.sinner_collection import home_sinners_target,reconcile,inventory_view_target
from maalimbus.overlay_dismissal import recognize as recognize_overlay
from recognition import Journal
from maalimbus.learning_dataset import local_file
from maalimbus.owned_inventory import recognize_filter, owned_page,observe_titles,reconcile_titles,sidebar_target


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb',type=Path,required=True);p.add_argument('--address',required=True)
    p.add_argument('--locale',choices=['en','jp'],default='en')
    actions=p.add_mutually_exclusive_group()
    actions.add_argument('--navigate-sinners',action='store_true')
    actions.add_argument('--dismiss-overlay',action='store_true')
    actions.add_argument('--open-sinner',type=int,choices=range(1,13),help='View one canonical sinner inventory; never equip')
    actions.add_argument('--switch-sinner',type=int,choices=range(1,13),help='Switch a verified owned-gallery sidebar filter only')
    a=p.parse_args();deadline=time.monotonic()+60
    names=['user-run-ledger.json','user-team-profiles.json','user-mirror-settings.json','user-reward-claim-transaction.json']
    hashes={n:hashlib.sha256((ROOT/'config'/n).read_bytes()).hexdigest() for n in names}
    directory=ROOT/'evidence/runtime'/('sinner-sample-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
    journal=Journal(directory);intent=ROOT/'build/sinner-collection-navigation.json'
    with closing(ControllerLease.acquire(ROOT/'build/controller.lock')):
        if a.navigate_sinners and intent.exists() and read_json(intent).get('pending'):
            raise ValueError('Unresolved collection input; capture only, never repeat it')
        Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
        Toolkit.init_option(ROOT/'build/sinner-capture-debug')
        binding=discover(a.address,a.adb);identity=foreground_of(binding)
        controller=build(binding,input_enabled=a.navigate_sinners or a.dismiss_overlay or a.open_sinner is not None or a.switch_sinner is not None)
        wait_job(controller.post_connection(),deadline=deadline)
        controller.set_screenshot_target_long_side(1920)
        resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'),deadline=deadline)
        wait_job(resource.post_bundle(ROOT/f'assets/resource/{a.locale}'),deadline=deadline)
        tasker=Tasker();assert tasker.bind(resource,controller)
        locale=read_json(ROOT/f'assets/resource/{a.locale}/locale.json')
        def native(kind,params,image):
            job=tasker.post_recognition(kind,params,image);wait_job(job,deadline=deadline)
            return job.get().nodes[-1].recognition
        def capture():
            foreground_of(binding)
            wait_job(controller.post_screencap(),deadline=deadline)
            image=controller.cached_image
            job=tasker.post_recognition(JRecognitionType.OCR,JOCR(threshold=.2),image)
            wait_job(job,deadline=deadline);reco=job.get().nodes[-1].recognition
            if reco is None:raise ValueError('Native OCR result absent')
            texts=[Text(x.text,tuple(x.box),x.score) for x in reco.filtered_results]
            scene=classify(texts,locale,[image.shape[1],image.shape[0]])
            closer=recognize_overlay(native,image,dict(scene=scene,size=[image.shape[1],image.shape[0]],
                ocr=[dict(text=t.text,box=list(t.box),score=t.score) for t in texts]))
            name=journal.frame(image,texts,scene,collection=True,neural_model_trained=False,overlay_dismissal=closer)
            frame=directory/(name+'.json');captured=read_json(frame)
            captured['owned_filter']=recognize_filter(native,image)
            try: sinner=owned_page(captured)
            except ValueError: sinner=None
            if sinner:
                captured['inventory_locale']=a.locale
                captured['inventory_observations']=observe_titles(native,image,captured,dict(
                    frame=str(frame),image_sha256=captured['image_sha256']))
                index=read_json(ROOT/'assets/resource/base/identity-index.json')
                captured['inventory_reconciliation']=reconcile_titles(index,sinner,
                    captured['inventory_observations'],a.locale)
            write_json(frame,captured)
            return directory/(name+'.json'),read_json(directory/(name+'.json'))
        before,record=capture();sent=False;settled=record
        inventory_intent=ROOT/'build/sinner-inventory-navigation.json'
        if inventory_intent.exists() and read_json(inventory_intent).get('pending'):
            state=read_json(inventory_intent)
            try: sinner=owned_page(record)
            except ValueError: sinner=None
            if sinner==state.get('sinner_index'):
                original=local_file(ROOT,state['before'])
                if (hashlib.sha256(original.read_bytes()).hexdigest()!=state['before_sha256'] or
                    hashlib.sha256(original.with_suffix('.png').read_bytes()).hexdigest()!=state['png_sha256']):
                    raise ValueError('Inventory original proof changed')
                if state.get('method')=='sidebar':sidebar_target(read_json(original),sinner)
                else:inventory_view_target(read_json(original),sinner)
                state.update(pending=False,observed_view='owned_identity_gallery',
                    successor=str(before),successor_json_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),
                    successor_png_sha256=record['image_sha256'],inventory_complete=False)
                write_json(inventory_intent,state)
        if not a.navigate_sinners and intent.exists():reconcile(ROOT,intent,before)
        overlay_input=False
        inventory_input=False
        if a.switch_sinner is not None:
            if inventory_intent.exists() and read_json(inventory_intent).get('pending'):
                raise ValueError('Unresolved inventory filter input; capture only')
            current=owned_page(record)
            if current!=a.switch_sinner:
                box=sidebar_target(record,a.switch_sinner);x,y,w,h=inset_box(tuple(box),.3)
                point=[random.randint(x,x+max(0,w-1)),random.randint(y,y+max(0,h-1))]
                duration=random.randint(350,750);foreground_of(binding)
                state=dict(pending=True,method='sidebar',sinner_index=a.switch_sinner,
                    before=str(before),before_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),
                    png_sha256=record['image_sha256'],target=box,point=point,delay_ms=duration,
                    prior=read_json(inventory_intent) if inventory_intent.exists() else None)
                write_json(inventory_intent,state);inventory_input=True
                wait_job(tasker.post_action(JActionType.Click,JClick(target=[*point,1,1])),deadline=deadline)
                time.sleep(duration/1000);time.sleep(1);after,settled=capture()
                if owned_page(settled)==a.switch_sinner:
                    state.update(pending=False,observed_view='owned_identity_gallery',successor=str(after),
                        successor_json_sha256=hashlib.sha256(after.read_bytes()).hexdigest(),
                        successor_png_sha256=settled['image_sha256'],inventory_complete=False)
                    write_json(inventory_intent,state)
        if a.open_sinner is not None:
            inventory_intent=ROOT/'build/sinner-inventory-navigation.json'
            if inventory_intent.exists() and read_json(inventory_intent).get('pending'):
                raise ValueError('Unresolved inventory view input; do not repeat')
            box=inventory_view_target(record,a.open_sinner);x,y,w,h=inset_box(tuple(box),.3)
            point=[random.randint(x,x+max(0,w-1)),random.randint(y,y+max(0,h-1))]
            duration=random.randint(350,750);foreground_of(binding)
            write_json(inventory_intent,dict(pending=True,sinner_index=a.open_sinner,
                before=str(before),before_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),
                png_sha256=record['image_sha256'],target=box,point=point,delay_ms=duration,
                prior=read_json(inventory_intent) if inventory_intent.exists() else None))
            inventory_input=True
            wait_job(tasker.post_action(JActionType.Click,JClick(target=[*point,1,1])),deadline=deadline)
            time.sleep(duration/1000)
            time.sleep(1);after,settled=capture()
        if a.dismiss_overlay and record.get('overlay_dismissal'):
            overlay_intent=ROOT/'build/sinner-collection-overlay-intent.json'
            if overlay_intent.exists() and read_json(overlay_intent).get('pending'):
                raise ValueError('Unresolved overlay dismissal; do not repeat')
            closer=record['overlay_dismissal'];x,y,w,h=inset_box(tuple(closer['box']),.3)
            point=[random.randint(x,x+max(0,w-1)),random.randint(y,y+max(0,h-1))]
            duration=random.randint(350,750);foreground_of(binding)
            state=dict(pending=True,before=str(before),before_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),
                png_sha256=record['image_sha256'],closer=closer,point=point,duration_ms=duration)
            write_json(overlay_intent,state);overlay_input=True
            wait_job(tasker.post_action(JActionType.LongPress,JLongPress(target=[*point,1,1],duration=duration)),deadline=deadline)
            for _ in range(3):
                time.sleep(1);after,settled=capture()
                if settled['scene'] not in ('TUTORIAL','UNKNOWN'):
                    state.update(pending=False,successor=str(after),successor_png_sha256=settled['image_sha256'])
                    write_json(overlay_intent,state)
                    if intent.exists():reconcile(ROOT,intent,after)
                    break
        if a.navigate_sinners:
            box=home_sinners_target(record)
            x,y,w,h=inset_box(tuple(box),.3)
            point=[random.randint(x,x+max(0,w-1)),random.randint(y,y+max(0,h-1))]
            duration=random.randint(350,750)
            foreground_of(binding)
            write_json(intent,dict(pending=True,expected_successor='TEAM_LIBRARY',
                before=str(before),before_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),
                png_sha256=record['image_sha256'],target=box,point=point,duration_ms=duration,
                collection_directory=str(directory)))
            sent=True
            wait_job(tasker.post_action(JActionType.LongPress,JLongPress(target=[*point,1,1],duration=duration)),deadline=deadline)
            for _ in range(3):
                time.sleep(1)
                after,settled=capture()
                if settled['scene']=='TEAM_LIBRARY':
                    reconcile(ROOT,intent,after);break
        assert all(hashlib.sha256((ROOT/'config'/n).read_bytes()).hexdigest()==hashes[n] for n in names)
        result=dict(directory=str(directory),foreground=identity,navigation_input_sent=sent,
            navigation_pending=intent.exists() and read_json(intent).get('pending') is True,scene=settled['scene'],
            overlay_dismissal_input_sent=overlay_input,
            inventory_view_input_sent=inventory_input,
            game_private_hashes_unchanged=True,team_edited=False,resources_spent=False,
            model_trained=False,training_label_verified=False)
        write_json(directory/'collection-result.json',result);print(json.dumps(result))


if __name__=='__main__':main()
