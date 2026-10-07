"""Which map spots have already had their turn on the floor being walked.

The window offers an ordered list of candidate boxes and stops at the first one that
opens the node panel, so a candidate that was swallowed must never be offered again --
otherwise the run burns its whole retry budget on the same first boxes. Live run
build/window-run110.json did exactly that on floor 3 "To be Cleaved": the floor reading
flickered 3 / None / 3 because a frame's header OCR dropped the floor token, every
flicker cleared the tried set, and the window re-clicked the same two 40x40 icons eight
times ([681,441], [748,416], [681,441], [748,416] ...) while the reachable "?" node at
[303,708] sat untried in the very same candidate list.

What resets the memory is a *named* floor change -- a new floor is a new layout -- never
a dropped reading. This module is that rule, kept pure so it can be tested offline.

A map visit also ends when the run walks off it and comes back. Live window
build/window-run-continue-4.json (floor 1 "The Outcast") clicked the offered "?" node,
which opened its panel, ran the event behind it and returned to the same map; the node
was still the page's forward step -- a manual tap on the same spot reopened its panel --
but the window had already spent it and walked the next nine speculative candidates to
no effect. So a step that settles on any page other than the map leaves the visit behind,
and the spots are offered again.
"""
from dataclasses import dataclass, field


@dataclass
class MapProgress:
    """The tried spots of the floor currently being walked."""

    floor: int | None = None
    tried: set = field(default_factory=set)

    def note_floor(self, floor):
        """Record this frame's floor reading and return the floor in force.

        Only a named floor that differs from the one in force starts a new floor; a
        ``None`` reading (the header OCR dropped or merged the token) keeps both the
        floor and the tried set, so a flickering reading cannot replay old candidates.
        """
        if floor is not None and floor != self.floor:
            self.floor = floor
            self.tried.clear()
        return self.floor

    def remaining(self, candidates):
        """The candidates whose turn has not come yet, in the order given."""
        return [box for box in candidates if tuple(box) not in self.tried]

    def note_click(self, box):
        """That spot has had its turn, whether or not it opened anything."""
        self.tried.add(tuple(box))

    def leave(self):
        """The run is no longer standing on the map, so the visit is over.

        Called when a step settles on a page other than the map. The floor is kept --
        a later frame of the same floor still reports it -- but the spots may be walked
        again, because the page that comes back can offer one of them as the next step.
        """
        self.tried.clear()
