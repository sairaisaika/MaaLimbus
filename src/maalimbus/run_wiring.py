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
#: the expired-session page's Confirm, from ``maalimbus.window``.
EXPIRED_CONFIRM_REASON = 'the_expired_session_is_confirmed_so_its_rewards_are_claimed'


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


def settle(store, *, page, reason=None, floor=None, proof, on_event=None, on_refusal=None):
    """Record everything ``page`` settles, in order, and return what was recorded.

    One page can settle more than one thing in order: the run summary proves floor 5 was
    finished and then, on the next turn of this same loop, that the run was won. The
    store is re-read each round, so the loop stops the moment the page settles nothing
    more and the store keeps its own order.

    A run that has already taken its receipt leaves the store with no active run, and the
    next dungeon's first floor clear is what opens the run after it -- without that, a
    long window that walked straight into a second dungeon would silently stop recording
    the moment the first one was paid out.

    ``proof`` is the retained frame the ledger hashes; ``on_event(event)`` and
    ``on_refusal(event, error)`` are optional observers (the window journals both), and a
    refused event ends the loop instead of raising, because the ledger is the authority.
    """
    recorded = []
    while True:
        active = (store.data or {}).get('active')
        standing = active or dict(floors=[], victory=False, reward=False)
        event = ledger_event(page=page, reason=reason, floor=floor,
                             cleared=standing['floors'], victory=standing['victory'],
                             reward=standing['reward'])
        if event is None:
            break
        if active is None:
            store.start()
            active = (store.data or {}).get('active')
            if active is None:
                break
        event_id = '%s-%s' % (event.kind, 'run' if event.floor is None else event.floor)
        try:
            fresh = store.record(active['id'], event_id, event.kind, proof, floor=event.floor)
        except ValueError as error:
            if on_refusal is not None:
                on_refusal(event, error)
            break
        if not fresh:
            # The identical observation is already on the ledger; asking again would only
            # repeat it, so the page is done settling.
            break
        if on_event is not None:
            on_event(event)
        recorded.append(event)
    return recorded


def expire(store, *, page, reason=None, proof=None, note=None, on_event=None):
    """File the run the game threw away when it expired the session, or None.

    The weekly reset can end a dungeon in progress: the run is then invalidated and the
    next entry answers "The previous session has expired. / Please claim your rewards."
    (live evidence/runtime/window-20261007-170653/frame-0009.json). That run never
    reached floor 5, so it is abandoned rather than receipted -- the rotation stays on
    the same team for the next attempt, and the abandoned entry keeps the floors it had
    reached plus the frame that proved it.

    Confirming that page is what records this, because it is the input that claims the
    leftover rewards; any other page leaves the ledger alone.
    """
    if page != 'EXPIRED_SESSION' or reason != EXPIRED_CONFIRM_REASON:
        return None
    active = (store.data or {}).get('active')
    if active is None:
        return None
    detail = note or 'the game expired the session before the run reached floor 5'
    if proof is not None:
        detail = '%s; evidence %s' % (detail, proof)
    store.abandon(note=detail)
    if on_event is not None:
        on_event(active)
    return active


def earned_its_payout(store, *, settled_now=False):
    """True when the run being paid out is one that finished its floors.

    A claim can ask a second question -- "Spend your 'Weekly Bonuses, to claim the /
    bonus rewards?" (live evidence/runtime/window-20261007-171228/frame-0003.json, the
    frame a run the weekly reset expired is left with). Only three weekly bonuses exist,
    they reset every week and they do not carry over (Steam discussion
    597403944640085425), so the answer cannot come from the page itself: a receipt spends
    one, and a run the game expired or the player gave up keeps them.

    ``settled_now`` is the window's own memory of settling this run in this session; it
    covers the claim that happens right after the summary. Otherwise the newest settled
    record decides, by comparing the receipt's ``settled_at`` with the abandoned run's
    ``abandoned_at``.
    """
    if settled_now:
        return True
    if store is None:
        return False
    data = store.data or {}
    receipts = data.get('receipts') or []
    if not receipts:
        return False
    receipt = receipts[-1]
    abandoned = data.get('abandoned') or []
    left_at = abandoned[-1].get('abandoned_at') if abandoned else None
    settled_at = receipt.get('settled_at')
    if left_at and settled_at:
        return settled_at > left_at
    return bool(receipt.get('victory') or receipt.get('reward'))
