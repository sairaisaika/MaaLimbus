"""Seven-sinner layouts must retain the lit-disc and caption gates."""
import json
from pathlib import Path
import cv2,pytest
from maalimbus.battle_vision import start_button
from maalimbus.vision import Text
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-180805'


def data(number):
    path=RUN/('frame-%04d.json'%number)
    if not path.exists():pytest.skip('Actual local battle frame unavailable')
    record=json.loads(path.read_text(encoding='utf-8'))
    rows=[Text(x['text'],tuple(x['box']),x['score']) for x in record['ocr']]
    return rows,record['size'],cv2.imread(str(path.with_suffix('.png')))


def test_shifted_lit_dial_is_bound_to_the_actual_assignment_captions():
    rows,size,image=data(157)
    rows=[r for r in rows if r.text!='START']
    target=start_button(rows,size,image)
    assert target is not None and 1590<=target[0]<=1630 and 100<=target[2]<=160
    assert start_button([r for r in rows if r.text!='Damage'],size,image) is None


def test_unassigned_dim_dial_stays_unavailable():
    rows,size,image=data(109)
    assert start_button(rows,size,image) is None


def test_a_readable_turn_still_gets_the_ring_as_a_last_look():
    """D151: captions locate the dial, they do not decide it exists."""
    import inspect
    import maalimbus.battle_vision as vision
    source = inspect.getsource(vision.start_button)
    tail = source.split("if hud.get('turn') is None:")[-1]
    assert 'submit_dial(image)' in tail, 'the ring is never tried on a turn-readable board'
