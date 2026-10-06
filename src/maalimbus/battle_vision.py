"""Experimental planning-page anchors; no turn submission or victory inference."""
from .theme_vision import ThemeCatalog
from .vision import find


class BattleCatalog(ThemeCatalog):
    def __init__(self, root):
        super().__init__(root, 'battle-catalog.json')


def planning_anchors(image, catalog, locale='en'):
    # Only the retained English label is available. Do not silently reuse it
    # as Japanese text validation. Lix locates skill glyphs at reference y560..600.
    if locale != 'en' or abs(image.shape[1]/image.shape[0]-16/9) > .02:
        return None
    buttons=catalog.matches(image,'win_rate',(.60,.65,1.,1.))
    if len(buttons)!=1:return None
    skills=[]
    width=image.shape[1]
    for kind in ('skill_slash','skill_pierce','skill_blunt'):
        for box in catalog.matches(image,kind,(0.,470/720,1.,625/720)):
            cx,cy=box[0]+box[2]/2,box[1]+box[3]/2
            if not 560/720<=cy/image.shape[0]<=600/720 or cx>=buttons[0][0]:continue
            if any(abs(cx-(b[0]+b[2]/2))<20*width/1280 for _,b in skills):
                return None
            skills.append((kind,box))
    if not 1<=len(skills)<=12:return None
    return {'win_rate':buttons[0],'skill_glyphs':sorted(skills,key=lambda s:s[1][0]),
            'scope':'pinned small English label and damage glyphs; experimental ROI, not full skill coverage'}


def preview_labels(records, size):
    # These are the upstream classifier's categories; text sightings are only
    # diagnostic. No coverage/assignment/survival proof follows from a few labels.
    result=[]
    for label in ('hopeless','struggling','neutral','favored','dominating'):
        for text in find(records,'^'+label+'$',(0.,.64,.90,.92),size,.85):
            result.append({'label':label,'box':text.box,'score':text.score,
                           'attention':label in ('hopeless','struggling','neutral')})
    return sorted(result,key=lambda t:t['box'][0])


def battle_hud(records, size):
    """Identify the combat HUD from its own WAVE/TURN captions.

    Both captions must appear exactly once in the top-left band. Their rendered
    values are gold bitmap glyphs that this OCR often misses, so a missing value is
    recorded as None rather than treated as a different page. Damage/Win-Rate
    readouts are diagnostics, never victory evidence.
    """
    wave = find(records, r'^WAVE$', (.0, .02, .06, .08), size, .85)
    turn = find(records, r'^TURN$', (.0, .06, .06, .13), size, .85)
    if len(wave) != 1 or len(turn) != 1:
        return None
    corner = [t for t in records
              if t.score >= .85 and t.text.strip()
              and .0 <= (t.box[0] + t.box[2] / 2) / size[0] <= .12
              and .0 <= (t.box[1] + t.box[3] / 2) / size[1] <= .16]
    wave_value = next((t.text.strip() for t in sorted(corner, key=lambda t: (t.box[1], t.box[0]))
                       if '/' in t.text), None)
    turn_value = next((t.text.strip() for t in sorted(corner, key=lambda t: (t.box[1], t.box[0]))
                       if t.text.strip().isdigit()), None)
    diagnostics = sorted(t.text.strip() for t in records
                         if t.score >= .85 and t.text.strip() in ('Win', 'Rate', 'Damage'))
    return {'wave': wave_value, 'turn': turn_value, 'wave_box': wave[0].box,
            'turn_box': turn[0].box, 'diagnostics': diagnostics,
            'scope': 'HUD identity only; no turn submission, coverage or victory claim'}
