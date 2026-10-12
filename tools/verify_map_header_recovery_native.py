"""Native caption/digit replays for the actual map glow failure, zero input."""
import json,sys,hashlib,re
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from maa.library import Library
from maa.resource import Resource
from maa.tasker import Tasker
from maa.pipeline import JRecognitionType,JOCR
from verify_sinner_neural_native import Offline
from maalimbus.jobs import wait_job
from maalimbus.theme_vision import ThemeCatalog
from maalimbus.vision import Text,find
from maalimbus.map_vision import HEADER_PATTERN


def main():
    Library.open(ROOT/'dist/MaaLimbus/maafw',agent_server=False)
    resource=Resource();wait_job(resource.post_bundle(ROOT/'assets/resource/base'))
    controller=Offline();wait_job(controller.post_connection())
    tasker=Tasker();assert tasker.bind(resource,controller)
    catalog=ThemeCatalog(ROOT/'assets/resource/base');rows=[]
    for name in ('packaged-mirror-20261012-101555/frame-0149.json','packaged-mirror-20261012-104758/frame-0080.json'):
        frame=ROOT/'evidence/runtime'/name;data=json.loads(frame.read_text(encoding='utf-8'))
        image=cv2.imread(str(frame.with_suffix('.png')))
        records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']]
        pack=find(records,r'^.{4,80}$',(.02,.17,.29,.215),data['size'],.9)
        assert len(pack)==1 and catalog.identity(pack[0].text)
        attempts=[]
        for negative in (False,True):
            pixels=image.copy()
            if negative:pixels[120:185,55:425]=0
            reads=[]
            for roi,expected in (((364,134,36,40),r'^[1-5]$'),((370,136,25,37),r'^[1-5]$'),((55,120,370,65),HEADER_PATTERN)):
                job=tasker.post_recognition(JRecognitionType.OCR,JOCR(roi=roi,only_rec=True,expected=[expected],threshold=.9),pixels)
                wait_job(job);d=job.get().nodes[-1].recognition
                reads.append([dict(text=r.text,score=r.score) for r in d.filtered_results] if d and d.hit else [])
            match=re.fullmatch(HEADER_PATTERN,reads[2][0]['text'],re.I) if len(reads[2])==1 else None
            agreement=bool(len(reads[0])==len(reads[1])==len(reads[2])==1 and match and match.group(1)
                and reads[0][0]['text']==reads[1][0]['text']==match.group(1))
            expected=(not negative and 'frame-0149' in name)
            assert agreement is expected
            attempts.append(dict(masked_negative=negative,readings=reads,agreement=agreement))
        rows.append(dict(frame=str(frame),image_sha256=hashlib.sha256(frame.with_suffix('.png').read_bytes()).hexdigest(),
                         original_scene=data['scene'],pack=pack[0].text,attempts=attempts))
    result=dict(passed=True,rows=rows,device_input=False,controller='offline CustomController')
    (ROOT/'build/map-header-recovery-native-20261012.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,cases=len(rows),device_input=False)))

if __name__=='__main__':main()
