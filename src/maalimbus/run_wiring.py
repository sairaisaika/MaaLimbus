"""Which observed page settles which completion event of the run ledger.

``maalimbus.storage.RunStore`` refuses an event that is out of order or that has no
proof, so the window must only offer events a page really proves. This module is that
mapping, kept pure so the rule can be tested without a device:

* a map page that reads floor *n* proves floor *n-1* was cleared -- the floor you are
  standing on is the one after the one you finished. Floor 1 proves nothing;
* the run summary (`RUN_CLAIM`, "Exploration Complete" at 100%) is the final victory,
  but only once all five floors are on the ledger, because that is what the summary
  itself is drawn from;
* the reward modal's own Confirm (`RUN_REWARD_CONFIRM`) is the claimed reward;
* the loadout picker's Confirm (`DUNGEON_TEAM`) is the entry returned, since it is the
  input that takes the rotated team back in.

Every event names the retained frame it came from, so the ledger stays evidence-backed
instead of trusting a page name on its own.
"""
from dataclasses import dataclass

#: the map page's only forward input in the window, from ``maalimbus.window``.
MAP_FORWARD_REASON = 'map_node_click_is_the_only_proven_forward_input'
#: the two inputs that settle the claim, from ``maalimbus.window``.
REWARD_CONFIRM_REASON = 'the_reward_claim_is_confirmed_and_never_cancelled'
ENTRY_CONFIRM_REASON = 'dungeon_team_confirm_brings_the_chosen_team_in'


@dataclass(frozen=True)
class LedgerEvent:
    """One completion event the ledger should record, with its floor if it has one."""

    kind: str
    floor: int | None = None


def ledger_event(*, page, reason=None, floor=None, cleared=(), victory=False,
                 reward=False, returned=False):
    """The event this observation settles, or None when it settles nothing.

    ``cleared``, ``victory``, ``reward`` and ``returned`` are what the ledger already
    holds, so the window never asks the store for an event it would refuse.
    """
    if returned:
        return None
    cleared = {int(f) for f in cleared}
    if page == 'MAP' and floor is not None:
        want = int(floor) - 1
        if 1 <= want <= 5 and want not in cleared and set(range(1, want)) <= cleared:
            return LedgerEvent('floor_clear', want)
        return None
    if page == 'RUN_CLAIM':
        # The summary is drawn from the whole run, so it is the only thing that can
        # prove floor 5 was finished -- there is no floor 6 to stand on. It then proves
        # the final victory on the next turn of the same loop, because the window keeps
        # asking until the page settles nothing more and the store keeps its order.
        # Live proof that this matters: build/window-run-continue-2.json reached
        # RUN_CLAIM (steps 52-55) and recorded nothing, so the rotation never moved.
        if set(range(1, 5)) <= cleared and not victory:
            if 5 not in cleared:
                return LedgerEvent('floor_clear', 5)
            return LedgerEvent('final_victory')
        return None
    if page == 'RUN_REWARD_CONFIRM' and reason == REWARD_CONFIRM_REASON:
        if victory and not reward:
            return LedgerEvent('reward_received')
        return None
    if page == 'DUNGEON_TEAM' and reason == ENTRY_CONFIRM_REASON:
        if reward:
            return LedgerEvent('entry_returned')
        return None
    return None
