"""Star grid uses frame edges/ordinals, never seasonal artwork or buff prose.

Lix 431b432 mirror_choose_star orders the grid left-to-right, top-to-bottom,
0..9; '+' and '++' are separate lower controls. Current 1920x1080 Maa frame
supplies normalized frame rectangles. Changed geometry fails closed.

The 2026-10 redesign keeps that 5x2 ordinal grid but redraws it: the borders are
thinner (measured 0.09-0.11 left and 0.02-0.04 right on live frame evidence
runtime/packaged-mirror-20261015-070250/frame-0010, inside cards the old .15/.07
floors refused) and the controls read with single-character slips ('Select All
Graces' -> 'Select Al Graoes' 0.92). Both are read the same way: try the proved
geometry and the exact locale pattern first, then look near it, and fail closed
when ten bordered cards or the page's three controls are not there.
"""
import cv2
from .vision import find, find_read

# The controls beneath the grid: locale key, printed phrase, band, score floor.
CONTROLS=(('star_select_all','Select All Graces',(.88,.66,.99,.75),.8),
    ('star_enhance_all','Enhance All',(.88,.71,.99,.80),.8),
    ('enter','Enter',(.88,.89,.99,.98),.85))

# Nominal 1920x1080 geometry the ordinal mapping was proved on.
X,Y,W,H,STEP,ROW=207,226,278,340,298,356
#: Card top, left and right border strips on the nominal box.
BORDER=(.15,.07,.15)
#: A boundary is looked for within this many pixels, at this measured floor.
SEARCH,FLOOR=24,.04


def page(records,size,locale):
    """The star page: its own three controls, exact locale pattern first."""
    for key,phrase,roi,threshold in CONTROLS:
        exact=find(records,locale[key],roi,size,threshold)
        if len(exact)==1:continue
        if exact or not find_read(records,phrase,roi,size,threshold):return False
    return True


def _density(strip):
    return float((strip>0).mean()) if strip.size else 0.0


def _nominal(edge,i):
    x,y=X+STEP*(i%5),Y+ROW*(i//5)
    return x,y,(edge[y:y+8,x:x+W],edge[y:y+H,x:x+8],edge[y:y+H,x+W-8:x+W])


def _look(strip):
    """The offset within +/-SEARCH whose strip carries the strongest border."""
    best,at=FLOOR,None
    for d in range(-SEARCH,SEARCH+1):
        density=_density(strip(d))
        if density>=best:best,at=density,d
    return at


def grid(image):
    """Ten card boxes: the proved geometry, else the bordered cards near it."""
    h,w=image.shape[:2]
    if (w,h)!=(1920,1080):return None
    edge=cv2.Canny(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),50,150)
    proved=[]
    for i in range(10):
        x,y,strips=_nominal(edge,i)
        if all(_density(s)>=f for s,f in zip(strips,BORDER)):proved.append((x,y,W,H))
    if len(proved)==10:return proved
    boxes=[]
    for i in range(10):
        x,y=X+STEP*(i%5),Y+ROW*(i//5)
        left=_look(lambda d:edge[y:y+H,x+d:x+d+8])
        right=_look(lambda d:edge[y:y+H,x+W-8+d:x+W+d])
        top=_look(lambda d:edge[y+d:y+d+8,x:x+W])
        if left is None or right is None or top is None:return None
        boxes.append((x+left,y+top,W,H))
    return boxes


def cost_roi(box):
    """The card's cost badge, in the box both clients draw it in.

    The badge moved with the 2026-10 redesign: it used to sit right-aligned (the
    readings the old box was proved on are offsets 202..274, evidence
    runtime/window-20261012-015054/frame-0005.json reading card 4's 20 at [1336,229]
    and again at [1306,230]) and now hangs left of that (live frame
    packaged-mirror-20261015-070250/frame-0010 reads card 1 at [394,236,56,32],
    digits from offset 205). The box spans both, and the starlight glyph that shares
    the new badge's OCR box stays just left of it.
    """
    x,y,w,h=box
    return (x+205,y+3,72,32)


def target_box(box):
    x,y,w,h=box
    # Upper card body; never the +/++ controls near the bottom.
    return (x+50,y+55,w-100,55)
