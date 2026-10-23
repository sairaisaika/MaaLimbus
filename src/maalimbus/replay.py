"""The mechanical half of an offline replay: saved frames in, refusals out.

Thirty-nine tools under `tools/` verify recognisers and pipelines against retained
frames. Every one of them needs the same four answers from a controller -- is it
connected, what is its uuid, what features does it claim, what frame does it show
-- and the same promise: a replay never sends input. Ten of them wrote those
answers themselves, and the other twenty-nine inherit them by importing whichever
neighbour was at hand (seventeen through `verify_grace_balance_replay`), so the
promise was written ten times with ten different wordings and could drift in nine
directions without any test noticing.

This module owns the identical half. What stays with a tool is the half that is
not identical: which frame it shows (single, sequence, or one it rewrites between
packets), and what input it expects, if any. The rule the gate enforces is that
`connect`, `request_uuid`, `get_features` and `disconnect` have exactly one
implementation in the repository; `click`, `swipe`, the touch and key methods, and
`screencap` may be overridden because a scenario is allowed to know its own
expectation -- but an override that only refuses input is redundant, since
refusing is the default here.

`ReplayFrames` is the half that needs no Maa library (frames, refusals, records),
so the promise is testable without opening `maafw`; `ReplayController` adds the
`CustomController` base the pipeline expects.

Measured before this existed (2026-10-23): `tools/verify_*_replay.py` = 39 files,
10 of them defining their own `CustomController`, 29 inheriting `Replay` through a
`from verify_*_replay import Replay` line, and 4 uuid strings that named the tool
rather than the layer.
"""
from maa.controller import CustomController

# One uuid for the whole layer: a retained frame is not a game.
OFFLINE_UUID = 'maalimbus-offline-no-game'


class ReplayInputRefused(AssertionError):
    """A replay asked to send input it did not declare.

    It is an `AssertionError` on purpose: every call site that reached this before
    the layer existed raised `AssertionError`, and tests written against those
    tools must keep seeing the same failure, not a new exception type.
    """


class ReplayFrames:
    """Frames, refusals and records -- the half that needs no Maa library.

    A subclass provides the scenario half: `frame` (what `screencap` shows) and,
    where the scenario really does expect input, an `expects` callable taking
    `(kind, position, *args)` and returning whether that input is the one the
    scenario expects. Only an accepted input is recorded in `inputs`.
    """

    #: what `screencap` shows; a subclass may replace it with a sequence, or
    #: rewrite it between packets, by overriding `screencap` itself
    frame = None

    def __init__(self, frames=None, *, uuid=OFFLINE_UUID, expects=None):
        if frames is None:
            self.frames = []
        elif isinstance(frames, (list, tuple)):
            self.frames = list(frames)
        else:
            self.frames = [frames]
        if self.frames and self.frame is None:
            self.frame = self.frames[0]
        self.position = 0
        #: `uuid` is a read-only property on Maa's `Controller`, so a subclass
        #: may not assign it: an earlier version of this layer did, and every
        #: controller built on it raised `property 'uuid' has no setter` the
        #: moment a tool constructed one (found 2026-10-23 by running
        #: `tools/verify_city_gifts_replay.py`, not by the static inventory).
        self.scenario_uuid = uuid
        self.expects = expects
        self.inputs = []
        self.attempts = []
        # the name the retained-map replay used before this layer existed
        self.input_attempts = self.attempts

    # -- the identical half: one implementation in the whole repository --------

    def connect(self):
        return True

    def request_uuid(self):
        return self.scenario_uuid

    def get_features(self):
        return 0

    def disconnect(self):
        return True

    def screencap(self):
        frame = self.frame if self.frame is not None else (
            self.frames[min(self.position, len(self.frames) - 1)] if self.frames else None)
        if frame is None:
            raise ReplayInputRefused('a replay has no frame to show')
        return frame.copy()

    # -- the input half: refused unless the scenario says it is the expected one -

    def click(self, x, y):
        return self._input('click', int(x), int(y))

    def swipe(self, x1, y1, x2, y2, duration):
        return self._input('swipe', int(x1), int(y1), int(x2), int(y2), int(duration))

    def touch_down(self, contact, x, y, pressure):
        return self._input('touch_down', contact, int(x), int(y), pressure)

    def touch_move(self, contact, x, y, pressure):
        return self._input('touch_move', contact, int(x), int(y), pressure)

    def touch_up(self, contact):
        return self._input('touch_up', contact)

    def press_key(self, keycode):
        return self._input('press_key', int(keycode))

    def key(self, keycode):
        return self._input('key', int(keycode))

    def key_down(self, keycode):
        return self._input('key_down', int(keycode))

    def key_up(self, keycode):
        return self._input('key_up', int(keycode))

    def click_key(self, keycode):
        return self.key_down(keycode) and self.key_up(keycode)

    def _input(self, kind, *args):
        self.attempts.append((kind,) + args)
        if self.expects is None:
            raise ReplayInputRefused(
                'a replay that declared no expectation was asked to send %s%s' % (kind, args))
        if not self.expects(kind, self.position, *args):
            raise ReplayInputRefused(
                'a replay refused %s%s at frame %d' % (kind, args, self.position))
        self.inputs.append((kind,) + args)
        return True


class ReplayController(ReplayFrames, CustomController):
    """A Maa controller that answers from frames and refuses input by default."""

    def __init__(self, frames=None, *, uuid=OFFLINE_UUID, expects=None):
        CustomController.__init__(self)
        ReplayFrames.__init__(self, frames, uuid=uuid, expects=expects)


def blank_replay(size=(640, 640)):
    """A controller showing one empty frame, for a scene that reads no picture.

    Three tools kept their own `Offline` class for this: an `__init__` that made a
    zero frame and nothing else. A class whose whole body is "show zeros" is a
    factory, not a controller, so it lives here once (D54).
    """
    import numpy as np  # only the blank frame needs it, and only when asked for

    width, height = size
    return ReplayController(np.zeros((height, width, 3), dtype=np.uint8))
