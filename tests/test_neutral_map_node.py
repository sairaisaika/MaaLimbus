from pathlib import Path
import cv2
from maalimbus.map_vision import neutral_node_outlines,map_clicks

ROOT=Path(__file__).resolve().parents[1]


def test_retained_second_floor_white_cube_is_a_bounded_candidate():
    image=cv2.imread(str(ROOT/'evidence/runtime/packaged-mirror-20261012-101555/frame-0212.png'))
    assert image is not None
    points=neutral_node_outlines(image)
    assert any(830<x<945 and 230<y<335 for x,y in points)
    rows=map_clicks(image)
    assert any(r['kind']=='neutral_outline_candidate' and 830<r['point'][0]<945 for r in rows[:5])
    # Erasing the icon cannot keep its candidate, even with the same map layout.
    absent=image.copy();absent[220:340,825:950]=0
    assert not any(830<x<945 and 230<y<335 for x,y in neutral_node_outlines(absent))
