"""Page-to-action planning for a bounded live verification window.

A window is one continuous live session that walks the dungeon loop and records
every page it meets, so that pages which can only be confirmed by looking at the
screen are confirmed once, in one batch, and afterwards the script works from
recorded numbers and anchors only.

The driver (``tools/window_step.py``) reads one fresh page, asks this module for
the single input it may send next, sends it, and then compares the successor page
against the expected set. The table lives here so it can be unit tested without a
device, and so the same reasoning can be lifted into agent pipeline actions later.

Rules encoded here:

* a page never sends more than one input per plan;
* a page with no proven control refuses instead of guessing a coordinate;
* a click is only accepted when the successor page is one of the expected pages,
  otherwise the step is recorded as ``unexpected_successor`` and the window stops;
* battle turns are submitted only when the game itself shows ``START``.
"""

from __future__ import annotations

CLICK = 'click'
SWIPE = 'swipe'
NODE = 'node'
RECORD = 'record'

#: expectation sentinel for a dismissal: the successor is proven by the covered
#: page being gone, not by which page it uncovered. The overlay's cards walk
#: through many different pages, so no positive list can name them all, but
#: "still the overlay" is a decidable failure.
ANY = '*'

#: pages that end the walk: a fresh observation is taken and the window stops.
OBSERVE_ONLY = ('SHOP', 'EVENT_DIALOG', 'REWARD_SETTLE', 'FLOOR_GIFTS',
                'BATTLE_RESULT', 'UNKNOWN')

#: pages whose only input is an existing, already proven pipeline node.
PAGE_NODES = {'DRIVE': 'WindowDrive'}

#: controls a window must never click, whatever else is on the same page. Halt
#: Exploration throws an in-progress run away, and Cancel on the encounter reward
#: page refuses a reward the run has already earned, so both stay registered as
#: anchors (their labels are how the page is identified) but are refused as targets.
#: The entry confirmation's X Cancel is the same shape: the run is already free to
#: start and cancelling it costs the step, not the run. The skill check's SKIP is the
#: fourth shape: it means nobody attempts the roll, which forfeits the check outright,
#: so it stays registered as an anchor but is never a target.
FORBIDDEN_CONTROLS = ('resume.halt_button', 'reward_card.cancel_button',
                      'gift_pick.refuse_button', 'gift_warning.confirm_button',
                      'entry_confirm.cancel_button', 'level_warning.cancel_button',
                      'star_confirm.cancel_button', 'initial_gifts.refuse_button',
                      'gift_search_forgo.cancel_button', 'event_check.skip_button',
                      # The reward modal's Give Up Rewards throws the five-floor run away.
                      'run_reward.give_up_button',
                      # Cancelling the claim question dismisses it without claiming.
                      'run_reward_confirm.cancel_button',
                      # The weekly reset notice's Confirm leaves the dungeon for the
                      # Window, which throws the run in progress away.
                      'window_reset.confirm_button',
                      # Dismissing the expired session leaves its rewards unclaimed.
                      'expired_session.cancel_button')

#: Pages that clear themselves: the planner has no control to send, so the driver
#: waits for the page to change instead of treating it as the end of the run.
#: Live: build/window-run62.json stopped on BATTLE_RESULT (step 31) with nothing sent,
#: and the very next observation already showed the post-battle story and then the map
#: ("Exploring Floor 1" / "Flat-broke Gamblers"), so the result screen needs no click.
#: DEFEAT is the same kind of page and is on the list for the same reason: live
#: evidence/runtime/window-20261007-195545/frame-0222.json (00:10:26) reads the DEFEAT
#: banner [726,434,470,225] over Gebura's 'All of your employees are dead.' with no rows
#: on screen yet, and run-continue-18 stopped there ('page_is_observe_only') while the
#: game was still drawing the stage-failure dialog that follows it - the dialog is
#: BATTLE_DEFEAT and that page is the one with a plan and a bounded retry count.
WAIT_PAGES = ('UNKNOWN', 'BATTLE_RESULT', 'DEFEAT')


def resolve_overlay(page, *, overlay_hit):
    """Return the page the tutorial overlay covers, while its control is visible.

    Live proof: ``evidence/runtime/window-20261006-024050/frame-0002.json`` is the
    overlay's second card ("Weekly Bonuses"). The OCR token only knew the first
    card, so the covered entry page was planned and its inert ``Enter`` swallowed
    the step. The overlay's own continue control does not change from card to
    card, so a visible continue control outranks the label underneath it.
    """
    return 'TUTORIAL' if overlay_hit else page


def _plan(page, action, *, target=None, node=None, expect=(), reason, detail=None,
          advance=False, to=None, duration=None):
    plan = {'page': page, 'action': action,
            'target': None if target is None else list(target),
            'node': node, 'expect': list(expect), 'reason': reason,
            'advance': bool(advance)}
    if to is not None:
        plan['to'] = list(to)
    if duration is not None:
        plan['duration_ms'] = int(duration)
    if detail is not None:
        plan['detail'] = detail
    return plan


def _refuse(page, reason):
    return _plan(page, RECORD, reason=reason)


def plan_step(page, *, controls=None, start_box=None, auto_assign=None,
              candidates=None, candidate_index=0, nodes=None, arrows=None, team=None,
              reward=None, gift=None, cards=None, graces=None, initial=None,
              search=None, check=None, defeat=None, bonus=None, difficulty=None):
    """Return the one input (or the refusal) allowed on ``page``.

    A plan that would land on a control in :data:`FORBIDDEN_CONTROLS` is refused
    here, so a mis-registered anchor can never abandon a run by itself.
    """
    controls = controls or {}
    plan = _plan_step(page, controls=controls, start_box=start_box,
                      auto_assign=auto_assign, candidates=candidates,
                      candidate_index=candidate_index, nodes=nodes, arrows=arrows,
                      team=team, reward=reward, gift=gift, cards=cards, graces=graces,
                      initial=initial, search=search, check=check, defeat=defeat,
                      bonus=bonus, difficulty=difficulty)
    forbidden = {tuple(box) for name, box in controls.items()
                 if name in FORBIDDEN_CONTROLS and not (
                     page=='STAR_CONFIRM' and name=='star_confirm.cancel_button'
                     and plan.get('reason')=='incomplete_graces_return_to_selection')}
    if plan.get('target') and tuple(plan['target']) in forbidden:
        return _refuse(page, 'control_is_forbidden')
    return plan


def _plan_step(page, *, controls=None, start_box=None, auto_assign=None,
               candidates=None, candidate_index=0, nodes=None, arrows=None, team=None,
               reward=None, gift=None, cards=None, graces=None, initial=None,
               search=None, check=None, defeat=None, bonus=None, difficulty=None):
    """Return the one input (or the refusal) allowed on ``page``.

    ``controls`` maps anchor names such as ``node_panel.enter_button`` to pixel
    boxes; ``start_box`` and ``auto_assign`` come from the battle observation;
    ``candidates`` are node boxes read from the live map frame; ``nodes`` maps a
    page to an existing pipeline node that already carries its own proven
    recognition and click box; ``team`` carries the pre-battle page's per-card
    participation badges; ``reward`` carries the encounter reward page's pick
    counter (``{'chosen': n, 'required': m}``); ``check`` carries the skill check's
    chosen slot (``{'slot': n, 'tier': t, 'box': [x, y, w, h]}``).
    """
    controls = controls or {}
    nodes = dict(PAGE_NODES, **(nodes or {}))
    if page=='DEPLOYMENT_RESET':
        box=controls.get('deployment_reset.confirm')
        if box is None or not (team or {}).get('reset_pending'):
            return _refuse(page,'deployment_reset_pending_intent_not_proven')
        return _plan(page,CLICK,target=box,expect=('PRE_BATTLE_TEAM',),
                     reason='confirm_pending_deployment_reset_once')
    if page == 'HOME':
        box = controls.get('home.drive_button')
        if box is None:
            return _refuse(page, 'drive_button_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('DRIVE', 'MIRROR_ENTRY', 'THEME_PACKS', 'MAP', 'UNKNOWN'),
                     reason='drive_nav_is_the_proven_way_back_to_the_mirror_menu')
    if page == 'DRIVE':
        node = nodes.get('DRIVE')
        if node is None:
            return _refuse(page, 'mirror_menu_node_not_registered')
        return _plan(page, NODE, node=node,
                     expect=('MIRROR_ENTRY', 'DRIVE', 'THEME_PACKS', 'MAP',
                             'EXPIRED_SESSION', 'UNKNOWN'),
                     reason='mirror_menu_recognition_owns_the_click_box')
    if page == 'EXPIRED_SESSION':
        # The weekly reset can end a run in progress: entering the mirror dungeon then
        # answers with "The previous session has expired. / Please claim your rewards."
        # (live evidence/runtime/window-20261007-170653/frame-0009.json, the page the
        # run-continue-9 window landed on at step 2). Its Confirm is the only control
        # that pays the run out; Cancel would leave those rewards unclaimed, so Cancel is
        # registered as an anchor and forbidden as a target.
        box = controls.get('expired_session.confirm_button')
        if box is None:
            return _refuse(page, 'expired_session_confirm_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_expired_session_is_confirmed_so_its_rewards_are_claimed')
    if page == 'TUTORIAL':
        # ``arrows`` comes from the live frame (maalimbus.overlay_vision): the two
        # page-turn triangles move, and the book's last page shows only ``previous``
        # (live: evidence/runtime/window-20261006-030152/frame-0014.png), where a
        # fixed right-edge box clicks empty space and proves nothing.
        #
        # The book's own header arrow in the top-left corner is tried first: it closes
        # the whole guide, while its ▶ only ever turns one page. The player pointed
        # this out after a run turned eleven pages without reaching the team page
        # underneath (build/window-run50.json).
        arrows = arrows or {}
        close = controls.get('tutorial.book_close')
        if close is not None:
            return _plan(page, CLICK, target=close, expect=(ANY,), advance=True,
                         reason='tutorial_book_is_closed_from_its_own_header_arrow')
        if arrows.get('next'):
            box = arrows['next']
        elif arrows:
            box = None
        else:
            box = controls.get('tutorial.next_button')
        if box is None:
            if arrows.get('previous'):
                # Last card of the book: there is no forward page-turn control, and
                # the only way out is the book's own header arrow, which closes it
                # and uncovers the page underneath (live: clicking it over the team
                # page reached PRE_BATTLE_TEAM).
                close = controls.get('tutorial.book_close')
                if close is None:
                    return _refuse(page, 'tutorial_last_page_has_no_forward_control')
                return _plan(page, CLICK, target=close, expect=(ANY,), advance=True,
                             reason='tutorial_last_page_is_closed_from_the_book_header')
            return _refuse(page, 'tutorial_next_button_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='tutorial_overlay_must_be_dismissed_before_enter_is_live')
    if page == 'RUN_REWARD_BONUS':
        # The second question the reward modal can ask: "Spend your 'Weekly Bonuses, to
        # claim the / bonus rewards?" (live
        # evidence/runtime/window-20261007-171228/frame-0003.json, what a run the weekly
        # reset expired is left with). Only three weekly bonuses exist, and they are worth
        # most on a run that finished its floors, so this page is answered by the ledger
        # instead of by taste: a settled run that completed spends one, and a run that was
        # given up (expired or abandoned) keeps them and cancels the question.
        spend = bool((bonus or {}).get('spend'))
        if spend:
            box = controls.get('run_reward_bonus.confirm_button')
            if box is None:
                return _refuse(page, 'run_reward_bonus_confirm_not_anchored')
            return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                         reason='a_completed_run_spends_one_weekly_bonus_on_its_rewards')
        box = controls.get('run_reward_bonus.cancel_button')
        if box is None:
            return _refuse(page, 'run_reward_bonus_cancel_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='a_run_that_was_not_completed_keeps_the_weekly_bonus')
    if page == 'RUN_REWARD_CONFIRM':
        # 'Claim the rewards?' with Cancel and Confirm: the modal's Claim only opens this,
        # and Confirm is what actually grants the rewards. Cancel is registered as an anchor
        # purely so it can be forbidden -- it would dismiss the question without claiming.
        box = controls.get('run_reward_confirm.confirm_button')
        if box is None:
            return _refuse(page, 'run_reward_confirm_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_reward_claim_is_confirmed_and_never_cancelled')
    if page == 'RUN_REWARD_DIALOG':
        # The modal the summary's claim opens: 'Exploration Reward' with Give Up Rewards,
        # To Window and Claim. Its Claim is the only control sent -- giving the rewards up
        # would throw the run away, and To Window leaves without them -- and it is exempt
        # from the loop guard because the reward split animates before the modal closes.
        box = controls.get('run_reward.claim_button')
        if box is None:
            return _refuse(page, 'run_reward_claim_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_reward_modal_is_claimed_and_never_given_up')
    if page == 'RUN_CLAIM':
        # The run summary -- five floors cleared, Total Progress 100% -- is claimed here
        # and nowhere else: live evidence/runtime/window-20261007-020715/frame-0006.json
        # reads 'Claim' [1682,865,82,30] and 'Rewards' [1662,901,124,28] beside a dim
        # 'Next' [1382,895,80,36] and a live 'Previous' [1096,895,148,36]. Only the claim
        # is sent; paging the summary back and forth proves nothing and is not done.
        box = controls.get('run.claim_button')
        if box is None:
            return _refuse(page, 'run_claim_button_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='claiming_is_the_only_forward_input_on_the_run_summary')
    if page == 'BATTLE_VICTORY':
        # The victory screen with a Confirm button is the one battle result page that
        # does not clear itself: live evidence/runtime/window-20261007-015542/frame-0130.json
        # reads 'Victory' 1.0, 'EX-CLEAR' 0.96 and 'Confirm' [1638,831,164,48] 1.0, and the
        # run stopped thirty rounds on it (build/window-run100.json) because it was being
        # waited out as an animation.
        box = controls.get('battle_victory.confirm_button')
        if box is None:
            return _refuse(page, 'battle_victory_confirm_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='victory_confirm_clears_the_result_and_carries_the_rewards')
    if page == 'BATTLE_DEFEAT':
        # A wiped stage asks what happens to the run: live
        # evidence/runtime/window-20261007-044408/frame-0001.json reads the three rows
        # 'Return to Stage Select' [948,343,262,28], 'Retry Stage' [946,480,144,34] and
        # 'Accept results and return to Stage select' [952,625,362,20] over 'All
        # participating Sinners have been killed.' and 'Remaining Units: 0/12', with the
        # Confirm [930,770,126,36] that commits whichever row is picked. Retrying the
        # stage is the only input that keeps the run alive, and it is bounded by the
        # driver: once the retries are spent nothing is sent and the player decides,
        # because accepting the deaths ends the run for real -- unless the window was
        # started with --defeat-accept, which is the operator saying they want the run
        # filed and the next one opened without them (the ledger files it as abandoned
        # through run_wiring.reconcile once the game is back at the picker).
        defeat = defeat or {}
        if defeat.get('row_sent'):
            # The row is already highlighted: this dialog is one Confirm away from
            # restarting the stage, and a retry in flight is never abandoned.
            box = controls.get('defeat.confirm_button')
            if box is None:
                return _refuse(page, 'defeat_confirm_not_anchored')
            return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                         reason='the_retry_is_confirmed_and_the_stage_starts_over')
        if defeat.get('spent'):
            if defeat.get('accept'):
                box = controls.get('defeat.accept_button')
                if box is None:
                    return _refuse(page, 'defeat_accept_row_not_anchored')
                return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                             reason='the_wiped_run_is_accepted_and_the_stage_select_comes_back')
            return _refuse(page, 'defeat_retries_exhausted')
        box = controls.get('defeat.retry_button')
        if box is None:
            return _refuse(page, 'defeat_retry_row_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_wiped_stage_is_picked_for_a_retry')
    if page == 'BATTLE_RESULT':
        # The victory screen has a proven producer and the pipeline clicks it
        # through PostBattleObserve, but no control for it has been anchored on a
        # real frame yet. Refuse by name rather than falling through to the
        # generic observe-only answer, so the driver says what is missing.
        return _refuse(page, 'battle_result_control_not_anchored')
    if page == 'PASS_LEVEL_UP':
        # Spending a weekly bonus levels the battle pass and the notice it raises sits on
        # top of Before Entry (live evidence/runtime/window-20261007-171928/frame-0007.json):
        # run-continue-12 pressed the menu's Enter under it and nothing moved. Its own
        # Confirm is the way out, and it is the only control on the notice.
        box = controls.get('pass_level_up.confirm_button')
        if box is None:
            return _refuse(page, 'pass_level_up_confirm_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_pass_level_up_notice_is_acknowledged_to_clear_the_menu')
    if page in ('MIRROR_ENTRY', 'BEFORE_ENTRY'):
        box = controls.get('entry.enter_button')
        if box is None:
            return _refuse(page, 'entry_enter_button_not_anchored')
        # Enter does not always start a fresh run: when the game still holds one, the
        # same press answers with the Dungeon Progress prompt instead (live:
        # evidence/runtime/window-20261008-030251/frame-0008.json is RESUME_DIALOG
        # straight after this page's Enter, and the window stopped on it as an
        # unexpected successor). Accept it and let that prompt's own Resume carry on.
        return _plan(page, CLICK, target=box,
                     expect=('STAR_GRACES', 'INITIAL_GIFTS', 'THEME_PACKS', 'MAP',
                             'LEVEL_WARNING', 'ENTRY_CONFIRM', 'PASS_LEVEL_UP', 'RESUME_DIALOG',
                             'UNKNOWN'),
                     reason='before_entry_enter_starts_the_free_run')
    if page == 'ENTRY_CONFIRM':
        # The entry page's Enter only raises the confirmation; the control that
        # really starts the run is the dialog's own Enter, and the X Cancel beside it
        # cancels instead (live: evidence/runtime/window-20261006-192917/frame-0001.json
        # carries the dialog Enter [1124,704,90,42] and the page's Enter
        # [1606,718,112,44] at once, so the two must never be confused).
        box = controls.get('entry_confirm.confirm_button')
        if box is None:
            return _refuse(page, 'entry_confirm_button_not_anchored')
        # The confirmation can also be the press that raises the held-run prompt, so
        # RESUME_DIALOG is an accepted successor here for the same reason as above.
        return _plan(page, CLICK, target=box,
                     expect=('STAR_GRACES', 'INITIAL_GIFTS', 'THEME_PACKS', 'LEVEL_WARNING',
                             'MAP', 'DUNGEON_TEAM', 'RESUME_DIALOG', 'UNKNOWN'),
                     reason='the_entry_confirmation_starts_the_run')
    if page == 'RESUME_DIALOG':
        box = controls.get('resume.resume_button')
        if box is None:
            return _refuse(page, 'resume_button_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('MAP', 'THEME_PACKS', 'STAR_GRACES', 'INITIAL_GIFTS', 'UNKNOWN'),
                     reason='resume_rejoins_the_run_that_is_already_in_progress')
    if page == 'WINDOW_RESET':
        # The notice's only two controls are Cancel (stay in the dungeon) and Confirm
        # (leave for the Window). The run in progress is what this window was sent to
        # drive, so the notice is declined and Confirm is a forbidden control -- an
        # unknown notice is never cleared by taking its irreversible branch (the user's
        # rule, m10140). Declining is a click, and the page must hand back something
        # other than itself, so a Cancel that did nothing is not recorded as progress.
        box = controls.get('window_reset.cancel_button')
        if box is None:
            return _refuse(page, 'weekly_reset_cancel_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_weekly_reset_notice_is_declined_and_the_run_stays')
    if page == 'THEME_PACKS':
        if difficulty=='normal' and controls.get('theme_packs.enable_hard'):
            return _plan(page,CLICK,target=controls['theme_packs.enable_hard'],expect=(ANY,),advance=True,
                         reason='enable_hard_on_proven_floor_one')
        if difficulty != 'hard':
            return _refuse(page, 'hard_difficulty_not_proven')
        # "SELECT FLOOR n THEME PACK" hangs the candidate packs from a rack and asks
        # for one to be taken: the page's own prompt is "Select a Pack And Pull", and
        # a click on a pack only plays its hover animation (live probe
        # build/theme-probe-click.json: the frame changed, no pack was taken), so
        # this page needs a drag down rather than a click. The leftmost pack is taken
        # so the choice is deterministic; matching a pack to the team's affinities is
        # a later refinement, not a licence to guess a coordinate here. The page must
        # hand back something other than itself, so a drag that did nothing is not
        # recorded as progress.
        box = controls.get('theme_packs.pack_01')
        if box is None:
            return _refuse(page, 'theme_pack_card_not_anchored')
        drop = controls.get('theme_packs.pull_to')
        if drop is None:
            return _refuse(page, 'theme_pack_pull_target_not_anchored')
        x, y, width, height = (int(value) for value in drop)
        return _plan(page, SWIPE, target=box, to=(x + width // 2, y + height // 2),
                     duration=700, expect=(ANY,),
                     reason='the_floor_theme_pack_is_pulled_down_to_be_taken')
    if page == 'EVENT_RESULT':
        if controls.get('factory_result.result_panel'):
            return _plan(page,CLICK,target=controls['factory_result.result_panel'],expect=(ANY,),advance=True,
                         reason='the_factory_result_is_acknowledged_on_its_own_panel')
        # The outcome page plays the event's own story with a dimmed bottom-right
        # control, and tapping the story panel is what turns that control into a
        # bright Continue (live: window-20261006-045451/frame-0001.json is dim, and
        # one tap produced frame-0002.json with Continue). The tap changes the frame
        # rather than the page, so this plan is an advancing one.
        box = controls.get('event_result.story_panel')
        if box is None:
            return _refuse(page, 'event_result_story_panel_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_event_result_story_is_tapped_to_reveal_its_continue')
    if page == 'EVENT_RESULT_READY':
        box = controls.get('event_result.continue_button')
        if box is None:
            return _refuse(page, 'event_result_continue_not_anchored')
        return _plan(page, CLICK, target=box, expect=('EVENT_RESULT_READY', ANY),
                     advance=True,
                     reason='the_event_result_is_cleared_with_its_own_continue')
    if page == 'CUTSCENE':
        # The abnormality/event intro covers the screen with a REC badge and one SKIP
        # button, and it does not advance on its own: live window-20261006-044556 sat
        # there with the text already complete for over a minute of observations.
        # Skipping is the page's own forward control, so it is a click, not a refusal.
        box = controls.get('cutscene.skip_button')
        if box is None:
            return _refuse(page, 'cutscene_skip_not_anchored')
        return _plan(page, CLICK, target=box, expect=('CUTSCENE', ANY), advance=True,
                     reason='the_cutscene_is_skipped_to_resume_the_run')
    if page == 'EVENT_CHECK':
        # The event's skill check asks which identity attempts the roll and prints each
        # one's odds caption over its card. The driver reads those captions off the live
        # frame (OCR merges the whole row into one token) and hands over the best slot's
        # card box, so the roll goes to the identity the game itself rates highest.
        # Choosing the identity does not leave the page: it swaps the bottom-right SKIP
        # for Commence and prints the prediction (live frame window-20261006-205435/
        # frame-0002 reads 'Commence' [1578,946,240,48] with 'Predicted Odds: Very High'),
        # so the driver's second pass over the same page reports that stage and its
        # button is what commits the roll.
        state = check or {}
        if state.get('stage') == 'commence':
            box = controls.get('event_check.commence_button')
            if box is None:
                return _refuse(page, 'event_check_commence_not_anchored')
            return _plan(page, CLICK, target=box, advance=True,
                         expect=('CUTSCENE', 'EVENT_RESULT', 'EVENT_RESULT_READY',
                                 'EVENT_CHECK', 'EVENT_CHECK_RESULT', ANY),
                         reason='the_skill_check_is_committed_with_its_commence',
                         detail={'slot': state.get('slot'), 'tier': state.get('tier')})
        box = state.get('box')
        if not box:
            # The page opens on its story: the question is printed, but the odds row and
            # the identity cards have not faded in yet and the bottom-right slot is the
            # dark SKIP. Live build/window-run88.json refused this page four times in a
            # row, and the user's rule (m10140) is to keep tapping the small screen until
            # the control lights up, so the story panel is the target until the row or
            # Commence arrives.
            panel = controls.get('event_check.story_panel')
            if panel is None:
                return _refuse(page, 'no_event_check_candidate_observed')
            return _plan(page, CLICK, target=panel, expect=('EVENT_CHECK', ANY), advance=True,
                         reason='the_skill_check_story_is_tapped_through_until_it_asks',
                         detail={'slot': state.get('slot'), 'tier': state.get('tier')})
        return _plan(page, CLICK, target=box, expect=('EVENT_CHECK', ANY), advance=True,
                     reason='the_skill_check_is_rolled_by_the_best_odds',
                     detail={'slot': state.get('slot'), 'tier': state.get('tier')})
    if page == 'EVENT_CHECK_RESULT':
        # The roll resolves on the same page: the question and the odds row stay, the
        # outcome panel prints 'Check Passed'/'Check Failed' with the Outcome number, and
        # the story it hands back plays inside the left panel while the bottom-right
        # control is still dark. Live window-20261006-205922 kept that page for 43 frames
        # with the text already complete ('E.G.O Gift Crown of Roses obtained!'), and only
        # frame-0001's OCR reached the SKIP at all. The user's rule (m10140) is to keep
        # tapping the small screen until the bottom-right lights up, so the panel is the
        # target here; the lit form is named CUTSCENE and its SKIP forwards the run.
        box = controls.get('event_check_result.story_panel')
        if box is None:
            return _refuse(page, 'event_check_result_panel_not_anchored')
        return _plan(page, CLICK, target=box, expect=('EVENT_CHECK_RESULT', ANY),
                     advance=True,
                     reason='the_check_outcome_is_tapped_through_until_its_control_lights_up')
    if page == 'EVENT_CHECK_READY':
        # The same page once the story has been tapped through: the bottom-right slot
        # lights up as its own Continue (live window-20261006-210803/frame-0001.json reads
        # 'Check Passed' with nothing in that slot, and frame-0002.json onward reads
        # 'Continue' [1588,941,220,59]). The roll is already resolved here, so this is not
        # the SKIP that forfeits a check - it is the page's forward control.
        box = controls.get('event_check_ready.continue_button')
        if box is None:
            return _refuse(page, 'event_check_ready_continue_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_check_outcome_is_left_with_its_lit_continue')
    if page == 'EVENT_CHOICE':
        # The event's "Choices" page lists two to four rows of spoken text; any row
        # advances the run, and the rows are read live because their count moves them.
        # A reward announcement under a row names what that row grants, so the hinted
        # row is the one taken when the driver can see one.
        if not candidates:
            return _refuse(page, 'no_event_choice_observed')
        if not 0 <= candidate_index < len(candidates):
            return _refuse(page, 'event_choice_index_out_of_range')
        return _plan(page, CLICK, target=candidates[candidate_index],
                     expect=('EVENT_CHOICE', ANY), advance=True,
                     reason='the_event_choice_that_names_its_reward_is_taken',
                     detail={'option_count': len(candidates),
                             'option_index': candidate_index})
    if page == 'MAP':
        if not candidates:
            return _refuse(page, 'no_candidate_node_observed')
        if not 0 <= candidate_index < len(candidates):
            return _refuse(page, 'candidate_index_out_of_range')
        # The map is the run's hub: a node opens its own panel (the proven case), and a
        # battle node can hand the run straight to the pre-battle team instead - live
        # build/window-run73.json step17 clicked a node and landed on PRE_BATTLE_TEAM,
        # which used to stop the run as an unexpected successor. Everything an Enter on a
        # node panel can produce is therefore a legitimate answer here, and the click is
        # judged by the page actually changing rather than by which one it became.
        return _plan(page, CLICK, target=candidates[candidate_index],
                     expect=('NODE_PANEL', 'PRE_BATTLE_TEAM', 'DEPLOYMENT', 'SHOP',
                             'SHOP_LEAVE', 'CUTSCENE', 'EVENT_CHOICE', 'EVENT_CHECK',
                             'EVENT_CHECK_RESULT', 'EVENT_CHECK_READY', 'EVENT_RESULT',
                             'EVENT_RESULT_READY', 'GIFT_PICK', 'GIFT_GET', 'REWARD_CARD',
                             'EGO_GIFT_POPUP', 'WINDOW_RESET', 'UNKNOWN'),
                     reason='map_node_click_is_the_only_proven_forward_input',
                     detail={'candidate_count': len(candidates),
                             'candidate_index': candidate_index})
    if page == 'NODE_PANEL':
        box = controls.get('node_panel.enter_button')
        if box is None:
            return _refuse(page, 'enter_button_not_anchored')
        # Enter hands the node over to the game: it fades back through MAP
        # (evidence/runtime/window-20261006-042056/frame-0002.json) before the node
        # itself shows up. What a node hands back depends on the node: the shop
        # (window-20261006-042123), the pre-battle team, an abnormality cutscene
        # (build/window-run30.json step 15), an event's choices, a floor-gift pick or a
        # reward card, so every one of them is a legitimate successor here. The weekly
        # reset notice landed here too (run-continue-8 step 64, frame-0252): it is a
        # notice about the run, not a failed click, and its own plan declines it.
        return _plan(page, CLICK, target=box,
                     expect=('PRE_BATTLE_TEAM', 'SHOP', 'MAP', 'CUTSCENE',
                             'EVENT_CHOICE', 'EVENT_RESULT', 'EVENT_RESULT_READY',
                             'GIFT_PICK', 'REWARD_CARD', 'WINDOW_RESET', 'UNKNOWN'),
                     reason='panel_enter_is_the_only_forward_input')
    if page == 'SHOP':
        # Spending is out of budget (module budget is 0/pending), so Leave is the
        # only input this project sends in a shop: it returns to the map with the
        # cost untouched. Refresh/Heal/Enhance/Fuse/Sell and every gift card are
        # deliberately left unanchored so no plan can ever land on them.
        box = controls.get('shop.leave_button')
        if box is None:
            return _refuse(page, 'shop_leave_button_not_anchored')
        return _plan(page, CLICK, target=box, expect=('SHOP_LEAVE', 'MAP', 'UNKNOWN'),
                     reason='leaving_the_shop_is_the_only_budget_safe_input')
    if page == 'SHOP_LEAVE':
        # Leaving the shop asks first. Confirm is the forward input; the Cancel
        # next to it only stays in the shop, so it is never a target.
        box = controls.get('shop.leave_confirm_button')
        if box is None:
            return _refuse(page, 'shop_leave_confirm_not_anchored')
        return _plan(page, CLICK, target=box, expect=('MAP', 'UNKNOWN'),
                     reason='confirming_the_shop_exit_is_the_only_forward_input')
    if page == 'GIFT_GET':
        # The gift-get notice sits on top of the reward-card page and carries one
        # Confirm. The gift was already granted by the reward card's own Confirm,
        # so this only clears the notice (live: window-20261006-042956).
        # The starting gift's notice leads straight into the optional gift search,
        # and which of the two the settle window catches is a race: build/window-run-continue-2.json
        # step 71 clicked Confirm and observed GIFT_SEARCH (late_observation), which
        # used to be read as an unexpected successor and stopped a live run.
        box = controls.get('gift_get.confirm_button')
        if box is None:
            return _refuse(page, 'gift_get_confirm_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('GIFT_GET', 'GIFT_SEARCH', 'REWARD_CARD', 'MAP', 'UNKNOWN'),
                     reason='the_gift_get_notice_is_cleared_with_its_own_confirm')
    if page == 'GIFT_WARNING':
        # Select pressed with choices still outstanding: the game offers to trade the
        # rest for random Trials. Taking that trade is the "refuse a reward" the user
        # forbade, so the warning is always cancelled and the pick resumes there.
        box = controls.get('gift_warning.cancel_button')
        if box is None:
            return _refuse(page, 'gift_warning_cancel_not_anchored')
        return _plan(page, CLICK, target=box, expect=('GIFT_PICK', 'UNKNOWN'),
                     reason='the_warning_is_cancelled_to_keep_the_remaining_gift_choices')
    if page == 'GIFT_PICK':
        # The floor hands out its gifts here: a row of cards and a Select button that
        # stays dark until the pick is satisfied. Two live variants exist — a
        # four-card round that prints "Select 0/2" and a three-card round that prints
        # a bare "Select" with no counter at all (evidence/runtime/window-20261006-043531),
        # so the planner takes the counter when it reads and the button's own
        # brightness when it does not. Refuse Gift is anchored but forbidden, so no
        # plan may ever land on it.
        state = gift or {}
        chosen = int(state.get('chosen') or 0)
        required = state.get('required')
        ready = state.get('ready')
        # The counter settles the pick whenever it reads: the button lights up with a
        # single choice made ("Select 1/2" is bright), so brightness alone confirms
        # early — live window-20261006-052152 raised the "remaining E.G.O Gift
        # choices" warning exactly that way. Without a counter (the three-card round)
        # brightness is the only completion signal, and an early Select is
        # recoverable because that warning's own Cancel brings the pick straight back.
        if required is not None:
            settled = chosen >= int(required)
        else:
            settled = ready is True
        if not settled and chosen < 4:
            # The number of offered gifts changes the card's own size (a single-card
            # round draws one card about 390x585, the four-card round draws 240x200
            # slots), so the boxes read from this frame's plates come first and the
            # anchored slot is only the fallback.
            derived = list(cards or [])
            box = (derived[chosen] if chosen < len(derived)
                   else controls.get('gift_pick.card_%02d' % (chosen + 1)))
            if box is None:
                return _refuse(page, 'gift_pick_card_not_anchored')
            return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                         reason='the_floor_gift_card_must_be_picked_before_select',
                         detail={'chosen': chosen, 'required': required, 'ready': ready})
        if not settled:
            # Every anchored card has been offered and the button still reads dark:
            # repeating a pick would be a blind guess, so the driver stops instead.
            return _refuse(page, 'gift_pick_cards_exhausted_without_a_lit_select')
        box = controls.get('gift_pick.select_button')
        if box is None:
            return _refuse(page, 'gift_pick_select_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('GIFT_GET', 'GIFT_PICK', 'MAP', 'UNKNOWN'),
                     reason='select_takes_the_picked_floor_gifts')
    if page == 'STAR_GRACES':
        # The Graces page sells buffs for starlight. The rotation's own card order is
        # the instruction and the budget is what the run may still spend, so the
        # planner buys exactly the next card the driver says is affordable and leaves
        # through the page's Enter otherwise (live:
        # evidence/runtime/window-20261006-193843/frame-0004.json reads the page title
        # and Enter [1740,986,102,42]).
        buy = graces or {}
        point = buy.get('point')
        if point is not None and buy.get('card'):
            return _plan(page, CLICK,
                         target=[point[0] - 45, point[1] - 23, 90, 46],
                         expect=(ANY,), advance=True,
                         reason='grace_card_is_bought_within_the_available_starlight',
                         detail={'card': buy['card']})
        box = controls.get('graces.enter_button')
        if box is None:
            return _refuse(page, 'graces_enter_not_anchored')
        # Enter asks its own question before the run starts ("Continue with selected
        # effects?"), so that confirm is an expected successor: live run105 bought five
        # graces, pressed Enter and was stopped as an unexpected successor on STAR_CONFIRM
        # (build/window-run105.json step8).
        return _plan(page, CLICK, target=box,
                     expect=('STAR_CONFIRM', 'INITIAL_GIFTS', 'THEME_PACKS', 'MAP', 'UNKNOWN'),
                     reason='the_graces_page_is_left_with_its_own_enter')
    if page == 'GIFT_SEARCH':
        # The run's optional gift search: picking up to three gifts off the pool costs
        # starlight (the tray header prints the running price, and Select stays inert
        # until something is picked). The player asked for the search to be refused
        # outright, so the planner takes the page's own Refuse Gift and spends nothing;
        # mode 'select' keeps the alternative of leaving through Select. Live:
        # evidence/runtime/window-20261006-195803/frame-0001.json reads the title, the
        # tray label, Select [1568,845,88,30], Refuse Gift [1302,843,152,34] and '0/3'.
        mode = (search or {}).get('mode', 'refuse')
        if mode == 'refuse':
            name, reason = ('gift_search.refuse_button',
                            'the_player_asked_the_optional_gift_search_to_be_refused')
            missing = 'gift_search_refuse_not_anchored'
        else:
            name, reason = ('gift_search.select_button',
                            'the_gift_search_is_left_without_spending_starlight')
            missing = 'gift_search_select_not_anchored'
        box = controls.get(name)
        if box is None:
            return _refuse(page, missing)
        return _plan(page, CLICK, target=box,
                     expect=('GIFT_SEARCH_FORGO', 'MAP', 'THEME_PACKS', 'UNKNOWN'),
                     reason=reason)
    if page == 'EGO_GIFT_POPUP':
        # A gift the run just picked up opens its own modal over the map; its Confirm
        # acknowledges the pickup and returns to the floor. Live:
        # evidence/runtime/window-20261006-201621/frame-0001.json reads 'E.G.O Gifts'
        # [832,170,256,58] and Confirm [916,825,126,40] over 'Exploring Floor 1'.
        box = controls.get('ego_gift_popup.confirm_button')
        if box is None:
            return _refuse(page, 'ego_gift_popup_confirm_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('MAP', 'NODE_PANEL', 'UNKNOWN'),
                     reason='the_ego_gift_popup_is_acknowledged_with_its_confirm')
    if page == 'GIFT_SEARCH_FORGO':
        # Refusing the search raises its own confirmation. Live:
        # evidence/runtime/window-20261006-200357/frame-0001.json reads "Forgo E.G.O
        # Gift Search?", Confirm [1116,722,112,38] and X Cancel [700,720,142,40].
        box = controls.get('gift_search_forgo.confirm_button')
        if box is None:
            return _refuse(page, 'gift_search_forgo_confirm_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('MAP', 'THEME_PACKS', 'GIFT_SEARCH', 'UNKNOWN'),
                     reason='the_forgone_gift_search_is_confirmed')
    if page == 'INITIAL_GIFTS':
        # The run opens on the starting E.G.O Gift picker: eight keyword columns, a
        # "Selected E.G.O Gift" tray, and a Select button that stays inert until the
        # counter fills. The rotation's keyword names the column and the first icon
        # under it is the gift (live:
        # evidence/runtime/window-20261006-195104/frame-0001.json reads 'Bleed'
        # [510,236,64,32], Select [1524,859,110,42] and '0/1' [1684,851,62,52]).
        state = initial or {}
        point = state.get('point')
        if point is not None:
            return _plan(page, CLICK, target=[point[0] - 30, point[1] - 30, 60, 60],
                         expect=(ANY,), advance=True,
                         reason=state.get('reason')
                         or 'the_starting_gift_is_picked_from_the_rotation_keyword',
                         detail={'keyword': state.get('keyword'),
                                 'gift': state.get('gift')})
        if state.get('chosen') is None or state.get('chosen')!=state.get('required'):
            return _refuse(page,'initial_gift_selection_incomplete')
        box = controls.get('initial_gifts.select_button')
        if box is None:
            return _refuse(page, 'initial_gift_select_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('GIFT_GET', 'MAP', 'THEME_PACKS', 'UNKNOWN'),
                     reason='select_takes_the_starting_gift')
    if page == 'STAR_CONFIRM':
        status=graces or {}
        if status.get('incomplete'):
            box=controls.get('star_confirm.cancel_button')
            if box is None:return _refuse(page,'star_cancel_not_anchored')
            return _plan(page,CLICK,target=box,expect=('STAR_GRACES',),
                         reason='incomplete_graces_return_to_selection')
        if not status.get('complete'):return _refuse(page,'grace_transaction_not_proven')
        if status.get('conversion')=='checked':
            return _plan(page,CLICK,target=status['conversion_box'],expect=(ANY,),advance=True,
                         reason='disable_unauthorized_starlight_conversion')
        if status.get('conversion')!='unchecked' or status.get('cost')!=0:
            return _refuse(page,'starlight_conversion_off_and_cost_zero_not_proven')
        box=controls.get('star_confirm.confirm_button')
        if box is None:return _refuse(page,'star_confirm_button_not_anchored')
        return _plan(page,CLICK,target=box,
                     expect=('INITIAL_GIFTS','THEME_PACKS','MAP','STAR_GRACES','UNKNOWN'),
                     reason='the_grace_selection_is_confirmed_before_the_run_starts')
    if page == 'LEVEL_WARNING':
        # A rotation team whose average level sits below the recommendation raises
        # this prompt; the rotation is the instruction, so the run proceeds and Cancel
        # is refused (live: evidence/runtime/window-20261006-193730/frame-0003.json
        # carries the dialog Confirm [1116,720,112,40], its X Cancel [744,728,96,30]
        # and the loadout page's own Confirm [1634,855,168,48] underneath).
        box = controls.get('level_warning.confirm_button')
        if box is None:
            return _refuse(page, 'level_warning_confirm_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('STAR_GRACES', 'INITIAL_GIFTS', 'THEME_PACKS', 'MAP',
                             'UNKNOWN'),
                     reason='the_level_warning_proceeds_with_the_rotation_team')
    if page == 'DUNGEON_TEAM':
        # A Mirror Dungeon run opens on the loadout picker: seven TEAMS slots down the
        # left edge and one Confirm on the bottom right. The rotation decides which
        # slot to bring, and only Confirm starts the run (live:
        # evidence/runtime/window-20261006-193439/frame-0002.json reads TEAMS #1..#7
        # at x≈150 and Confirm [1632,853,170,52] with Starlight Bonus 107).
        wanted = (team or {}).get('wanted')
        chosen = (team or {}).get('selected')
        slot = controls.get('team.slot_%02d' % wanted) if wanted else None
        if slot is not None and chosen != wanted:
            return _plan(page, CLICK, target=slot, expect=(ANY,), advance=True,
                         reason='dungeon_team_slot_is_selected_for_the_rotation',
                         detail={'slot': wanted})
        confirm = controls.get('team.confirm_button')
        if wanted is not None and chosen != wanted:
            return _refuse(page, 'wanted_team_header_not_proven')
        if confirm is None:
            return _refuse(page, 'dungeon_team_confirm_not_anchored')
        return _plan(page, CLICK, target=confirm,
                     expect=('STAR_GRACES', 'INITIAL_GIFTS', 'THEME_PACKS', 'MAP',
                             'LEVEL_WARNING', 'UNKNOWN'),
                     reason='dungeon_team_confirm_brings_the_chosen_team_in')
    if page == 'PRE_BATTLE_TEAM':
        # The page opens with nobody picked, and its Battle! button is dark until
        # at least one card is in the team (live: window-20261006-030750 has
        # 0/12 and a dim button; window-20261006-030941 has 12/12 and a bright
        # one). Selecting is per card and never touches the identity, so the only
        # safe move is to pick the first card that still has no badge -- unless the
        # page's own counter already reads full (live: '11/11' with eleven badges and
        # a bright Battle!, where the twelfth slot does not exist and tapping it was
        # fifty-seven wasted steps in build/window-run94.json).
        states = list((team or {}).get('states') or [])
        picked, capacity = (list((team or {}).get('participants') or []) + [None, None])[:2]
        full = bool(picked) and bool(capacity) and picked >= capacity
        if (team or {}).get('reset_required'):
            box=controls.get('pre_battle.clear_selection')
            if box is None:return _refuse(page,'deployment_clear_selection_not_anchored')
            return _plan(page,CLICK,target=box,expect=(ANY,),advance=True,
                         reason='clear_inherited_participant_order_before_saved_deployment')
        if full and (team or {}).get('order') and not (team or {}).get('order_verified'):
            return _refuse(page,'saved_deployment_sequence_not_proven')
        if not full:
            order = (team or {}).get('order') or list(range(1, len(states) + 1))
            if (len(order) != len(states) or set(order) != set(range(1, len(states) + 1))):
                return _refuse(page, 'saved_deployment_order_invalid')
            for card in order:
                index = card - 1
                state = states[index]
                box = controls.get('pre_battle.card_%02d' % (index + 1))
                if state is None and box is not None:
                    return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                                 reason='team_card_joins_the_next_unpicked_identity',
                                 detail={'card_index': index + 1})
        box = controls.get('pre_battle.battle_button')
        if box is None:
            return _refuse(page, 'battle_button_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('BATTLE_HUD', 'DEPLOYMENT', 'THEME_PACKS', 'UNKNOWN'),
                     reason='battle_button_submits_the_team')
    if page == 'DEPLOYMENT':
        # Submitting the team can land on the deployment view instead of the battle:
        # live run build/window-run29.json had To Battle! hand back DEPLOYMENT, whose
        # own bottom-right control is the same "To Battle!" (live frame
        # evidence/runtime/window-20261006-050402/frame-0006.json reads it at
        # [1614,857,206,48], inside the anchored battle button). The fight then
        # starts by itself, so one click here is enough.
        box = controls.get('deployment.battle_button') or controls.get('pre_battle.battle_button')
        if box is None:
            return _refuse(page, 'deployment_battle_button_not_anchored')
        return _plan(page, CLICK, target=box,
                     expect=('BATTLE_HUD', 'UNKNOWN'),
                     reason='deployment_view_starts_the_fight')
    if page == 'REWARD_CARD':
        # A cleared node hands back a pick-one reward screen ("Selectable 0/1").
        # Confirm does nothing until a card is picked, so the planner reads the
        # counter instead of clicking blind. Cancel is a registered anchor (its
        # label is part of the page identity) and is refused as a target, because
        # refusing a reward the run already earned is a forbidden input.
        state = reward or {}
        chosen = int(state.get('chosen') or 0)
        required = int(state.get('required') or 1)
        if chosen < required:
            box = controls.get('reward_card.card_01')
            if box is None:
                return _refuse(page, 'reward_card_box_not_anchored')
            return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                         reason='the_reward_card_must_be_picked_before_confirm',
                         detail={'chosen': chosen, 'required': required})
        box = controls.get('reward_card.confirm_button')
        if box is None:
            return _refuse(page, 'reward_card_confirm_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='confirm_grants_the_picked_encounter_reward')
    if page == 'BATTLE_TIP':
        # A tap on a skill card opens that skill's detail over the board, and the panel
        # has no close control of its own (live window-20261007-014613/frame-0094.json:
        # 'Skill Effects' over the keyword list, the WAVE/TURN captions covered). The
        # dark board area under the auto-assign buttons is empty in that frame --
        # (1700,950) reads mean (0,3,14) with std 6.6 -- so a tap there dismisses the
        # panel, which is the same unbounded-by-design, step-budgeted shape as the other
        # dismiss taps.
        box = controls.get('battle_tip.dismiss_point')
        if box is None:
            return _refuse(page, 'battle_tip_dismiss_not_anchored')
        return _plan(page, CLICK, target=box, expect=(ANY,), advance=True,
                     reason='the_skill_detail_popup_is_dismissed_off_the_board')
    if page in ('BATTLE_HUD', 'BATTLE_PLANNING'):
        # BATTLE_PLANNING is the same battle screen in its skill-planning sub-state
        # (agent/recognition.py:198 names it when the WAVE/TURN captions are not read
        # on that frame), so the forward input is unchanged: assign, then submit.
        if start_box:
            return _plan(page, CLICK, target=start_box,
                         expect=('BATTLE_HUD', 'BATTLE_PLANNING', 'BATTLE_RESULT', 'DEFEAT',
                                 'UNKNOWN'),
                         reason='start_button_submits_the_assigned_turn')
        if auto_assign and auto_assign.get('win_rate'):
            return _plan(page, CLICK, target=auto_assign['win_rate'],
                         expect=('BATTLE_HUD', 'BATTLE_PLANNING', 'BATTLE_RESULT', 'DEFEAT',
                                 'UNKNOWN'),
                         reason='win_rate_is_the_proven_auto_assign_control')
        return _refuse(page, 'battle_has_no_proven_control')
    return _refuse(page, 'page_is_observe_only')


def successor_ok(plan, page):
    """True when the successor page satisfies the plan's expectation.

    An empty expectation set means the plan sent no input, so any page is fine.
    :data:`ANY` is the dismissal case: the click is proven by the covered page
    being gone, so every successor except the plan's own page passes.
    """
    if plan.get('action') not in (CLICK, SWIPE, NODE):
        return True
    if page == 'TUTORIAL' and plan.get('page') != 'TUTORIAL':
        # The guide book pops up over any page without warning (live: it covered
        # the battle HUD right after "To Battle!"), so its appearance never
        # disproves the input that preceded it; the next step dismisses it.
        return True
    expect = plan.get('expect') or []
    if ANY in expect:
        return page != plan.get('page')
    return page in expect


def step_result(plan, *, sent, before, after, page, frame_changed=False):
    """Assemble the recorded step verdict for one planned input.

    ``frame_changed`` is the pixel evidence that the screen moved on. An
    ``advance`` plan is one whose own page is expected to stay: the tutorial
    overlay walks card after card, so a changed frame is the proof that the click
    landed even while the page label is unchanged.
    """
    if not sent:
        return {'action': plan['action'], 'reason': plan['reason'], 'passed': False,
                'page_before': before, 'page_after': after or before,
                'clicks_sent': 0}
    ok = successor_ok(plan, page) or (plan.get('advance') and frame_changed)
    return {'action': plan['action'], 'reason': plan['reason'] if ok else 'unexpected_successor',
            'passed': ok, 'page_before': before, 'page_after': page,
            'expect': list(plan.get('expect') or []), 'clicks_sent': 1}
