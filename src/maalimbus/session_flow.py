"""Named live-session flows: the walk through the game, written down once.

Driving the live client by hand — one ``--click-box`` per screen and a screenshot
read after every one of them — is slow and impossible to repeat. A flow is that
same walk as data: an ordered list of :class:`Step`, each one a token to wait for
(or a fixed box), an optional click, and a bound. ``tools/window_step.py --flow``
turns a flow into Maa input; every decision a step makes is a pure function here,
so the tables are unit tested without a device.

Step kinds:

``start_app``
    hand the intent to the controller's own start-app call (never a desktop
    launcher: the only input channel is Maa's simulated touch).
``wait``
    read the screen until the pattern is on it, then move on. Nothing is sent.
``click``
    wait for the pattern, then click inside the token's own box. ``repeat``
    clicks it again while it is still there (a chain of popups), and
    ``optional`` means "it may already be gone" — the step is then skipped, not
    failed.

A step that never sees its token inside ``timeout_s`` fails the flow and the
runner stops there: a flow never guesses a coordinate for a control it has not
recognised, and it never sends a second input to a page that did not move.
"""
from dataclasses import dataclass

from .vision import Text, find

#: the Android package and the activity that owns the game window (read from
#: ``dumpsys window`` on the live device: mCurrentFocus after a fresh start).
PACKAGE = 'com.ProjectMoon.LimbusCompany'
ACTIVITY = 'com.ProjectMoon.LimbusCompany/com.ProjectMoon.LimbusCompany.LimbusCompanyActivity'
LAUNCH_INTENT = ACTIVITY

#: words a flow may never click on, whatever the pattern says. These are the
#: controls that end or refuse something the run owns: halting an exploration,
#: refusing a gift, cancelling an alarm, giving up a run.
FORBIDDEN_WORDS = ('halt', 'refuse', 'decline', 'cancel', 'quit', 'give up',
                   'close down', 'abandon', 'stop exploration')

#: how many times a repeating click step may fire before the chain is called stuck
MAX_REPEAT = 8


@dataclass(frozen=True)
class Step:
    id: str
    kind: str
    pattern: str | None = None
    roi: tuple | None = None
    threshold: float = .85
    box: tuple | None = None
    timeout_s: float = 90.0
    repeat: int = 1
    optional: bool = False
    note: str = ''


#: the walk from a cold client to the Mirror Dungeon mode card. Coordinates are
#: fractional frame boxes for the OCR band, and every token here was read on the
#: live 1920x1080 frames of 2026-10-06 (device space is 1280x720, Maa frames are
#: 1.5x that: build/live-menu.png, build/live-menu2.png, build/live-drive.png).
FLOWS = {
    'launch': (
        Step('start_app', 'start_app', timeout_s=180,
             note='Maa starts the package activity itself; no desktop launcher'),
        Step('title_text', 'wait', r'^TOUCH TO START$', (.36, .72, .62, .84), .70,
             timeout_s=240, note='cold boot sits on the title card'),
        Step('title_touch', 'click', r'^TOUCH TO START$', (.36, .72, .62, .84), .70,
             timeout_s=240),
        Step('home_menu', 'wait', r'^(?:LUNACY|Inventory|Dispense)$', (.25, .85, .85, .99),
             .70, timeout_s=300, note='main menu, whatever popup is on top of it'),
        Step('home_popup', 'click', r'^Confirm$', (.42, .68, .60, .82), .85,
             timeout_s=25, repeat=8, optional=True,
             note='patch notes and level-cap notices chain here and must be cleared '
                  'before the menu buttons answer'),
    ),
    'to_mirror': (
        Step('menu_drive', 'click', r'^Drive$', (.74, .86, .86, .95), .70,
             timeout_s=120, note='bottom-right Drive button -> dungeon selection'),
        Step('drive_mirror_mode', 'click', r'^Mirror Dungeons$', (.28, .33, .46, .48), .70,
             timeout_s=120, note='left column card; the subtitle carries the season name'),
    ),
    'enter_mirror': (
        Step('enter_button', 'click', r'^Enter$', (.80, .62, .93, .74), .70,
             timeout_s=120,
             note='live: build/live-entry3.png -- the guide overlay dims this button '
                  'until it is dismissed, and the panel only answers when it is lit'),
    ),
}


def flow(name: str) -> tuple:
    """The steps of a named flow. Unknown names raise ``KeyError``."""
    if name not in FLOWS:
        raise KeyError(name)
    return FLOWS[name]


def names() -> tuple:
    return tuple(FLOWS)


def token_of(records, size, step):
    """The token a step waits for, as ``{'text', 'box', 'score'}``, or ``None``.

    ``records`` is a frame's OCR token list as the journal writes it (a list of
    dicts); only the band in ``step.roi`` is searched, and a step without a band
    reads the whole frame. ``vision.find`` matches the token's centre and is
    case-insensitive, so a pattern here is written the way the game prints it.
    """
    if not records or not step.pattern:
        return None
    texts = [Text(item['text'], tuple(item['box']), item.get('score', 0.0))
             for item in records]
    hits = find(texts, step.pattern, step.roi or (0.0, 0.0, 1.0, 1.0), tuple(size),
                step.threshold)
    if not hits:
        return None
    hit = hits[0]
    return {'text': hit.text, 'box': list(hit.box), 'score': hit.score}


def center(box, ratio=.3):
    """A point inside the inset of a box: the click never lands on a border."""
    x, y, w, h = (int(value) for value in box)
    dx, dy = int(w * ratio / 2), int(h * ratio / 2)
    return (x + dx, y + dy, max(1, w - 2 * dx), max(1, h - 2 * dy))


def forbidden(step) -> str | None:
    """Why a step is not allowed to click, or ``None`` when it is allowed.

    A flow may not click a control that ends, refuses or cancels something the run
    already owns, even if its pattern would match: the check is on the step's own
    text, so it holds for flows nobody has written yet.
    """
    if step.kind != 'click':
        return None
    text = ' '.join(part for part in (step.pattern or '', step.note or '')).lower()
    for word in FORBIDDEN_WORDS:
        if word in text:
            return f'step {step.id} would click a forbidden control ({word!r})'
    return None


def validate(flow_name=None) -> list:
    """Structural problems with the tables, as a list of strings (empty is good).

    Run by the tests and by the tool before it touches a device: a flow whose box
    is malformed or whose step names collide is refused before any input is sent.
    """
    problems = []
    for name in ([flow_name] if flow_name else names()):
        steps = flow(name)
        seen = set()
        for step in steps:
            if step.kind not in ('start_app', 'wait', 'click'):
                problems.append(f'{name}.{step.id}: unknown kind {step.kind!r}')
            if step.id in seen:
                problems.append(f'{name}.{step.id}: duplicate step id')
            seen.add(step.id)
            if step.kind == 'start_app':
                continue
            if step.box is None and not step.pattern:
                problems.append(f'{name}.{step.id}: needs a pattern or a box')
            if step.box is not None:
                x, y, w, h = step.box
                if min(x, y, w, h) < 0 or w == 0 or h == 0:
                    problems.append(f'{name}.{step.id}: malformed box {step.box}')
            if step.roi is not None:
                x0, y0, x1, y1 = step.roi
                if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                    problems.append(f'{name}.{step.id}: roi outside the frame {step.roi}')
            if step.kind == 'click':
                if not 1 <= step.repeat <= MAX_REPEAT:
                    problems.append(f'{name}.{step.id}: repeat {step.repeat} out of range')
                refusal = forbidden(step)
                if refusal:
                    problems.append(f'{name}.{step.id}: {refusal}')
        if not steps:
            problems.append(f'{name}: empty flow')
    return problems
