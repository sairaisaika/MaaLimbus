"""Text + normalized position; artwork and currency are never scene anchors."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Text:
    text: str
    box: tuple[int, int, int, int]
    score: float


def find(records, pattern, roi, size, threshold=.65):
    w, h = size
    matches = []
    for record in records:
        x, y, bw, bh = record.box
        cx, cy = (x + bw / 2) / w, (y + bh / 2) / h
        if record.score >= threshold and roi[0] <= cx <= roi[2] and roi[1] <= cy <= roi[3] and re.search(pattern, record.text, re.I):
            matches.append(record)
    return matches


def inset_box(box, ratio=.2):
    x, y, w, h = box
    dx, dy = int(w * ratio), int(h * ratio)
    return (x + dx, y + dy, max(1, w - 2 * dx), max(1, h - 2 * dy))


def classify(records, locale, size):
    # Tutorial overlays expose inactive underlying Enter/menu text.
    # Never treat those underlying labels as actionable entry evidence.
    # Live proof: evidence/runtime/window-20261006-023714/frame-0001.json is that
    # overlay — "Enter" and "Before Entry" are visible, yet a click on them did
    # nothing and the frame stayed byte-identical for 10 s (sha 830f27e4e62c...).
    if find(records, locale.get('tutorial', r'(?!)'), (.10,.30,.98,.85), size, .7):
        return 'TUTORIAL'
    # Shop/extraction/resource dialogs are separate tasks, never generic mirror buttons.
    forbidden = locale['forbidden_dialog']
    if find(records, forbidden, (.2, .15, .85, .85), size, .7):
        return 'RESOURCE_DIALOG'
    if find(records, locale['expired'], (.15, .1, .9, .85), size):
        return 'EXPIRED_SESSION'
    if find(records, locale['defeat'], (.15, .05, .9, .7), size):
        return 'DEFEAT'
    if (find(records,locale.get('gift_get',r'(?!)'),(.40,.21,.62,.29),size,.85)
        and len(find(records,locale['gift_confirm'],(.44,.70,.58,.78),size,.85))==1):
        return 'GIFT_GET'
    if find(records,locale.get('gift_get',r'(?!)'),(.40,.21,.62,.29),size,.75):
        return 'UNKNOWN_DIALOG'
    if (find(records,locale.get('gift_search_forgo',r'(?!)'),(.40,.45,.62,.51),size,.85)
        and len(find(records,locale['gift_confirm'],(.53,.65,.68,.73),size,.85))==1
        and len(find(records,locale.get('cancel',r'(?!)'),(.34,.65,.48,.73),size,.85))==1):
        return 'GIFT_SEARCH_FORGO'
    if (find(records,locale.get('star_confirm',r'(?!)'),(.38,.29,.63,.34),size,.85)
        and find(records,locale.get('star_convert',r'(?!)'),(.57,.48,.72,.53),size,.85)
        and len(find(records,locale['gift_confirm'],(.51,.71,.65,.77),size,.85))==1
        and len(find(records,locale.get('cancel',r'(?!)'),(.35,.71,.49,.77),size,.85))==1):
        return 'STAR_CONFIRM'
    if (find(records, locale.get('entry_confirm', r'(?!)'), (.30,.42,.70,.54), size,.85)
        and len(find(records, locale['enter'], (.53,.63,.67,.71), size,.85))==1
        and len(find(records, locale.get('cancel', r'(?!)'), (.34,.63,.48,.71), size,.85))==1):
        return 'ENTRY_CONFIRM'
    if (find(records,locale.get('level_warning',r'(?!)'),(.30,.30,.70,.41),size,.85)
        and find(records,locale.get('proceed_anyway',r'(?!)'),(.40,.38,.60,.44),size,.85)
        and len(find(records,locale['gift_confirm'],(.53,.64,.68,.72),size,.85))==1
        and len(find(records,locale.get('cancel',r'(?!)'),(.34,.64,.48,.72),size,.85))==1):
        return 'LEVEL_WARNING'
    # "Dungeon Progress" is the prompt a run that is already in progress shows
    # when you press Enter again. Live evidence
    # evidence/runtime/window-20261006-025617/frame-0002.json carries Resume,
    # Halt Exploration and Cancel. Halt Exploration throws the run away, so this
    # page must be named here instead of falling into the generic dialog veto.
    if (find(records, locale.get('resume_dialog', r'(?!)'), (.42, .29, .58, .35), size, .85)
        and find(records, locale.get('resume', r'(?!)'), (.45, .52, .55, .58), size, .85)
        and find(records, locale.get('halt_exploration', r'(?!)'), (.43, .58, .57, .64), size, .85)):
        return 'RESUME_DIALOG'
    # Encounter Reward Card is the pick-one screen a cleared node hands back. It
    # carries Cancel as well, so it has to be named before the generic dialog veto.
    # Live evidence evidence/runtime/window-20261006-034714/frame-0022.json.
    if (find(records, locale.get('encounter_reward', r'(?!)'), (.20, .12, .85, .25), size, .85)
        and find(records, locale.get('selectable', r'(?!)'), (.66, .13, .82, .25), size, .85)
        and find(records, locale['gift_confirm'], (.56, .68, .72, .78), size, .85)):
        return 'REWARD_CARD'
    if (find(records, locale.get('cancel', r'(?!)'), (.25,.25,.75,.80), size,.8)
        or find(records, locale.get('entry_confirm', r'(?!)'), (.30,.42,.70,.54), size,.8)):
        return 'UNKNOWN_DIALOG'
    if find(records,locale.get('gift_search',r'(?!)'),(.10,.02,.29,.10),size,.85):
        return 'GIFT_SEARCH'
    if (find(records,locale['acquire_gift'],(.06,.13,.95,.26),size,.8)
        and find(records,locale['gift_confirm'],(.77,.72,.97,.91),size,.8)):
        return 'FLOOR_GIFTS'
    # The Before Entry page is the concrete two-token exit from the mirror menu.
    # It has to stay after the tutorial veto above: the live overlay carries these
    # same two labels while the underlying Enter is inert.
    if (find(records, locale['enter'], (.76, .55, .97, .85), size)
        and find(records, locale['exploring'], (.68, .10, .96, .3), size)):
        return 'MIRROR_ENTRY'
    if find(records, locale['mirror_menu'], (.23, .25, .46, .55), size) and find(records, locale['inferno'], (.70, .07, .99, .3), size):
        return 'DRIVE'
    # The supplied Sinners page is a library, not the dungeon deployment page.
    if (find(records, locale['details'], (.6, .04, .95, .35), size)
        and find(records, locale['teams'], (.03, .08, .20, .8), size)
        and find(records, locale['sin_cost'], (.78, .05, .95, .24), size)):
        if (len(find(records,locale['gift_confirm'],(.82,.76,.96,.88),size,.85))==1
            and find(records,locale.get('bonus',r'(?!)'),(.83,.71,.94,.77),size,.8)):
            return 'DUNGEON_TEAM'
        return 'TEAM_LIBRARY'
    if (not find(records, locale['inferno'], (.70, .07, .99, .3), size)
        and find(records, locale.get('home_drive', r'(?!)'), (.73, .86, .81, .96), size)
        and find(records, locale.get('home_sinners', r'(?!)'), (.67, .86, .74, .96), size)
        and find(records, locale.get('home_window', r'(?!)'), (.61, .86, .68, .96), size)):
        return 'HOME'
    return 'UNKNOWN'
