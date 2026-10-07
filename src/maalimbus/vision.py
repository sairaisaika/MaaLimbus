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
    # Victory proof: 'VICTORY' is set in huge type on the result screen; the
    # archived frames read it at [732,432,470,213] score .999 and
    # [732,434,470,209] score 1.0 (evidence/runtime/window-20261006-105647/
    # frame-0066.json and frame-0067.json), so this band is tight around it and
    # the threshold is high on purpose.
    if find(records, locale.get('victory', r'(?!)'), (.33, .36, .68, .64), size, .85):
        return 'BATTLE_RESULT'
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
    # Leaving the shop asks first ("Leave the shop?" with X Cancel / Confirm). The
    # plain shop labels stay on screen behind it, so this veto has to sit above
    # SHOP or the confirm could never be reached.
    # Live evidence evidence/runtime/window-20261006-042529/frame-0002.json.
    if (find(records, locale.get('leave_shop_question', r'(?!)'), (.40, .40, .60, .56), size, .85)
        and find(records, locale['gift_confirm'], (.55, .63, .67, .74), size, .85)):
        return 'SHOP_LEAVE'
    # The Shop node hands back a shop instead of a battle. Leave is the only input
    # this project sends there: the module budget is 0, so nothing is bought.
    # Live evidence evidence/runtime/window-20261006-042123/frame-0001.json.
    if (find(records, locale.get('shop', r'(?!)'), (.10, .10, .30, .24), size, .85)
        and find(records, locale.get('leave', r'(?!)'), (.78, .82, .97, .96), size, .85)):
        return 'SHOP'
    # Pressing Select with choices left over raises this warning on top of the pick
    # page ("You have remaining E.G.O Gift choices. Will you proceed without selecting
    # an E.G.O Gift?"). Its Confirm trades the gifts for random Trials, so the page has
    # to be named -- and its Cancel is the input this project sends -- before both the
    # pick page underneath and the generic dialog veto claim the frame.
    # Live evidence evidence/runtime/window-20261006-052152/frame-0003.json.
    if (find(records, locale.get('gift_warning_proceed', r'(?!)'), (.32, .38, .72, .52), size, .85)
        and find(records, locale.get('gift_warning_remaining', r'(?!)'), (.34, .34, .68, .46), size, .85)):
        return 'GIFT_WARNING'
    # The floor's gift pick ("Acquire E.G.O Gift" cards + Select N/1 + Refuse Gift)
    # hands the run its floor rewards. Refuse Gift is a forbidden input, so the page
    # has to be named before the generic dialog veto and before FLOOR_GIFTS (which
    # wants a plain Confirm the live page does not carry).
    # Live evidence evidence/runtime/window-20261006-043102/frame-0003.json.
    # The Select caption itself is not required: on the live three-card round the OCR
    # reads its counter as a lone low-score "1" (window-20261006-203033/frame-0001.json,
    # score 0.44) and the button text is missed, while the card label and Refuse Gift
    # both read cleanly, so those two identify the page.
    if (find(records, locale.get('gift_pick_label', r'(?!)'), (.06, .13, .95, .26), size, .85)
        and find(records, locale.get('refuse_gift', r'(?!)'), (.62, .74, .82, .88), size, .85)):
        return 'GIFT_PICK'
    # The event's skill check ("Who should do it?" / "Choose a character to perform the
    # check with:") asks which identity takes the roll, and prints each identity's odds
    # over its card. It carries the same bottom-right SKIP as the cutscene, so it has to
    # be named before that branch. Live: evidence/runtime/window-20261006-204421/
    # frame-0001.json reads 'Who should do it?' [1294,275,232,28] and 'Choose a
    # character to perform' [1278,442,402,36], with 'Threshold', 'Predicted' and the
    # twelve odds captions below them. The question alone names the page: a sparser OCR
    # pass over the same page (evidence/runtime/window-20261006-204143/frame-0002.json)
    # returns only four tokens -- the question, the advantage line and SKIP -- and the
    # prompt's second line is simply absent. No other page prints that question, and
    # nothing else on this page distinguishes it from the cutscene, so requiring the
    # second line would hand the page back to the cutscene branch and press SKIP on a
    # check the run should have attempted.
    # The question is worded several ways across encounters, and a sparser OCR pass drops
    # the prompt's second line, so the page is named by whichever of the question or the
    # chooser caption the pass managed to read. Once an identity is picked the page asks
    # "What will you do?" over the prediction instead (evidence/runtime/
    # window-20261006-235032/frame-0013.json, whose bottom-right control is Commence).
    if (find(records, locale.get('who_should_do_it', r'(?!)'), (.62, .23, .82, .30), size, .85)
            or find(records, locale.get('who_will_take_the_challenge', r'(?!)'),
                    (.62, .23, .82, .30), size, .85)
            or find(records, locale.get('what_will_you_do', r'(?!)'),
                    (.62, .23, .82, .30), size, .85)
            or find(records, locale.get('choose_character', r'(?!)'),
                    (.63, .38, .90, .47), size, .85)):
        return 'EVENT_CHECK'
    # The event's "Choices" page (abnormality events) puts two to four option rows in
    # the right-hand column. Any row advances, but the rows are read live because
    # their number moves them, so the page is named here and its rows come from OCR.
    # It has to be named before the cutscene branch: the choices page keeps the
    # story playback's REC badge and its SKIP button, so a cutscene test placed first
    # swallows it (live build/window-run31.json: the SKIP press handed back
    # evidence/runtime/window-20261006-051213/frame-0002.json, which reads Choices
    # 1.0, REC 1.0 and SKIP 1.0 together).
    # Live evidence evidence/runtime/window-20261006-044943/frame-0015.json.
    if (find(records, locale.get('choices', r'(?!)'), (.50, .11, .68, .24), size, .85)
        and len(find(records, r'.+', (.52, .24, .99, .72), size, 0)) >= 2):
        return 'EVENT_CHOICE'
    # The event's outcome page keeps the REC badge of the story playback and adds a
    # "Result" panel on the right. Its bottom-right control is the same slot the
    # cutscene uses, and it stays dimmed until the story has been tapped through, at
    # which point that slot carries a bright "Continue": live
    # evidence/runtime/window-20261006-045451/frame-0001.json (dim, no button token)
    # becomes frame-0002.json ("Continue" 1.0 at [1588,943,218,55]). It therefore has
    # to be named before CUTSCENE, which also sees REC and SKIP. The Result panel alone
    # names the page: the live signboard event reaches this page with a bright
    # "Proceed" [1594,945,206,49] and no readable REC badge at all, and a page that
    # shows a Result panel is this page whether or not the badge was read.
    if find(records, locale.get('result', r'(?!)'), (.48, .11, .66, .24), size, .85):
        if find(records, locale.get('continue', r'(?!)'), (.78, .82, .99, .98), size, .85):
            return 'EVENT_RESULT_READY'
        return 'EVENT_RESULT'
    # The skill check resolves on a page of its own: the outcome panel prints
    # "Check Passed"/"Check Failed" over the threshold it beat, and the story that follows
    # plays inside the left panel while the bottom-right control stays dark. Live
    # evidence/runtime/window-20261006-210803/frame-0001.json reads 'Check Passed'
    # [1294,722,212,34] beside 'E.G.O Gift Crown of Roses obtained!' with no readable
    # bottom-right control at all; tapping that panel is what lights the control up
    # (frame-0002.json of the same window reads 'Continue' [1588,941,220,59] there), and
    # the user's rule for it (m10140) is to keep tapping the small screen until it does.
    # So the dark form is named here and the lit one is named below, ahead of the cutscene
    # branch that owns the same slot's SKIP. The pre-roll check page prints 'Predicted'
    # instead, so it can never be mistaken for this one.
    if find(records, locale.get('check_outcome', r'(?!)'), (.66, .65, .80, .72), size, .85):
        if find(records, locale.get('continue', r'(?!)'), (.78, .82, .99, .98), size, .85):
            return 'EVENT_CHECK_READY'
        if not find(records, locale.get('skip', r'(?!)'), (.78, .82, .99, .98), size, .85):
            return 'EVENT_CHECK_RESULT'
    # A cutscene (abnormality intro, event story) covers the screen with a REC badge
    # and a single SKIP button, and it waits for input instead of advancing: live
    # window-20261006-044556 sat on it for over a minute with the text already complete
    # ("Clopping like a spider, it talks to me."). Skipping is that page's own forward
    # control, so it must be named rather than left as an unknown page. The SKIP button
    # alone names it: the live event story (window-20261006-203xxx, "What does this
    # signboard say?") carries SKIP at [1618,919,154,99] with no readable REC badge, and
    # the choices page that also carries SKIP is named ahead of this branch.
    if find(records, locale.get('skip', r'(?!)'), (.78, .82, .99, .98), size, .85):
        return 'CUTSCENE'
    if (find(records, locale.get('cancel', r'(?!)'), (.25,.25,.75,.80), size,.8)
        or find(records, locale.get('entry_confirm', r'(?!)'), (.30,.42,.70,.54), size,.8)):
        return 'UNKNOWN_DIALOG'
    if find(records,locale.get('gift_search',r'(?!)'),(.10,.02,.29,.10),size,.85):
        return 'GIFT_SEARCH'
    # A gift the run just picked up opens its own modal over the map: the "E.G.O Gifts"
    # title, the gift's name, a "View Desc." button and a Confirm along the bottom.
    # Live: evidence/runtime/window-20261006-201621/frame-0001.json reads 'E.G.O Gifts'
    # [832,170,256,58], 'Wound Clerid' [546,327,252,42], 'View Desc.'
    # [482,428,152,38] and Confirm [916,825,126,40] over the map behind it.
    if (find(records, locale.get('ego_gifts', r'(?!)'), (.42,.14,.60,.23), size,.85)
        and find(records, locale.get('gift_confirm', r'(?!)'), (.45,.73,.56,.81), size,.85)):
        return 'EGO_GIFT_POPUP'
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
