"""The auto-assignment toggles sit at a measured point, not wherever OCR looks.

The operator's report (2026-10-24): "p（win rate）固定点就好了啊" -- battle is the one
screen whose controls do not move, so pressing a measured point is more reliable than
rediscovering the caption every turn.  These tests pin the measurement, the scaling and
the fallback order: a readable caption still wins, an unreadable one gets the fixed box.
"""

from maalimbus import battle_vision, window

SIZE = (1920, 1080)   # (width, height), the order `find` uses


def _token(text, box, score=.98):
    from types import SimpleNamespace
    return SimpleNamespace(text=text, box=box, score=score, type='Text')


def _box(centre, box):
    x, y, w, h = box
    return x <= centre[0] <= x + w and y <= centre[1] <= y + h


def test_the_measured_points_are_inside_the_archive_spread():
    # Measured over 544/541 archived BATTLE_HUD frames (D107).
    win = battle_vision.TOGGLE_POINTS['win_rate']
    damage = battle_vision.TOGGLE_POINTS['damage']
    assert 1542 <= win[0] <= 1818 and 790 <= win[1] <= 839
    assert 1528 <= damage[0] <= 1832 and 861 <= damage[1] <= 889


def test_the_boxes_contain_their_own_centre():
    boxes = battle_vision.toggle_boxes(SIZE)
    assert _box(battle_vision.TOGGLE_POINTS['win_rate'], boxes['win_rate'])
    assert _box(battle_vision.TOGGLE_POINTS['damage'], boxes['damage'])


def test_the_boxes_stay_clear_of_the_skill_row():
    boxes = battle_vision.toggle_boxes(SIZE)
    for box in boxes.values():
        assert box[1] + box[3] < 900, 'the skill row starts at y 900 on a 1080 screen'


def test_a_smaller_frame_scales_the_same_point():
    boxes = battle_vision.toggle_boxes((1280, 720))
    assert _box((round(1622 * 1280 / 1920), round(816 * 720 / 1080)), boxes['win_rate'])
    assert boxes['win_rate'][2] == 120 and boxes['win_rate'][3] == 44


def test_an_unreadable_caption_gets_the_fixed_box():
    # `MAX` is the battle's own chrome; without it the frame is not the board.
    buttons = battle_vision.auto_assign_buttons([_token('MAX', [1690, 40, 60, 24])], SIZE)
    assert buttons is not None, 'a battle without captions still has its toggles'
    assert _box(battle_vision.TOGGLE_POINTS['win_rate'], buttons['win_rate'])
    assert 'fixed point' in buttons['scope']


def test_a_frame_without_battle_chrome_gets_no_toggle():
    buttons = battle_vision.auto_assign_buttons([_token('Sinners', [120, 380, 96, 22])], SIZE)
    assert buttons is None, 'a page that is not the battle must not offer a toggle'


def test_a_readable_caption_still_wins():
    records = [
        _token('Win', [1600, 796, 40, 21]),
        _token('Rate', [1646, 796, 48, 21]),
        _token('Damage', [1590, 866, 78, 26]),
    ]
    buttons = battle_vision.auto_assign_buttons(records, SIZE)
    # The union of the two caption words, not the fixed point: a caption that reads
    # remains the authority on where the toggle is (D107 keeps this order).
    assert _box((1620, 806), buttons['win_rate'])
    assert _box((1629, 879), buttons['damage'])
    assert 'captions' in buttons['scope']


def test_the_plan_still_needs_a_battle_hud():
    plan = battle_vision.auto_assign_plan([], SIZE)
    assert plan['target'] is None and plan['reason'] == 'battle_hud_not_identified'


def test_a_fixed_point_is_not_evidence_that_a_page_is_the_battle():
    # The click path may stand in for an unreadable caption; the page-identity gate may
    # not, or a frame that is not the board would be read as one (live
    # `tests/test_theme_vision.py::test_regular_battle_requires_numeric_turn_and_both_controls`).
    records = [_token('MAX', [1690, 40, 60, 24]), _token('TURN', [18, 95, 44, 24]),
               _token('5', [68, 90, 30, 30])]
    clickable = battle_vision.auto_assign_buttons(records, SIZE)
    assert clickable is not None and clickable.get('positional') is True
    assert battle_vision.auto_assign_buttons(records, SIZE, positional=False) is None
    assert battle_vision.battle_hud(records, SIZE) is None


def test_a_toggle_plan_asks_for_one_confirming_read():
    # D108: the toggle switches a mode on the same board, so the settle rounds after it
    # would read the same frame; the plan caps them at one.
    for reason in ('win_rate_is_the_proven_auto_assign_control',
                   'damage_is_the_proven_auto_assign_control'):
        assignment = 'win_rate' if reason.startswith('win_rate') else 'damage'
        plan = window.plan_step('BATTLE_HUD', auto_assign={'win_rate': [1602, 794, 120, 44],
                                                          'damage': [1603, 854, 120, 40]},
                                battle_assignment=assignment)
        assert plan['reason'] == reason, plan
        assert plan['settle_rounds'] == 1, plan
    start = window.plan_step('BATTLE_HUD', start_box=[1340, 795, 77, 78])
    assert start['reason'] == 'start_button_submits_the_assigned_turn'
    assert 'settle_rounds' not in start, 'the submit needs its successor read'
