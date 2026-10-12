"""Candidate ordering replay only; a node still requires a live NODE_PANEL."""
import sys,json,hashlib
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.map_vision import map_clicks
path=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-112240/frame-0095.png'
pixels=cv2.imread(str(path));assert pixels is not None
original=map_clicks(pixels)
assert original[0]['kind']=='bright_lit_icon'
assert abs(original[0]['point'][0]-1089)<30 and abs(original[0]['point'][1]-576)<30
masked=pixels.copy();masked[545:615,1055:1125]=0
negative=map_clicks(masked)
assert not any(r['kind']=='bright_lit_icon' and abs(r['point'][0]-1089)<30
               and abs(r['point'][1]-576)<30 for r in negative)
assert all(.14*1080<=r['point'][1]<.84*1080 for r in original)
report=dict(passed=True,source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            original=original,masked=negative,device_input=False,node_success_verified=False)
(ROOT/'build/gui-map-candidate-replay-20261012.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,first=original[0],device_input=False)))
