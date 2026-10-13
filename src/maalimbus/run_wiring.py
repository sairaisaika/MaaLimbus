"""Which observed page settles which completion event of the run ledger.

``maalimbus.storage.RunStore`` refuses an event that is out of order or that has no
proof, so the window must only offer events a page really proves. This module is that
mapping, kept pure so the rule can be tested without a device:

* a map page that reads floor *n* proves floor *n-1* was cleared -- the floor you are
  standing on is the one after the one you finished. Floor 1 proves nothing;
* the run summary (`RUN_CLAIM`, "Exploration Complete" at 100%) is the final victory,
  but only once all five floors are on the ledger, because that is what the summary
  itself is drawn from;
* reward confirmation is an input intent, never evidence of received rewards;
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
#: the weekly-bonus question's Confirm, from ``maalimbus.window``: the input that hands a
#: finished run's rewards over when only that question stands between the claim and them.
BONUS_CONFIRM_REASON = 'a_completed_run_spends_one_weekly_bonus_on_its_rewards'
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
        # Only a separate verified receipt/balance transaction may credit payout.
        return None
    if page == 'RUN_REWARD_BONUS' and reason == BONUS_CONFIRM_REASON:
        # A weekly bonus question also proves no receipt or resource balance change.
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


def reconcile(store, *, page, proof=None, note=None, on_event=None):
    """File a run the game no longer holds, when the team picker proves it is gone.

    The loadout picker is only drawn for a *new* dungeon: a run still in progress answers
    with the Dungeon Progress dialog ("Resume" / "Halt Exploration", live
    evidence/runtime/window-20261006-025617/frame-0002.json) instead of the picker. So
    reaching the picker while the ledger still calls a run active means the game has none
    -- the player accepted a wipe, or the run ended some other way -- and the ledger would
    otherwise keep a run that can never take a receipt, which also stops the next run from
    being opened at all (``settle`` only starts a run when the store has none).

    An abandoned run keeps the rotation where it stands, so the team that could not clear
    the floors is the team that tries again.
    """
    if page != 'DUNGEON_TEAM':
        return None
    active = (store.data or {}).get('active')
    if active is None:
        return None
    if active.get('phase') == 'preparing' and not any((active.get('floors'), active.get('events'),
                                                     active.get('victory'), active.get('reward'))):
        return None
    if active.get('phase') == 'entry_pending':
        raise ValueError('Entry confirmation pending; do not discard or retry')
    if not active.get('phase') and not any((active.get('floors'),active.get('events'),
                                          active.get('victory'),active.get('reward'))):
        raise ValueError('Empty legacy entry scope requires evidence migration')
    if active.get('victory') and active.get('reward') and proof is not None:
        # The run finished and its reward was already granted; the only thing missing is
        # the walk back to the entry, and a window that starts after the game drew the next
        # run's loadout can never see it. That completion is worth a receipt: recording the
        # return advances the rotation instead of throwing a finished run away. (The live
        # ledger reached this shape by accident -- run 476f23dc held floor 5 and its final
        # victory but no reward, so it was abandoned at 2026-10-08T00:39:35Z and the next
        # run came up on the same team; with the bonus question wired, the same sequence
        # now receipts the run before the picker is ever drawn.)
        fresh = store.record(active['id'], 'entry_returned-run', 'entry_returned', proof)
        filed = dict(active)
        filed['how'] = 'receipt'
        if on_event is not None and fresh:
            on_event(filed)
        return filed if fresh else None
    detail = note or ('the team picker was drawn with no dungeon in progress, so the run '
                      'the ledger still held was filed as abandoned')
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
    active = data.get('active') or {}
    if active.get('victory'):
        # The claim asking the question is this run's own payout: the ledger already holds
        # its five verified floors and its final victory, so the bonus was earned even
        # though the run has not been filed yet. Live run-continue-20 sat exactly there --
        # the window that filed the victory had stopped, and the next one was started after
        # it, so this is the only record the new window can read.
        return True
    receipts = data.get('receipts') or []
    if not receipts:
        return False
    receipt = receipts[-1]
    abandoned = data.get('abandoned') or []
    left_at = abandoned[-1].get('abandoned_at') if abandoned else None
    settled_at = receipt.get('settled_at')
    if abandoned:
        if not (left_at and settled_at):
            # A ledger written before receipts carried ``settled_at`` cannot say which
            # settled last -- live config/user-run-ledger.json held a team-4 receipt from
            # before the change and an expired run filed after it, and the old permissive
            # fallback spent one of three weekly bonuses on rewards that run never earned.
            # Not knowing is not a reason to spend a weekly resource.
            return False
        return settled_at > left_at
    return bool(receipt.get('victory') or receipt.get('reward'))


def reconcile_idle_entry(store, proof):
    """Retire a stale gameplay scope before native queue/settings application.

    Uses the newly observed frame, never the broad MIRROR_ENTRY classifier alone:
    an ongoing run can share its Enter/Exploring chrome. No reward is inferred.
    Unsettled receipts and entry inputs remain protected and are never erased.
    """
    import hashlib
    from pathlib import Path
    from .storage import read_json
    from .vision import Text, find
    from .team_vision import selected_saved_team
    if proof is None:raise ValueError('Fresh entry frame is missing; preserve the active run')
    proof=Path(proof)
    record=read_json(proof)
    if not isinstance(record,dict) or not isinstance(record.get('ocr'),list):
        raise ValueError('Fresh entry frame is malformed; preserve the active run')
    png=proof.with_suffix('.png')
    if hashlib.sha256(png.read_bytes()).hexdigest()!=record.get('image_sha256'):
        raise ValueError('Fresh entry screenshot hash differs; preserve the active run')
    import cv2
    image=cv2.imread(str(png));size=record.get('size')
    if image is None or size!=[image.shape[1],image.shape[0]]:
        raise ValueError('Fresh entry screenshot geometry differs; preserve the active run')
    texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
    page=record.get('scene')
    if record.get('overlay_dismissal'):
        return dict(retired=False,reason='entry_overlay_requires_normal_resolution')
    idle=(page=='MIRROR_ENTRY'
          and len(find(texts,r'^\s*Before\s+Entry\s*$',(.68,.10,.98,.32),size,.9))==1
          and len(find(texts,r'^\s*Enter\s*$',(.76,.55,.97,.85),size,.9))==1)
    picker=(page=='DUNGEON_TEAM' and selected_saved_team(texts,size) is not None
            and len(find(texts,r'^\s*Confirm\s*$',(.76,.70,.98,.96),size,.9))==1)
    if not idle and not picker:
        return dict(retired=False,reason='fresh_page_does_not_prove_no_active_dungeon',page=page)
    active=store.data.get('active')
    if active is None:return dict(retired=False,reason='ledger_already_idle',page=page)
    if active.get('phase')=='entry_pending':
        raise ValueError('Entry confirmation pending; preserve its original intent')
    path=store.path.parent/'user-reward-claim-transaction.json'
    claim=read_json(path) if path.exists() else {}
    if not isinstance(claim,dict):raise ValueError('Invalid payout state; preserve active run')
    if claim.get('scope')==active['id'] and (claim.get('pending') or not claim.get('completed')):
        raise ValueError('Current payout transaction remains pending; preserve its evidence')
    identity=active['id']
    if active.get('victory') and active.get('reward'):
        store.record(identity,'entry_returned-startup','entry_returned',proof)
        disposition='verified_reward_return'
    else:
        ended=dict(
            json=str(proof),json_sha256=hashlib.sha256(proof.read_bytes()).hexdigest(),
            png_sha256=record['image_sha256'],page=page,outcome_inferred=False)
        store.abandon(note='Fresh native idle entry proves the old dungeon is no longer active; '
                           'outcome/payout not inferred; evidence '+str(proof),ended_entry_proof=ended)
        disposition='ended_without_new_outcome_claim'
    return dict(retired=True,previous_scope=identity,page=page,disposition=disposition,
                game_input=False,completed_runs=store.data['completed_runs'])
