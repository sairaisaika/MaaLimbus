# Acceptance evidence

## October8 Hard floor1 map and failed inherited deployment order

Actual Hard theme page041437 and successor042100 ExploringFloor1/To beCrushed prove Hard entry and selected theme, not a clear. Current042218 BATTLE_HUD after WinRate, no START: pre-battle inherited Ryoshu/Meursault/Gregor/YiSang as positions1–4. Added remainingcards and12/12 is therefore NOT the requested saved order. Offline durable clear/count/sequence repair added; real reordered-team validation remains open. No current run combat victory, floorclear, finalclaim, or rotation/reentry acceptance.


## October8 team2 gifts and actual Hard mode

Employee Card and Portable Battery Socket selected under Charge with separate0/2→1/2→2/2 and row highlight proof, and each exact E.G.O Gift GET receipt plus next-page proof. Optional search refused once with no purchase. Actual Normal041201 switched once; fresh041437 provesHard via .92 glyph recognition despite low-confidence fullOCR. Current state is Hard floor1 pack selection, not a completed floor or run. No reward or rotation accepted. Full Python480passed before final added switch regression.


## October8 native star recovery, incomplete final goal

Actual team2 entry and base cards2,4,5,7 now have four exact debits totaling100, pool116→16. Remaining-starlight conversion unchecked with Cost0 was retained before confirmation. Latest fresh observation is INITIAL_GIFTS, no current Hard proof or floor/reward acceptance. Native retained-frame OCR repair covers 86 truncated to8; offline replay is recognition evidence only. New run scope discards no history and inherits no prior floor1. Durable transaction refuses unresolved inputs and changed scope/config/balance. Python479 passed before the additional current checkbox sample.


## 2026-10-07 the bonus question grants the reward, and a finished run is receipted

- **What went wrong.** `run-continue-21` (job `pwsh-508`, dir
  `evidence/runtime/window-20261007-203856`) walked the whole claim: 00:39:00 the reward
  modal's `Claim`, 00:39:02 `a_completed_run_spends_one_weekly_bonus_on_its_rewards` on the
  now correctly named `RUN_REWARD_BONUS` page, then the summary, the drive back to the mirror
  menu, a new entry, team pick, graces, gift and gift search — one clean pass. The ledger,
  though, filed that finished run as abandoned: `abandoned 476f23dc team 1 floors
  [1,2,3,4,5] victory true reward false` at `2026-10-08T00:39:35Z`. Victory and all five
  floors were there; only `reward` was missing, so `reconcile` read the next loadout as proof
  the game had dropped a run and threw the completion away — `completed` stayed at 1 and the
  rotation stayed on team 1, which is why the next dungeon came up on the same team.
- **Why.** `run_wiring.ledger_event` only treated `RUN_REWARD_CONFIRM` +
  `REWARD_CONFIRM_REASON` as the claim, but on this screen the input that hands the rewards
  over is the weekly-bonus question's own Confirm; and `reconcile` abandoned every active run
  it found at the loadout picker, including one whose ledger entry already said it finished
  and was paid.
- **What the script does now.** `run_wiring.BONUS_CONFIRM_REASON` joins `ledger_event`, so
  confirming `RUN_REWARD_BONUS` records `reward_received` (only when the run holds its
  victory; cancelling grants nothing), and `reconcile` files a `victory and reward` run as a
  **receipt** through `entry_returned` — settled time, `completed_runs` and the rotation all
  advance — abandoning only runs that never got paid. Its return value carries `how`
  (`receipt` / `abandoned`) for the window's journal.
- **Tests.** `tests/test_run_wiring.py::test_the_team_picker_receipts_a_run_that_finished_and_was_paid`
  drives floors 1–4, the summary and the bonus question, then asserts the picker receipts the
  run (no active run, `settled_at` set, rotation 1→2, nothing abandoned) and that seeing the
  same picker again files nothing. 429 passed.
- **Not claimed.** The live ledger was left as the game left it (rotation on team 1, matching
  the dungeon that is running); the repeated team-1 turn is recorded history, and the fix is
  only proven by the next run that settles under it. The bonus question's Confirm is pinned
  as the reward input on one live window.

## 2026-10-07 the weekly-bonus question is named however the OCR breaks its two lines

- **What stalled.** `run-continue-20` (job `pwsh-492`, dir
  `evidence/runtime/window-20261007-203340`) took the stage-clear panel's Confirm
  (`BATTLE_VICTORY → RUN_CLAIM`, 00:33:43) and the ledger filed `floor_clear 5` with
  `final_victory` at 00:33:47, then alternated `RUN_CLAIM ↔ RUN_REWARD_DIALOG` for eight
  clicks until `claim_family_made_no_progress` stopped it. The page it was really on is the
  weekly-bonus question: `frame-0009.json` reads it as **one glued line**
  `Spend your 'Weekly Bonuses, to claim the bonus [636,486,646,34] 0.97` above
  `× Cancel [704,718,142,42]` and `Confirm [1112,720,112,34]`, where the pinned pair reading
  (`evidence/runtime/window-20261007-171228/frame-0003.json`) has `... to claim the` plus
  `bonus rewards?` on two lines.
- **Why.** `spend_weekly_bonuses` demanded the line end in `the$` and `bonus_rewards`
  demanded `bonus rewards?$`, so neither matched the glued reading; the run summary's four
  words stayed readable behind the dialog and named the page `RUN_CLAIM`, so every click went
  to the summary's `Claim Rewards [1638,855,180,80]` and dismissed the question instead of
  answering it. The weekly bonus stayed at 2/3 throughout.
- **What the script does now** (`battle_victory` commit `63aa2aa`; this one follows it).
  `assets/resource/en/locale.json` reads `^Spend your '?Weekly Bonuses,? to claim the(?: bonus)?$`,
  and `src/maalimbus/vision.py`'s `RUN_REWARD_BONUS` rule needs the question line (either
  `spend_weekly_bonuses` or `bonus_rewards`) with `Confirm` and `Cancel`, its first ROI widened
  to `(.33,.42,.68,.51)` to hold `[636,486,646,34]`. The rule already sat before `RUN_CLAIM`,
  so only the reading changed. The plan spends a weekly bonus only for a run the ledger holds
  as finished, and this run is one (`final_victory`), so the next window answers Confirm.
- **Tests.** `tests/test_vision.py::test_the_weekly_bonus_question_is_named_before_anything_is_spent`
  additionally pins frame-0009 (the glued line must classify as `RUN_REWARD_BONUS`) and its
  negative now removes both lines of the question, since either one names the page. 428 passed;
  `tools/verify_anchors.py` reports 45 page(s), 0 broken.
- **Not claimed.** The glued reading is pinned on one frame only, and no run has yet been
  driven from this question through `reward_received` to `entry_returned` under the new rule.

## 2026-10-07 the stage-clear result panel is read even when its badge is misread

- **What stalled.** `run-continue-19` (job `pwsh-465`, dir
  `evidence/runtime/window-20261007-201340`) beat floor 5's boss and stalled at step 24 with
  `page_unreadable_after_waiting` — forty `window_unknown_wait` rounds on a screen whose only
  way forward is a button. Frames `.../frame-0218..0220.json` (00:30:03–00:30:17) are that
  screen: `Most Valued Employee` / `Damage Contributed 23%` and the boss portrait with its
  dialogue on the left, `Victory [1486,146,276,100] 1.0`, `EX-GLEAR [1334,162,180,86] 0.86`,
  `LV.91` / `EXP +0` / `3992/5178`, twelve Lv.60 cards and `Confirm [1638,831,164,48] 1.0`
  on the right (`build/live-stall-19.png`).
- **Why.** The `BATTLE_VICTORY` rule demanded both `Victory` and `EX-CLEAR`, and this frame's
  small print was read as `EX-GLEAR` — the C taken for a G — so the page fell through to
  `UNKNOWN` and was treated as an animation to wait out. That screen does not clear itself:
  its Confirm is the only forward input, exactly like the layout already pinned in
  `evidence/runtime/window-20261007-015542/frame-0130.json`.
- **What the script does now** (commit `battle_victory` badge rule). `src/maalimbus/vision.py`
  accepts `Victory` in the top-right band together with either the badge's `EX-CLEAR` or the
  `Confirm` in the bottom-right band (`.78,.70,.96,.86`), with the live frame and the misread
  named in the comment. `assets/resource/base/anchors.json` lists frame-0220 as further
  evidence for the `battle_victory` page; its `battle_victory.confirm_button` geometry
  `[1638,831,164,48]` is identical on both frames. Plan, anchor and loop-guard exemption
  already existed (`src/maalimbus/window.py:262-272`, reason
  `victory_confirm_clears_the_result_and_carries_the_rewards`, listed in
  `tools/window_step.py:97`), so only the reading changed.
- **Tests.** `tests/test_vision.py` pins frame-0220 in
  `test_the_result_page_is_read_when_the_badge_letters_are_misread` (the frame carries
  `Victory`, `EX-GLEAR` and `Confirm`, and it classifies as `BATTLE_VICTORY`; without the
  banner's own word the rule must not claim the page), and the older
  `test_the_victory_result_with_confirm_is_its_own_page` now removes **both** `EX-CLEAR` and
  `Confirm` before asserting the page is not claimed. 428 passed;
  `tools/verify_anchors.py` reports 45 page(s), 0 broken.
- **Not claimed.** Only two frames prove the Confirm geometry (frame-0130 and frame-0220);
  the badge's small print has not been sampled at other resolutions or in the Japanese
  locale, and no run has yet been driven from this panel all the way to the next floor
  under the new rule.

## 2026-10-07 the wiped run is waited into its dialog, retried on a budget, and filed

- **What stalled.** `run-continue-18` (job `pwsh-447`, dir
  `evidence/runtime/window-20261007-195545`) fought floor 5 and was wiped: step 33 is
  `page_before DEFEAT` / `page_after DEFEAT`, `action record`, `reason page_is_observe_only`,
  `stopped page_is_observe_only` — nothing was sent on the one page that decides whether the
  run survives. The frame behind it (`.../frame-0222.json`, 00:10:26) reads the banner
  `DEFEAT [726,434,470,225]`, `Gebura [332,101,100,28]` and Gebura's three lines
  (`All of your employees are dead. Bur this moment into` `[446,43,482,26]`), and **none** of
  the dialog's rows yet, so it classified as `DEFEAT` and not `BATTLE_DEFEAT`.
- **Why.** `src/maalimbus/window.py:70` held `WAIT_PAGES = ('UNKNOWN', 'BATTLE_RESULT')`, and
  only `BATTLE_DEFEAT` has a plan (`window.py:267-292`: pick the `Retry Stage` row, then send
  its own `Confirm`, bounded by `--defeat-tries`; once spent it refuses with
  `defeat_retries_exhausted`, because accepting the deaths or leaving the run is the player's
  decision). The banner is a page that clears itself a moment later, like `BATTLE_RESULT`.
- **What the script does now** (commit `8baaeb1`). `DEFEAT` joins `WAIT_PAGES`, and both battle
  plans list it in their `expect`. Live proof that the dialog follows and the retry works:
  `run-continue-19` (job `pwsh-465`, dir `evidence/runtime/window-20261007-201340`) read
  `BATTLE_DEFEAT` at 00:13:43 and sent `the_wiped_stage_is_picked_for_a_retry`, then at 00:13:45
  `the_retry_is_confirmed_and_the_stage_starts_over`, and was back in `BATTLE_HUD` at 00:14:02
  submitting turns again (00:14:06, 00:15:18). `build/live-defeat.png`, captured after the stop,
  shows the dialog the game had already drawn by then: `Floor in Progress 5/5`,
  `All participating Sinners have been killed.`, `Remaining Units: 0/12`, and the three rows
  `Return to Stage Select` / `Retry Stage` / `Accept results and return to Stage select` over
  `✓ Confirm`.
- **The ledger is reconciled too** (commit `1a0374d`). `src/maalimbus/run_wiring.py::reconcile`
  files a run the game no longer holds: the loadout picker (`DUNGEON_TEAM`) is only drawn for a
  **new** dungeon — a run still in progress answers the entry with the Dungeon Progress dialog
  (`evidence/runtime/window-20261006-025617/frame-0002.json`: `Resume` / `Halt Exploration`) —
  so seeing the picker while the ledger still calls a run active means that run ended without a
  receipt (the wipe dialog's own `Accept results` row, which the player presses, not the script).
  The run is filed into `abandoned` with the floors it reached and the rotation stays put, which
  also keeps `settle` able to open the next run at all. `tools/window_step.py` calls it beside
  the expired-session path and journals `run_reconciled`; `tests/test_run_wiring.py::
  test_the_team_picker_files_a_run_the_game_no_longer_holds` pins the archive, the rotation and
  the fact that no other page files anything. Full suite 427 passed.
- **Not claimed.** Nothing here shows which of the three dialog rows the player should prefer,
  that `Retry Stage` is free in every mode, or that a wipe always ends the run (the dialog itself
  offers the retry, so the run can continue). The retry budget lives in the window that is
  running: a fresh window starts counting again. Nor is anything claimed about the banner's
  animation timing beyond the one frame above.

## 2026-10-07 the turn dial is only the lit one, and the Win Rate press lights it

- **What stalled.** `run-continue-16` (job `pwsh-385`, report `build/window-run-continue-16.json`)
  ended after all 300 of its steps with its last 27 intents all reading
  `win_rate_is_the_proven_auto_assign_control` (targets `[1598,796,48,41]`,
  `[1600,792,46,45]` — the Win Rate caption itself) and **not one**
  `start_button_submits_the_assigned_turn`. The fight stood at TURN 3 for about 40 minutes
  (`build/live-stall-run16.png`), and the frame behind it
  (`evidence/runtime/window-20261007-184958/frame-1401.json`, 23:33:43) reads
  `Damage [1584,863,78,26]`, `Rate [1600,815,46,22]`, `Win [1604,796,40,21]`,
  `MAX [1636,39,62,40]`, `TURN [20,97,42,22]`, `1/10 [88,37,46,32]`, `3 [98,95,16,26]` —
  **no `START`**.
- **Why.** `src/maalimbus/window.py:804-816` sends the turn when the observation carries a
  `start_box`, and otherwise falls back to the Win Rate auto-assign; `start_box` comes from
  `battle_vision.start_button()`, which, when the START word is unreadable, reads the dial by
  colour inside `(0.60,0.66,0.78,0.88)` with `area>=4000`, `side>=60`. Of that window's 1103
  battle frames only `frame-0760.json` (23:17:39) and `frame-0912.json` (23:21:29) carried a
  readable START word, while the dial is drawn warm on 160 of 163 sampled battle frames in two
  size variants — `(1440,771,121,134)` area 5501 and `(1455,800,81,79)` area 1913, measured in
  1920 — whose centre `x` is about 1500, just outside the old band's right edge (`0.78*1920 =
  1497`). The old parameters answered on 11 of those 163 frames, so the fight was re-assigning
  skills instead of submitting turns.
- **What the script does now** (commit `624b067`, corrected here). The dial is read by its own
  shape inside the band `(0.58,0.60,0.82,0.93)`: `area>=4000`, side `100..160`, aspect at most
  `1.25`, and at least `28%` of its box filled. That keeps the **lit** disc and drops the dim one,
  and it also drops the wide warm highlights of the skill board that share the band — measured on
  `window-20261007-175552/frame-0307.png`, whose decoy `(1180,732,200,145)` area 5949, aspect 1.38,
  fill 0.21 sits beside the real `(1436,770,121,133)`, and on `frame-0083.png`
  (`(1113,676,172,264)` area 13468). The Win Rate/Damage captions start at `x=1584`, outside the
  right edge (`0.82*1920 = 1574`), so they cannot be mistaken for the dial, and the turn is still
  submitted only when the game itself draws its START word or its **lit** dial — nothing is
  inferred from the fight's state.
- **Why the dim dial is not the control.** A fresh window (`--label run-continue-17`, job
  `pwsh-403`, dir `evidence/runtime/window-20261007-194201`) used the earlier, looser thresholds
  and clicked `(1455,800,81,79)` seven times; TURN stayed 3 and no turn was submitted. On the
  stalled window the same input had already burned all 300 steps. The board draws that dim variant
  while the turn is still unassigned, and it lights the disc only after the Win Rate
  auto-assignment is pressed: `window-20261007-175552` pressed Win Rate at 22:43:44
  (`[1714,796,46,41]`) and `frame-1010.json` at 22:43:46 carries `START [1580,742,52,24]` with the
  lit disc `(1551,773,121,133)`, which was then submitted. Reproduced by hand on the stalled board
  with a single handed probe click at 1920 `(1623,816)` (`tools/map_zoom.py --click`): the disc
  went from the dim 854-pixel blob to the lit 2474-pixel blob (1280 screen) and the START banner
  appeared, while the same screen had been static through 48 seconds of sampling.
- **Measured.** Of 1651 archived battle frames across
  `window-20261007-184958`, `window-20261007-175552` and `window-20261007-194201`, `dial_control`
  now answers on 691 and every answer but two is the disc's own `121x13x` box (the two exceptions
  are `138x141` and `137x136`, the same disc with its glow). `tests/test_battle_touch.py` pins both
  sides of the distinction: `test_the_dim_dial_waits_for_the_auto_assignment_instead_of_submitting`
  (frame-1401: no START token, `dial_control` and `start_button` both `None`, `begin_turn_plan`
  refuses with `turn_start_not_present`, and the offered control is the Win Rate caption) and
  `test_the_lit_dial_is_read_on_a_board_that_draws_no_start_word`
  (`window-20261007-175552/frame-0020.json`, 21:57:13, no START token, box `(1439,772,121,133)`
  entirely left of the captions, and it is what `begin_turn_plan` targets). Full suite 425 passed;
  `tools/verify_anchors.py` 45 pages, 0 broken.
- **Not claimed.** Nothing here shows the dim state is *only* unassigned skills (the reading is
  that its board changes from bare chains to chains with `Clash!`/`REINFORCE` and arrows once the
  assignment lands), nor that one Win Rate press always lights the disc on every board, nor that
  the disc is the only control that can submit a turn anywhere else in the game.

## 2026-10-07 the factory floor's cyan path is walked, and the player is read from the flame

- **What stalled.** `run-continue-13` (report `build/window-run-continue-13.json`) stopped at
  step 113 on floor 2, "Automated Factory": two clicks
  (`map_node_click_is_the_only_proven_forward_input`) opened no panel
  (`map_click_opened_no_panel`, targets `[599,609,190,190]` then `[599,0,190,190]`), and
  three reads then found no candidate at all (`no_candidate_node_observed`). The page
  (`build/live-stall-113.png`) shows the flame in the lower middle with a bright cyan line
  leaving it for a `?` node in the upper right, with another `?` on the left and a grey node
  between them; `node_markers` found only two nodes on that frame and both were the player's
  own -- its flame and a reward chip under it.
- **Why.** `map_vision.path_end`'s mask only accepted the violet path floors 1 and 3 draw.
  Floor 2 draws it cyan, so the mask read nothing, the walk returned nothing, and the ladder
  of candidates fell through to the player's own node and the chip. Sampling the frame fixed
  the thresholds: a cyan mask needs `max >= 180` (below it the floor's own cyan grid joins the
  line into one 5.6k-pixel component; at 200 it breaks the line into three), and the target
  node sits about 470 px away, past the old `PATH_WALK_LIMIT` of 320.
- **What the script does now** (commit `3ee766d`). The mask takes the cyan line as well; the
  walk limit reaches one lattice step (560); and a far end within `PATH_SNAP` (70 px) of a
  ringed cyan node snaps to that node's pixel -- the path names which node, the ring names
  which pixel, and on the floor-1 frame the two disagree by 66 px. The archived floor-3
  reading `path_end(image, (960,672)) = (1123,641)` is unchanged at every cap.
- **The next window's first click still missed, for a second reason.** `run-continue-14` step
  0 read `frame-0002` -- caught mid-fade -- where the locomotive pair lands at (636,510) and
  the badge lift at (751,425) while the flame burns at (694,384). The old order believed the
  locomotive, which is 137 px from the flame, past `PATH_REACH`, so `path_end` again returned
  nothing and the click went to the hexagon between them. `player_readings()` now scores every
  reading by the flame under it -- restricted to the map band, because the header's sin
  counters are saturated yellow too and the whole-map centroid has already returned one of
  them (`evidence/runtime/window-20261006-233633/frame-0001.png`) -- and `map_clicks` walks
  the path from the other readings when the best one walks nowhere, since a path is drawn
  from the player and so can testify to where the player is.
- **Third stall of the same window: the story box over the victory banner.** Step 60 stopped
  `page_unreadable_after_waiting` after the wait budget (12 rounds) ran out. Frame
  `evidence/runtime/window-20261007-174525/frame-0159.json` reads `ICTORY` `[830,444,342,187]`
  .85 with the story lines ("... It's all thanks to their excellent classes. I've learned a"
  `[460,83,480,20]` .96) over the V, so `^VICTORY$` did not match and the result screen --
  which is only waited out, never clicked (`WAIT_PAGES`) -- was never named. The caption is
  now matched without its first letter. The story itself does advance on its own: consecutive
  frames keep changing (`frame-0191` .. `frame-0196`, six different hashes), so the next
  window runs with a larger `--unknown-rounds` rather than a click the player did not ask for.
- Tests: `tests/test_map_vision.py::test_the_player_is_the_reading_the_flame_agrees_with`,
  `::test_the_cyan_path_is_walked_even_when_the_player_is_read_mid_fade` (both pinned to
  frame-0002), `tests/test_vision.py::test_the_result_screen_is_named_when_the_story_box_covers_its_first_letter`
  (pinned to frame-0159), and the caption pin in `tests/test_battle_result_scene.py` follows
  the widened token. 422 passed; `tools/verify_anchors.py` 45 pages, 0 broken.
- Not claimed: that every floor's path colour is covered (floor 2's cyan and floors 1/3's
  violet are the two seen), and that the larger `--unknown-rounds` is the right budget for a
  long story rather than a named story page.

## 2026-10-07 the claim's second question is answered from the ledger, not the page

- **The page asks before it spends.** Claiming the rewards a weekly reset left behind
  raises a second question: "Spend your 'Weekly Bonuses, to claim the / bonus rewards?"
  with `× Cancel` and `Confirm` over the dimmed reward modal
  (`evidence/runtime/window-20261007-171228/frame-0003.json`, sha `be5d7c3077df`).
  Window `--label run-continue-11` stopped on it as `page_is_observe_only` at step 1.
- **Why it is not a free click.** Weekly Bonuses are three per week and they reset rather
  than accumulate; an unfinished run auto-concedes when the week turns and that week's
  bonus is lost, though its cleared floors can still be claimed in a later week (Steam
  discussion of patch 1973530, thread 597403944640085425). So the page cannot answer for
  itself.
- **What the script does now.** The window names `RUN_REWARD_BONUS` and asks the ledger:
  `run_wiring.earned_its_payout()` returns true only for the run that finished its floors,
  by comparing the receipt's `settled_at` with the abandoned run's `abandoned_at` (a
  receipt now carries that stamp). A completed run answers `Confirm` and spends one; a run
  the game expired or the player gave up answers `Cancel` and keeps them. When the ledger
  holds an abandoned run but cannot say which settled last, it keeps them: not knowing is
  not a reason to spend a weekly resource.
- **How it went live.** `run-continue-12` step 0 reached that page first and answered
  `Confirm` -- the old fallback treated the team-4 receipt, written before receipts carried
  `settled_at`, as the newer record. The claim paid out (Weekly Bonuses went 3/3 -> 2/3,
  Weekly Projection Cap 0/1000 -> 10/1000) and the game levelled the battle pass, raising
  `Pass Level Up` (`evidence/runtime/window-20261007-171928/frame-0005.json`, sha
  `aa7c595bbc77`) over Before Entry. That notice covered the menu's own `Enter`
  `[1606,718,112,44]` while the menu stayed readable, so step 1 clicked the covered button
  and stopped with `unexpected_successor`.
- **The notice is its own page now.** `PASS_LEVEL_UP` is named before `MIRROR_ENTRY` (an
  overlay wins over the page it covers) and acknowledges itself; Before Entry accepts it as
  a successor. `run-continue-13` then walked `PASS_LEVEL_UP -> MIRROR_ENTRY ->
  ENTRY_CONFIRM -> DUNGEON_TEAM` on the rotation's own team 1.
- Not claimed: that `Cancel` at the second question keeps the same rewards unspent; the
  ledger's rule is the conservative reading.

## 2026-10-07 a weekly reset invalidates a run and the script files it

- **The game, not the script, ends the run.** Window `--label run-continue-8`
  (`evidence/runtime/window-20261007-164753`) met the weekly reset notice over floor 3
  (`frame-0252.json`, sha `525d45cc4e7b`: "The weekly record has been reset. / Moving over
  to the Window." with `Cancel` and `Confirm`). Declining it did not save the run: the
  window drove to `DRIVE`, entered the mirror dungeon again, and landed on
  `EXPIRED_SESSION` -- "The previous session has expired. / Please claim your rewards."
  (`evidence/runtime/window-20261007-170653/frame-0009.json`, sha `323539fd0c19`), which
  run-continue-9 reported as `DRIVE -> EXPIRED_SESSION unexpected_successor` at step 2.
- **What the script does now.** The notice is its own page and clicks `Cancel` (its
  `Confirm` is a forbidden control: it would leave the dungeon); the expired session is
  its own page and clicks `Confirm`, because the run is already gone and only the reward
  is left on the table (its `Cancel` is forbidden). After that Confirm the driver calls
  `run_wiring.expire()`, which files the run under `abandoned` with the floors it did
  reach and the proving frame, journals `run_expired`, and **leaves the rotation on the
  same team** -- an expired run was never completed, so no receipt is invented for it.
- **Why it is in the ledger at all.** Before this, a run the game threw away stayed
  `active` forever and no command could clear it (`seed_run_store` refuses a ledger that
  already holds receipts); `tools/run_ledger.py abandon --note` and this automatic path
  are the two ways out.
- Not claimed: that a weekly reset is predictable from anywhere the script can read
  before it fires.

## 2026-10-07 the rotation ledger advanced on its own after a completed run

- **The driven run closed its own loop.** Window `--label run-continue-7`
  (`evidence/runtime/window-20261007-162956`) was started from an active run at team 4
  with `--run-store config/user-run-ledger.json` and drove it to the end. The journal's
  four `run_ledger_event`s are `floor_clear 5` (20:31:29Z, frame-0025), `final_victory`
  (20:31:29Z, frame-0025), `reward_received` (20:31:34Z, frame-0029) and `entry_returned`
  (20:32:06Z, frame-0045).
- **The ledger now reads** `slots [5,4,1,6,2,7,3]`, **`rotation 2 -> team 1`**,
  `completed 1`, `active run none` (`tools/run_ledger.py --path
  config/user-run-ledger.json status`). Its receipt `8de51ee326254dada65ae776aa1c1e11`
  carries `team 4`, `floors [1,2,3,4,5]`, `victory true`, `reward true`, and one evidence
  frame (with sha256) per event: `floor_clear-1 ->
  evidence/runtime/window-20261007-134338/frame-0307.json`, `floor_clear-2 ->
  window-20261007-140234/frame-0271.json`, `floor_clear-3 -> .../frame-0375.json`,
  `floor_clear-4 -> .../frame-0814.json`, `floor_clear-5 -> .../frame-0025.json`,
  `final_victory -> .../frame-0025.json`, `reward_received -> .../frame-0029.json`,
  `entry_returned -> .../frame-0045.json`. The next run then entered on team 1 on its own
  (`SHOP -> SHOP_LEAVE -> MAP -> NODE_PANEL` in the same journal).
- **Why it had not advanced before**: `run_wiring.ledger_event` finished a run only when
  `RUN_CLAIM` saw five cleared floors, but floor 5 can never be proved from a map page
  (there is no floor 6 to stand on), so `RUN_CLAIM` now settles floor 5 and then the
  victory itself (commit `a961044`); the driver's `record_ledger_event` asks that page
  repeatedly until it settles nothing new, and the report field is the `ledger_events`
  list.
- **Stalls this pass fixed**, each with a live frame and a test: the map forgetting that a
  spot it already tried is still the step after the event ends (`MapProgress.leave`,
  commit `ba0f5a3`), the battle HUD's wave counter losing its leading digit (`/10`, commit
  `cbb4b7f`), a story cutscene skipped three times tripping the same-plan guard on the one
  skip that revealed the check page (commit `3e5e1ba`), and `--flow launch,to_mirror,
  enter_mirror` chaining a cold start into a driven run (commit `d57b020`).
- **Not claimed**: no live JP/MXU evidence, no Enkephalin conversion, and the rotation
  ledger has no abandon path yet, so a run that ends on a wipe (the `BATTLE_DEFEAT`
  "Accept results" row) stays open until the next settlement or a manual reseed.

## 2026-10-07 five floors cleared, rewards claimed, the run re-entered

- **Five hard floors, live.** The window drove one dungeon from floor 1 to the floor-5
  boss and out: `build/live-after-victory.png` is the "Exploration Complete" settlement,
  Floor 1..5 each `6/6`, Total Progress `100%`, Last Reached
  "Mirror of Names and Spiders / Floor 5 [NORMAL]", Starlight 60 + 15x1.000 - 60 = 15,
  Pre-dungeon Reserve 7541 + 75 - 60 = Net 7,556. Runs: `build/window-run99.json`
  (floor-5 boss battle), `build/window-run101.json` (victory screen cleared).
- **Rewards claimed, then the run re-entered.** The settlement's Claim is the first of
  three pages: `RUN_CLAIM` -> `RUN_REWARD_DIALOG` -> `RUN_REWARD_CONFIRM`
  (`build/window-run104.json`, 8 steps, 9 clicks). The window then walked home -> Drive
  -> mirror entry -> entry confirmation -> the rotation slot on `DUNGEON_TEAM` -> level
  warning -> star graces -> initial gifts -> refused gift search -> theme pack -> map ->
  node panel -> deployment -> battle -> map again, 30 steps all passed
  (`build/window-run106.json`), and the next run kept progressing
  (`build/window-run108.json`, `build/window-run109.json`, `build/window-run110.json`).
- **Pages this pass had to name** (each with anchors, a plan branch and tests):
  `BATTLE_TIP` (the "Skill Effects" card popup that covers the HUD, commit `b18ce58`),
  `BATTLE_VICTORY` ('Victory' + 'EX-CLEAR', a screen that does not clear itself, commit
  `208866c`), `RUN_CLAIM` (commit `6f8aae9`), `RUN_REWARD_DIALOG` (commit `08526bb`),
  `RUN_REWARD_CONFIRM` (the "Claim the rewards?" confirmation, whose Cancel is in
  `FORBIDDEN_CONTROLS`, commit `52e5152`).
- **A loop the per-page guard could not see**: `RUN_REWARD_DIALOG <-> RUN_CLAIM` ping-pong
  passed the per-page guard every time because the page label really changed, so a claim
  family budget (`CLAIM_FAMILY`, `--claim-tries`, default 6) now counts steps spent inside
  the family; and `map_clicks` offers a step read off the frame (`lit_icon`) before the
  badge lift, because run107 spent every click on four lifted badge boxes while the red
  "?" node's own icon at `(1087,409)` was the step (a manual 1920-space tap on
  `(1080,428)` opened its panel; commit `7a17842`).
- **Since superseded**: that pass still used the fixed `--team 5`, but the rotation ledger
  has since advanced itself on a completed run — see the section above. Still not claimed:
  live JP/MXU evidence and Enkephalin conversion.

## 2026-10-06 first real battle entered, fought and won from the map

- With the discovery-based binding (MuMu's own adb, `EmulatorExtras` screencap,
  `AdbShell|MinitouchAndAdbKey|Maatouch` input) the bounded stepper advanced the real
  battle: `START` clicks moved the HUD from turn 1 to turn 2, and the following turn
  resolved into the victory sequence — "…have dealt a fatal blow to your enemies",
  `Gain Corpus Ingredient`, `Sloth DMG Up +1`, `TOTAL 132`
  (`evidence/runtime/battle-step-20261006-013320/frame-0001.png`). This is the first
  actual combat progress from the stopped 231221 session, and it used one bounded
  click per step with no key input.
- The `START` word is a banner above the real button: clicking the label did nothing
  until `battle_vision.warm_control()` read the warm control blob beneath it, so the
  pinned geometry is label `(1060,738,66,30)` versus control `(1038,771,121,133)`.
  The auto-assign bands also had to widen (`.58-.74` / `.58-.75`) because the board
  shifts the buttons to x 1300-1362; both layouts are pinned.
- Blocker found and stopped on: after the victory sequence the HUD shows `TURN 3`
  with `Win Rate`/`Damage` present but never a `START`. Eight successive bounded
  `auto_assign` clicks produced no state change, so the loop was stopped and the
  stepper now reports `auto_assign_had_no_effect` instead of repeating it. Whether
  that turn needs a manual skill assignment, a different control, or is an
  end-of-battle state is undetermined; no further input was sent.
- Not claimed: no floor clear, no reward receipt, no rotation or re-entry. The run
  remains mid-battle at turn 3.

## 2026-10-06 authorized entry into the first battle from the map

- With the same gated authorization, one click on the pre-battle team page's
  `Battle!` action (`battle_box (1674,859,144,44)`, sampled target `(1755,883)`,
  delay `689ms`, foreground unchanged) started the run's first battle. The team page
  was the one reached from the map node, showing `Preset #1 / Zilu/Zigong` with
  `2/12` participants; the user authorized proceeding exactly as shown.
- Successor page: the combat HUD — `WAVE` `(16,39,54,30)` and `TURN` `(18,95,44,24)`
  captions with the `Win` / `Rate` / `Damage` readouts, skill slots with SP counters
  and the twelve-slot party bar (`evidence/runtime/team-page-battle-20261006-010230/frame-0007.png`).
  So the real entry chain is: map click -> node info panel -> `Enter` -> pre-battle
  team page -> `Battle!` -> combat.
- `map_vision.pre_battle_team_page()` / `battle_target()` identify that page from its
  own `Clear Selection` and `Battle!` captions (participant counts recorded as
  context), and the agent now reports scene `PRE_BATTLE_TEAM` instead of the generic
  `TEAM_LIBRARY`. `battle_vision.battle_hud()` identifies the combat HUD from its
  `WAVE`/`TURN` captions and the agent reports scene `BATTLE_HUD`; its gold bitmap
  values are recorded as `None` when this OCR misses them rather than being guessed.
- Not claimed: no turn was submitted, no skill was selected, no damage, victory,
  floor clear, reward or rotation follows from this. Android touch battle control is
  **not implemented** (the Windows `P`-key planning path is forbidden on Android by
  `docs/design.md`), so the battle is parked awaiting a decision.

## 2026-10-06 authorized single-node probe and the panel -> team flow

- With an explicit user authorization and the gated probe (nonce in
  `build/map-probe-authorization.json`), exactly one click was sent at the sampled
  target `(997,452)` inside the node requested at `(1005,465)`, delay `481ms`,
  foreground unchanged before and after. Successor: the node info panel, not a
  battle (`evidence/runtime/map-probe-20261006-000748/frame-0002.png`). So a click
  on the map opens a node info panel carrying `Clear Rewards`, an `85` reward icon
  and an `Enter` action; the map pans while the panel is open.
- `src/maalimbus/map_vision.py` gained `node_panel()`/`enter_target()` (identity =
  exactly one `Clear Rewards` caption plus exactly one `Enter` in their own bands;
  title and numeric costs recorded as context only) and the agent promotes that page
  to scene `NODE_PANEL`. A regression pinned to that actual frame asserts the panel
  is not a map header; the retained map frame is asserted not to be a panel.
- A second single click on that panel's `Enter` (`enter_box (1668,780,124,63)`,
  sampled target `(1705,815)`, delay `712ms`) reached the **pre-battle team /
  identity selection page**, not a battle: `Preset #1 / Zilu/Zigong`, twelve
  identity cards with two marked `SELECTED`, right-hand `SIN | COST`, `Details`,
  `Clear Selection`, `Total Participants 2/12` and a `To Battle!` action
  (`evidence/runtime/map-settle-20261006-000930/frame-0001.png`). The production
  classifier reported `TEAM_LIBRARY` for this page, so its scene identity is still
  open.
- No input was sent twice, no key was sent, and no floor clear, battle, reward or
  rotation is claimed. The game is parked on this team page; no preset was changed
  and `To Battle!` / `Clear Selection` were never pressed.
- Open: the team page's true scene identity and its preset-to-saved-team mapping,
  which must be resolved before the rotation ledger's `index 2` continuation can
  select the right team and continue.

## 2026-10-06 upstream and live comparison of the map node grid

- Pinned LALC 431b432 ships two trained classifiers: `mirror_legend` with eight node
  classes (abnormality/boss/elite/focused/regular encounter, event, shop, empty) and
  `mirror_path` with nine `00..22` cells over six regions. This is recorded as
  reference vocabulary only; no model or weight is imported.
- `tools/compare_lalc_map_regions.py` sampled LALC's six path regions on the live
  MuMu capture at the 1440x810 authoring scale and at half scale. The six slots fall
  in the dark upper-left quadrant (bright ratios 0.0000-0.0814) while the drawn nodes
  span a wider area, so LALC's coordinates are not this page's node coordinates. The
  comparison is read-only and sends no input (`build/map-region-comparison.json`,
  `build/map-region-annotation.png`).
- Consequence kept explicit: node identity, the panel's cleared/uncleared meaning and
  the option-selection successor are all still unproven, so no node is clicked. The
  first step of any live continuation must be a single observed-node click with its
  successor page recorded, not an assumed grid.

## 2026-10-06 live MuMu verification of the map identity

- A read-only MuMu probe (`tools/probe_adb.py`, actual address `127.0.0.1:16416`,
  foreground `com.ProjectMoon.LimbusCompany`, input method `Null`, no input) shows
  the game is still on `Exploring Floor 1 / To be Cleaved`, 7548 Starlight and 600
  Enkephalin, matching the retained `231221/terminal.png` state.
- `tools/verify_map_live_crosscheck.py` ran the real Maa OCR over that live capture
  and over the retained frame: both classify as scene `MAP` and both identify floor
  `1` with pack `To be Cleaved`; the header box scales exactly 1.5x between the
  1280x720 and 1920x1080 captures. No controller input in either run
  (`build/map-live-crosscheck-verification.json`).
- `tools/map_live_observe.py` then executed the real pipeline node against the live
  emulator through an `Maa AdbController` with `Null` input: scene `MAP`, floor `1`,
  pack `To be Cleaved`, and route `current_position_not_proven` with `next_node`
  null. `stop_confirmed` true and no click, swipe or key was ever sent
  (`evidence/runtime/map-live-20261006-000159/result.json`).
- The node is now the first legal continuation from the stopped session:
  `MapObserve` (DirectHit, `limbus_map_observe`, `max_hit` 1, `on_error`
  `LimbusUnknown`) in `assets/resource/base/pipeline/mirror.json`, with its action
  registered in `tools/run_native.py`. `tools/verify_map_observe_replay.py` replays
  that exact node: the map frame succeeds with zero input, the pack page fails
  closed (`build/map-observe-replay-verification.json`).
- Still unproven and still un-clicked: node identity, current-position proof, floor
  routing, battle, floor clear, reward and rotation. Route stays an explicit
  refusal until a live frame proves a current position and an unvisited node.

## 2026-10-05 offline map identity repair

- `src/maalimbus/map_vision.py` now identifies the Mirror Dungeon map page from the
  localized floor header plus the theme-pack line beneath it; artwork, currency and
  season icons are never anchors. `agent/recognition.py` promotes only that page to
  scene `MAP`, and `ThemeObservation` records `theme_map_postcondition` with
  `selected` true solely when the fresh floor header names the pack this run planned.
- Actual Maa OCR/recognition replay over the retained `231221/terminal.png` (binary
  `build/portable check 249aba9398a84dbfacd55c2b79065cd7/maafw`) identifies scene
  `MAP` and hits only `OfflineMapHeader`; the retained pack page is not promoted and
  hits no map node. The replay controller asserts that click/swipe/touch/key are
  never called: `build/map-frame-replay-verification.json`, no device input.
- Route reading stays an explicit refusal. The retained map frame shows no provable
  unvisited node, so `route_decision` returns `current_position_not_proven` and
  records no click target; `tools/verify_map_replay.py` deliberately sends no input.
- 153 Python tests pass (145 before this change). Node identity, floor-1 routing and
  any live continuation from the stopped session remain unproven and unauthorised.

## 2026-10-05 23:13 actual downward pack selection

- Real-frame Maa intercepted replay passed five cases: one downward Swipe on the
  original230455/frame-0001.png, zero on missing mode/header/Refresh and altered
  covers with uncertain HARD OCR. No device in replay; unchanged post-frame keeps
  selected false. Terminal frame OCR also failed closed, retained as a robustness
  issue rather than a threshold relaxation.
- Actual MuMu session231221 used Maatouch once to drag To be Cleaved downward,
  after foreground/process/lease checks. Fresh terminal.png visibly proves entry
  into Exploring Floor1 / To be Cleaved map. Result stoppedconfirmed, UNKNOWN,
  verified_clear false. Map classification/routing must be repaired offline before
  further input. This is live pack-selection evidence, not floor completion.

## 2026-10-05 23:05 free receipts and Hard selection page

-224322 acknowledged first named free gift, exposing the second named receipt.
  224508 acknowledged second receipt, exposing extra gift search. Fresh224916
  verifies both Owned labels and distinct catalog icons; this is initial gift
  ownership evidence, not final dungeon rewards. Unknown new page stopped input
  until classification and ownership proof were repaired offline.
-225222 refused extra gift search at0/3 and zero selected cost.225439 confirmed
  Forgo;225512 read-only capture showed Normal floor1 packs.230146 toggled Hard
  once; highlighted mode recognition failed closed and was repaired offline.
  230455 fresh native proof confirms HARD, clears only difficulty pending, and
  retains `terminal.png` with all three pack names. No pack drag has occurred.
- Latest complete Python suite:145 passed. Maa replay checks cover wrapped receipt
  names, Owned icon identity, modal veto, free-search refusal and highlighted Hard
  mode. Derived images are not live selection or map proof. User's downward-drag
  instruction agrees with native Swipe; actual-frame geometry validation and live
  map postcondition remain pending. No floor or final reward is accepted.

## 2026-10-05 22:36 initial gifts

- Read-only actual MuMu222911 unchanged at0/2. Native223048 clicked the independently
  OCR-identified Bleed header for saved team1, exposing three actual candidates.
- Native223230 selected first priority Wound Clerid. Read-only proof task223418
  verified fresh exact title, row1 selection border and1/2; uncertain intent was
  retained until that proof. Native223506 selected second priority Little and
  To-be-Naughty Plushie; fresh exact title, rows1/2 and2/2 confirmed in-frame.
- Native223639 submitted2/2 once. Actual terminal screenshot shows Wound Clerid
  E.G.O Gift GET modal. Task is stoppedconfirmed; no receipt Confirm sent yet.
  Retained private pending prevents repeat Commit. Gift GET does not prove any
  floor clear or Enkephalin-module reward receipt.
- Actual Maa intercepted group/pick/proof/commit replays passed original/changed
  icon cases and rejected missing counters, wrong profile/foreground, wrong title
  and absent selection marker. No incomplete/unverified intent is reset by replay.
  Retained GET observation native Maa OCR passed with zero input; GET title without
  independent Confirm vetoes underlying selection UI. Python full143 passed before
  last veto change;12 focused tests passed afterwards.
- Next: bounded per-gift acknowledgements, actual Hard difficulty and floor1 entry;
  all remaining full-goal acceptance remains open. FGO was not reopened.

## 2026-10-05 22:27 MuMu star stage

- Latest usage refresh allowed ordinary work (58% five-hour/76% weekly consumed).
  No credits purchase/reset. Verified one foreground Android package and shared
  controller lease for each bounded session. CLI now records its actual Windows
  executable/PID/integrity before constructing the controller; latest PID35540
  ended with `stop_confirmed:true`. No MaaLimbus/FGO controller remained in CIM.
- Real entry confirmation, saved team1 row/header confirmation, low-level warning
  and star page retained in215631,220118,220441 sessions. Tutorial was already
  absent at the relevant initial frames: no native tutorial-exit success claimed.
- Real single-choice sessions222020/222045/222108/222131 selected Lix1,3,4,6.
  Each fresh available balance matched prior minus10/20/30/40, ending7. No Enhance.
- Session222313 entered the confirmation modal and stopped; its default conversion
  was checked. Session222509 disabled it; actual terminal frame shows unchecked
  checkbox and Cost0. Session222652 confirmed and actual terminal capture shows
  initial E.G.O Gift selection, count0/2. All are retained real Maa captures, not
  derived images. Owned7541 is visible before confirmation; final settlement and
  clear still unproved. No gifts/floors/rewards have been accepted yet.
- `build/star-replay-verification.json`: source/changed-buff/derived-balance plus
  missing-grid/over-budget/pending-input. Derived balance is explicitly synthetic.
  Entry/conversion/confirmation replay reports retain native Maa OCR/TemplateMatch
  with intercepted clicks and zero-input negative cases. Full suite143 passed.
- Local Lix import saved/read back seven profiles and preserved rotation/deployment;
  latest user's1,3,4,6 overrides older1,4,5,6. Highest-level compatible identity policy
  is offline-only; no actual automatic roster/filter/identity-switch acceptance yet.
- Remaining: initial gifts/native Hard floors1–5, reward receipt and module budget,
  team rotation/re-entry, native automatic formation/MXU settings, JP real pages,
  Windows/PI/package/update validation and FGO error option/Release. Goal stays active.

## 2026-10-05 MuMu continuation

- Usage allowed: 26% five-hour and 72% weekly consumed at start. No credits bought/reset.
- Clean initial git state; latest previous Limbus evidence was October 1. Old recorded
  PID39436 absent. New controllers65148/47524 paths/arguments/parents read via CIM;
  shared OS lease held throughout and confirmed task stop before subsequent observation.
- Maa AdbController Encode screenshot + Null input captured already foreground Android
  `com.ProjectMoon.LimbusCompany` at 1920x1080. No game restart.
- Maatouch actual navigation: HOME -> Drive -> mirror entry. Retained original and
  changed-art home/menu frames pass actual Maa OCR/Pipeline with intercepted clicks;
  missing independent anchor produces zero input. Random inset targets and 180..480ms
  pre-delay retained in recognition journals. Full suite128 passed before tutorial guard.
- Enter was attempted against underlying text while a tutorial was present. Postcondition
  did not occur; session stopped confirmed. Read-only terminal frame proves tutorial remains.
  Added tutorial veto; dismissal and this final guard require offline/native verification.
- `evidence/runtime/live-20261005-214739`, `live-20261005-215020`,
  `adb-probe-20261005-215059`; `build/home-replay-verification.json`,
  `build/drive-adb-replay-verification.json`. No resource purchase/refill/conversion.
- No five-floor clear, reward receipt, deployment/rotation/re-entry, JP live acceptance,
  MXU Android preflight integration, new Windows package or FGO Release claimed.

## Custom deployment choices and callback failure boundary

- Twelve PI child dropdowns apply only in custom mode. All twelve positions must
  be complete and unique before atomic save; other teams/preferences are retained.
- A derived replay exposed an exception escaping Maa's ctypes callback and
  continuing old-order selection. All recognition/action callbacks now explicitly
  fail and latch the Agent instance closed, even if journal writes fail.
- 125 tests, 17 actual Maa derived deployment cases and seven battle-planning
  regressions pass. Six callback faults produce zero clicks, no order proof or
  battle start. `build/deployment-replay-verification.json` retains actual errors.
- Clean d14d119 Windows development package: 622 manifest hashes/self-test pass.
  Nine frozen-Agent deployment IPC cases pass, including custom save and five
  invalid-config/evidence cases with zero input. Four frozen-Agent battle
  regressions pass (1/1/0/0 P), plus three source navigation regressions.
  `build/packaged-deployment-replay-verification.json`,
  `build/packaged-battle-replay-verification.json`, `build/battle-package-integrity.json`
  retain this package's scope. No release, game controller, GUI replacement or UAC.
- The old 08c2adc GUI exited normally. Actual d14d119 MXU displays positions1..12;
  changed positions1/3 survive normal exit/restart, with all twelve persisted
  options identical. New GUI PID23688 is disconnected, one unchecked task,
  auto-run false; no live game task, input or UAC. Frozen Agent replay resolves
  these actual saved choices against installed PI, saves the full order and
  selects the first three derived slots while retaining the other team/preferences.
  `build/native-deployment-ui-verification.json` and
  `build/mxu-deployment-options-replay-verification.json` retain evidence.
  GUI Start dispatch and live geometry remain unverified; five floors/rewards/
  rotation are incomplete. Game remains HIGH/minimized; no permission bypass.

Each requirement needs implementation plus matching verification scope. Status is not inferred
from a task returning success, a manifest loading, or a process staying alive.

| Requirement | Current status | Required evidence |
| --- | --- | --- |
| Maa Win32 native input/screenshot | Capture verified; live input blocked by game HIGH vs Maa MEDIUM integrity | Running game capture and recognized click with page postcondition |
| PI V2 labels and EN/JP resources | Maa resources parsed; native Chinese MXU/controller/task/12-position display verified; EN/JP game acceptance pending | Actual Maa parser + MXU UI |
| Variable cover/background recognition | Actual Maa saved-frame replay: reference, changed cover, unknown | Four supplied frames + live frame; negative and changed-art replay |
| Saved teams / deployment / rotation | Library and experimental deployment-order derived replays passed; profiles persist; live deployment/rotation pending | Save/restart persistence + two different confirmed dungeon teams |
| Five hard floors | **Verified live 2026-10-07**: `build/live-after-victory.png` is the "Exploration Complete" settlement with Floor 1..5 each 6/6, Total Progress 100%, Last Reached "Mirror of Names and Spiders / Floor 5 [NORMAL]" | Floor 1..5 battle and completion observations |
| Battle planning / turn execution | Live Win Rate auto-assign plus START turn submission and the victory/result screens (`BATTLE_VICTORY`) are driven live (`build/window-run99.json`, `build/window-run101.json`); full selected-skill/clash/survival proof still pending | Full selected-skill/clash/survival proof + actual turn and victory/map return |
| Rewards then repeat | **Verified live 2026-10-07**: the settlement's Claim goes `RUN_CLAIM` -> `RUN_REWARD_DIALOG` -> `RUN_REWARD_CONFIRM` (`build/window-run104.json`), then the window walks home -> Drive -> mirror entry -> entry confirmation -> the rotation slot on `DUNGEON_TEAM` -> grace/gift/theme -> map again (`build/window-run106.json`) and a second run is in progress (`build/window-run108..110.json`); advancing the rotation **ledger** to the next team is still the fixed `--team` argument | Reward receipt and next-run entry with next team |
| Gifts / enemy buffs / theme pack selection | Floor gifts and weighted theme-title/native drag derived replays passed; enemy buffs and full-loop integration pending | Live selection quota, confirmation, acquisition and next-floor postcondition |
| Human-paced jitter and bounded sessions | Finite Maa node hits; inset clicks/delays, bounded setup/stop jobs and monotonic CLI deadline tested | Full-run cancellation and timeout checks still required |
| Stamina conversion / refill budgets | Pure budget boundaries passed; no spending implementation yet | Zero-spend default, budget boundaries and balance postconditions |
| Mail / daily rewards | Design | Claimed/empty mailbox and mission reward evidence |
| GitHub update / rate-limit resume | Metadata/cache and isolated download/checksum/manifest staging implemented; 612-file development ZIP offline staging passed. MXU UI and installer pending | Public asset download + installed version/config preservation + rollback |
| Windows package | Local development package built; packaged Agent IPC replay passed; MXU UI/live acceptance and release audit pending | Portable build + actual UI/runtime + installed version/config preservation |
| FGO error option and Release | Error option built/installed, config preserved; actual GUI exit + public Release pending | Option persistence/error action; full release gate + published asset |

## 2026-10-01 evidence

- 39 tests passed (policies, profile/ordered run persistence, Windows identity,
  team positions, EN/JP strings, GitHub deadlines and error/cache behavior;
  includes a real Windows two-process controller-lock exclusion test).
- Actual Maa 5.12.2 parser/OCR/Pipeline: three navigation replay cases and six team
  library cases passed. The #2 title change and resource dialog are derived fixtures.
  Already selected, missing slot, stuck click, paid dialog and unknown behavior are
  verified offline. User frame #2 is the Sinners library, not dungeon deployment.
- Live read-only Windows process identity: game integrity RID 12288; controller
  RID 8192. Earlier Seize calls did not change the page. All task entries now check
  identity/privileges before input. No new live click attempted after this finding.
- `build/native-replay-verification.json`, `build/team-replay-verification.json`,
  `build/windows-preflight.json` are local evidence, excluded from release.
- FGO prepublish audit returned ready with a missing-project-license warning;
  this is a privacy/source-tree audit, not full-suite or release validation.
- FGO's full current Python suite subsequently passed 710 tests after stale
  controller-scenario timing/retry assertions were corrected. Production behavior
  unchanged. Error options, license and release package/publishing are still pending.

## Runtime bounds refresh

- 43 tests pass, including finite pending setup/stop jobs, timeout cancellation,
  interrupted sessions and the distinction between task status and dungeon clear.
- CLI setup/load time now consumes the same monotonic session budget; wall-clock
  changes cannot extend it. If a stop does not complete, `stop_confirmed` remains
  false and the controller lease stays held until the process exits.
- Game PID40196 is still HIGH integrity RID12288; the inspected Python controller
  is MEDIUM RID8192. This is a read-only refresh, not a new live attempt.

## Floor-gift recognition refresh

- 48 tests pass. Imported 332 public cropped gift icons from pinned LALC with
  per-file hashes/source paths and keyword groups. Only local reward labels,
  ownership strips and gift icons are considered; covers/identities are not.
- The production recognizer supports `FLOOR_GIFTS` / `gift_mode: recommend` with
  a configured team. Owned is associated by column, block-list wins, uncertain
  titles/icons and overlapping candidates are refused. The default rank remains
  unowned preferred → unowned other → owned. Each ranking retains target/provenance
  and explicitly sets `selected=false`, `reward_received=false`.
- Actual Maa OCR/CustomRecognition/Click routing passed five derived public-icon
  cases: preferred, owned preferred, all blocked, paid zero-input and icon-only
  identity with the JP resource. This does not verify Japanese rendered text,
  selection quota, reward confirmation/receipt or a live floor transition.
  The helper is not yet wired into the full dungeon loop.
- Three navigation and six team-library Maa replay regressions passed. Private
  local result: `build/gift-replay-verification.json`.
- Original FGO installation is now clean 36e2f79, with nine configuration files
  preserved and a retained rollback directory. Packaged Agent replay passed;
  GUI error-option/exit and public Release remain unverified/unpublished.

## Native Windows launcher and continuation schedule

- Compared MaaEnd's published `assets/interface.json`: Win32 foreground/background
  controllers declare `permission_required: true`. LALC's `update_to.bat` starts
  its application with standard Windows `RunAs`. MaaLimbus now declares the same
  permission requirement and includes `tools/start_native.ps1` with normal UAC.
- Launcher/wrapper scripts parse successfully. The wrapper invokes only the native
  bounded Maa CLI, records separate stdout/stderr, and enforces the exact created
  process's outer deadline. Identity and one-controller gates are preserved.
- A real UAC request was issued this turn; Windows returned operation cancelled.
  No new wrapper/runner or live transition was established. No permission was
  bypassed and no second request was issued. The game remains at Before Entry.
- App heartbeat `maalimbus` is active every 30 minutes on the current thread.
  It checks usage availability and resumes the entire goal after limits recover,
  remaining quiet on unchanged/limited state. This is scheduling proof, not proof
  of future executions or live dungeon completion.

## README and license reference correction

- Chinese/English README now follows the pinned MaaFramework title/badges/language,
  introduction/start, statements/licenses, development, acknowledgements and
  communication structure. Actual feature coverage remains explicit.
- Original MaaFramework LGPL and Lix AGPL notices remain; the GNU GPL v3 text
  referenced by LGPL has been added. Main-project AGPL was a project choice,
  not a framework requirement; no third-party material was relicensed.
- `docs/readme-license-reference.md` maps the user's four specified references
  to the current application and lists remaining packaging/artwork rights gaps.
  Documentation alignment is not evidence of live completion or release readiness.

## Local Windows package and packaged IPC verification

- Fixed frozen Agent/Runner root resolution and import-time native library setup.
  Packaged resources are resolved from the executable's installation, not cwd or
  PyInstaller extraction. EN/JP and gift catalog load from the actual package.
- 57 tests passed, including installed path resolution, unsafe archive prevalidation
  and public source archive privacy exclusions. Two packed executables built.
- Actual Maa AgentClient connected to the packaged Agent. Installed resource/OCR/
  Pipeline passed reference navigation (two replay clicks, TEAM_LIBRARY boundary)
  and UNKNOWN (zero input). Both preserve `verified_clear: false`; no Win32 game
  controller was constructed. Record: `build/packaged-replay-verification.json`.
- Local development ZIP manifest verified; source/third-party notices are included.
  Builder never overwrites an install or publishes a release. Current game process
  remained HIGH integrity 12288 vs controller MEDIUM 8192; no UAC was requested.
- Actual MXU UI, live input, five floors/rewards/rotation and complete source/asset
  redistribution audit remain pending. This is a local development packaging gate.

## Native theme-pack selection

- Stable five-glyph/title recognition replaces whole-card matching; 95 pinned
  names, team-specific weights and zero-weight blocks persist in old-compatible
  profiles. PI selects names/weights from choices and writes independent nodes.
- Actual Maa production graph replay passed seven derived cases: save/read
  preference, changed artwork, NEW exclusion, unknown, NORMAL, paid, all blocked.
  Three permitted cases route exactly one native Swipe; four negative cases send
  zero input. After dragging a fresh frame is observed and the task intentionally
  stops with `selected=false` / `verified_clear=false` at the unfinished map boundary.
- Fixed short-title OCR boxes extending several pixels past the card; bounded
  padding permits that case without accepting adjacent titles. Fixed option
  overrides replacing custom parameters and losing their mode/other settings.
- `build/theme-replay-verification.json` retains local scope and frame provenance.
  No UAC/game input was requested. Japanese rendered titles, live selection,
  difficulty switching/refresh policy, deployment/battle and complete loop remain pending.
- 68 unit tests and six team-library Maa regression cases passed. New Windows
  development package from clean `4178821` includes the theme component: 611
  manifest hashes/privacy checks and Agent self-test pass. Frozen Agent IPC
  confirms saved team 2 keeps its name/other weights while updating one choice;
  native drag and paid zero-input cases pass using installed resources.
  `build/packaged-theme-replay-verification.json` and `build/theme-package-integrity.json`
  retain evidence. The GUI was not opened, no game input was sent, and game
  PID40196 remains HIGH 12288 vs inspected controller MEDIUM 8192.

## Experimental native deployment preparation

- Added a separate opt-in preparation task using saved team order, with explicit
  standard-order persistence. Count must be recognized, agree with all local
  ordinals and match the desired prefix before each next click. No 0/1 fallback,
  reset or battle-start input. Unconfirmed selections are not clicked again.
- Actual Maa production graph passed ten derived cases including saved/preset,
  resume, already complete, wrong order, missing count, paid, stuck, missing badge
  and unconfigured. Small standalone digits missed by full-frame OCR are handled
  by local `only_rec` with retained ROIs. 79 unit tests pass.
- `build/deployment-replay-verification.json` is offline evidence. Grid centers
  come from pinned Lix; badge strips are experimental, not live-validated geometry.
  Capacity semantics for overflow, actual sinner identity, Japanese rendering,
  battle start and five-floor/reward/rotation acceptance remain pending.
- Clean `ded609b` Windows development package built; 612 manifest hashes,
  private-data exclusions and Agent self-test pass. Frozen Agent over Maa IPC
  verifies ordered choice, stuck no-repeat and paid zero-input cases with saved
  team 2/name/keywords/weights preserved. Records:
  `build/packaged-deployment-replay-verification.json` and
  `build/deployment-package-integrity.json`. Three reference navigation/changed
  cover/UNKNOWN regression replays also pass. No live controller or UAC request.

## GitHub update staging

- Shared ZIP prevalidation now also refuses Windows device names/data streams,
  invalid characters, existing extraction destinations and file/directory collisions.
  The downloader accepts only one stable package/checksum pair from the selected
  GitHub repository/tag, checks metadata sizes/digests, checksum and all manifest
  files, and refuses private config/evidence roots or unlisted files.
- HTTP download failures persist safe retry state; restart during a rate-limit
  delay performs no download. Incomplete `.part` files are removed only from the
  newly created stage. Failed full archives/extracted contents remain quarantined
  with `status=failed`; neither a failure nor `staged` executes/replaces an install.
- 103 tests pass. `build/update-stage-verification.json` proves complete staging
  of the actual retained clean `ded609b` development ZIP, with its original
  hash and all 612 manifest files. Release metadata and transport were derived
  offline fixtures; no public stable Release or live network download was tested.
- Game PID40196 remains HIGH 12288 vs current Python MEDIUM 8192, recorded in
  `build/update-development-preflight.json`. No game input/GUI/UAC was requested;
  no active MaaLimbus Agent/Runner found. Full dungeon acceptance remains pending.
- See `docs/update-staging.md`. MXU update integration, actual install/rollback,
  source/asset distribution audit and public Release remain pending.

## Experimental native battle planning

- Four pinned small glyphs retain source hashes/notice; one English win-rate
  marker and local damage glyph(s) are required. Resource/defeat classification
  wins; duplicates/missing markers and Japanese resources refuse input.
- Seven actual Maa derived cases passed: plan/stuck each exactly one P, five
  negative cases zero input. A fresh changed frame/Neutral OCR observation is
  retained, but plan/coverage/turn/victory/clear remain false. No Enter/EGO/mouse
  action; an unchanged page is not retried. 112 unit tests pass.
- Three navigation regressions passed from retained normalized Maa frames,
  with source mapping in `build/battle-navigation-regression-refs/provenance.json`.
  The replay helper avoids double resampling these images (`--prepared-frames`);
  raw reference handling is unchanged. UNKNOWN remains zero input.
- `build/battle-plan-replay-verification.json`, `docs/battle-planning.md` retain
  offline scope. Live glyph/ROI/skill coverage, Japanese UI, EGO/survival, turn
  execution and victory/map return are unverified; MirrorHard still stops at entry.
- Read-only `build/battle-development-preflight.json`: game PID40196 HIGH12288,
  current Python MEDIUM8192. No UAC/game input/GUI/live task was started. Latest
  frozen development ZIP remains `ded609b`, not this battle-planning code.

## Packaged battle planning refresh

- Clean `8b309b8` development package built with 619 manifest file hashes,
  private-root exclusion and actual frozen Agent self-test passing. Maa IPC
  installed production graph passed four derived cases: normal/stuck one P each,
  resource/unsupported JP zero input. Normal frame Neutral text retained; plan,
  skill coverage, turn, victory and clear assertions remain false.
- `build/battle-package-integrity.json`, `build/packaged-battle-replay-verification.json`
  and `build/windows-package-latest.json` point to the new package. No GUI/game
  input, UAC, installation replacement or public publication occurred.
- New ZIP also passed isolated offline staging with all 619 hashes/ZIP checksum
  checked; `build/update-stage-verification.json` now describes `8b309b8`. Metadata
  and transport are derived fixtures, not published-release/download evidence.
- All verification Agent children exited; CIM found only game PID40196/parent18536.
  Read-only `build/packaged-battle-preflight.json` still records game HIGH12288 vs
  controller MEDIUM8192. Full five-floor/reward/rotation acceptance remains pending.

## Reference control profiles and actual native UI

- Clean `08c2adc` package: 622 manifest files and frozen Agent self-test pass.
  Its four actual Maa IPC regressions pass with keys 1/1/0/0; no game controller.
- Compared MaaEnd `850e5fa` PI source and Lix `431b432` input defaults/launcher.
  Window/background/foreground combinations now match MaaEnd, with the existing
  `windows` name retained. CLI reads the same PI configuration. 114 tests pass.
- Opened the actual unmodified MXU executable. Native screenshots confirm the
  generated Don Quixote window/title icon, Chinese labels, all three controller
  choices and the five current task entries. Language and log retention survive
  restart. UI smoke actions only dismissed welcome/onboarding and opened the
  task picker in the bound MaaLimbus window; no task was added or started.
- `build/native-ui-verification.json`, `evidence/runtime/native-ui-chinese-check/main-frame.png`
  and the actual package debug logs retain display evidence. GUI PID52748 is
  still open; no Agent/Runner is alive. This proves UI display, not live game input,
  team settings execution, update installation or the complete MirrorHard loop.
- Fresh game identity remains PID40196 HIGH12288; GUI MEDIUM8192. Game is
  minimized with 0x0 client area; FramePool/Background capture attempts failed.
  Both access-denied and empty-window evidence are retained, not reduced to a
  speculative single cause. No new UAC or game input was sent.
- Full five-floor combat/reward/rotation integration and real-game acceptance
  remain incomplete. FGO was not reopened. New PNG branding does not change the
  executable's embedded Explorer icon; the running MXU window uses the PI icon.
