"""Star grid uses frame edges/ordinals, never seasonal artwork or buff prose.

Lix 431b432 mirror_choose_star orders the grid left-to-right, top-to-bottom,
0..9; '+' and '++' are separate lower controls. Current 1920x1080 Maa frame
supplies normalized frame rectangles. Changed geometry fails closed.
"""
import cv2
from .vision import find


def page(records,size,locale):
    return (len(find(records,locale['star_select_all'],(.88,.66,.99,.75),size,.8))==1
        and len(find(records,locale['star_enhance_all'],(.88,.71,.99,.80),size,.8))==1
        and len(find(records,locale['enter'],(.88,.89,.99,.98),size,.85))==1)


def grid(image):
    h,w=image.shape[:2]
    if (w,h)!=(1920,1080):return None
    edge=cv2.Canny(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),50,150)
    boxes=[]
    for i in range(10):
        x,y,bw,bh=207+298*(i%5),226+356*(i//5),278,340
        strips=(edge[y:y+8,x:x+bw],edge[y:y+bh,x:x+8],edge[y:y+bh,x+bw-8:x+bw])
        if any(float((s>0).mean())<minimum for s,minimum in zip(strips,(.15,.07,.15))):
            return None
        boxes.append((x,y,bw,bh))
    return boxes


def cost_roi(box):
    x,y,w,h=box
    return (x+235,y+3,42,32)


def target_box(box):
    x,y,w,h=box
    # Upper card body; never the +/++ controls near the bottom.
    return (x+50,y+55,w-100,55)
