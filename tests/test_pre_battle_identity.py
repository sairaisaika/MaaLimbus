"""Tests for the two independent pre-battle identity teachers.

The module under test feeds correctness claims about the live team screen, so
every test here has the same goal: prove that an identity is only ever claimed
from evidence that never reads the detector, and that a gap stays a gap.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maalimbus import pre_battle_identity as teacher

INDEX = Path(__file__).resolve().parents[1] / 'assets/resource/base/identity-index.json'


@pytest.fixture(scope='module')
def index():
    return json.loads(INDEX.read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def aliases(index):
    return teacher.alias_index(index)


def token(text, cx, cy, score=.95):
    return dict(text=text, box=[cx - 20, cy - 10, 40, 20], score=score)


# --- geometry: a slot is a fixed grid position, never a list index --------

def test_every_slot_has_a_fixed_origin_from_the_search_grid():
    origins = [teacher.card_origin(slot) for slot in range(12)]
    assert origins[0] == (350, 225)
    assert origins[1] == (548, 225)
    assert origins[6] == (350, 523)
    assert len(set(origins)) == 12


@pytest.mark.parametrize('slot', [-1, 12, 100, None, '3', 3.0, True])
def test_an_invalid_grid_slot_is_refused(slot):
    with pytest.raises(ValueError):
        teacher.card_origin(slot)


def test_band_and_badge_rois_are_absolute_for_their_own_slot():
    assert teacher.title_band_roi(1) == [548 + 0, 225 + 180, 190, 105]
    assert teacher.corner_badge_roi(6) == [350 + 140, 523 + 4, 44, 44]


# --- the level band is read, never guessed -------------------------------

@pytest.mark.parametrize('text,value', [
    ('Lv.60', 60), ('lv.55', 55), ('LV.1', 1), ('Lv.100', 100),
    ('Lv. 60', 60), ('Level 60', None), ('60', None), ('Lv.1000', None), ('', None),
])
def test_level_value(text, value):
    assert teacher.level_value(text) == value


# --- one slot reads only its own cell and windows ------------------------

def test_read_caption_keeps_this_cards_own_title_and_level_only():
    slot = 7
    x, y, _, _ = teacher.card_box(slot)
    tokens = [
        token('Lv.60', x + 90, y + 175),
        token('Heishou Pack -', x + 90, y + 205),
        token('Wu Branch Adept', x + 90, y + 235),
        token('Lv.60', x + 90 - 198, y + 175),          # the neighbouring card
        token('Yi Sang', x + 90, y + 100),               # above the caption window
    ]
    reading = teacher.read_caption(tokens, slot)
    assert reading['slot_state'] == 'measured'
    assert reading['card_state'] == 'measured_card'
    assert reading['level'] == 60
    assert reading['caption'] == 'Heishou Pack - Wu Branch Adept'
    assert [t['text'] for t in reading['caption_tokens']] == [
        'Heishou Pack -', 'Wu Branch Adept']
    assert 'Yi Sang' in reading['rejected_tokens']


def test_reading_order_sorts_by_line_then_column():
    tokens = [token('B', 200, 300), token('A', 100, 300), token('C', 100, 500)]
    ordered = teacher._reading_order(tokens)
    assert [t['text'] for t in ordered] == ['A', 'B', 'C']


def test_two_level_bands_in_one_cell_leave_the_level_unknown():
    slot = 0
    x, y, _, _ = teacher.card_box(slot)
    reading = teacher.read_caption(
        [token('Lv.60', x + 90, y + 175), token('Lv.55', x + 90, y + 195)], slot)
    assert reading['level'] is None
    assert len(reading['level_tokens']) == 2


def test_a_caption_with_no_readable_token_is_none_not_an_empty_card():
    reading = teacher.read_caption([], 3)
    assert reading['caption'] is None
    assert reading['caption_tokens'] == []
    assert reading['slot_state'] == 'measured'


def test_a_missing_slot_is_explicitly_missing_never_empty_or_unknown():
    row = teacher.missing_slot(11, 'no_card_border_measured')
    assert row['slot_state'] == 'missing'
    assert row['card_state'] == 'missing_grid_slot'
    assert row['missing_reason'] == 'no_card_border_measured'
    assert row['caption'] is None and row['level'] is None


# --- the caption teacher resolves against the revisioned public index -----

def test_the_real_index_yields_one_alias_row_per_locale(aliases):
    assert len(aliases) > 100
    assert {row['locale'] for row in aliases} == {'en', 'jp'}
    assert all(row['alias'] == teacher.normalized(row['title']) for row in aliases)


def test_an_exact_alias_resolves_and_keeps_its_evidence(aliases):
    result = teacher.resolve_caption('Heishou Pack - Wu Branch Adept', aliases)
    assert result['resolved'] is True
    assert result['method'] == 'exact_alias'
    assert result['sinner'] == 'Yi Sang'
    assert result['identity_id'] == 10114


def test_a_shared_base_title_is_ambiguous_for_every_sinner(aliases):
    # Every sinner has an 'LCB Sinner' base identity, so the caption teacher
    # cannot name one of them: this is the honest gap the emblem teacher covers.
    result = teacher.resolve_caption('LCB Sinner', aliases)
    assert result['resolved'] is False
    assert result['reason'] == 'ambiguous_catalogue_alias'
    assert len(result['identity_ids']) == 12


def test_a_short_prefix_never_reaches_the_subsequence_path(aliases):
    result = teacher.resolve_caption('The Very Long', aliases)
    assert result['resolved'] is False
    assert result['reason'] == 'no_catalogue_alias_matches'


def test_an_unresolvable_caption_is_a_named_gap_not_a_guess(aliases):
    result = teacher.resolve_caption('Nowhere Pack - X Branch', aliases)
    assert result['resolved'] is False
    assert result['reason'] == 'no_catalogue_alias_matches'
    assert 'sinner' not in result


def test_a_short_caption_is_refused_before_any_matching(aliases):
    result = teacher.resolve_caption('Lv', aliases)
    assert result == dict(resolved=False, alias='lv', reason='caption_too_short')


def test_exact_only_refuses_what_the_fuzzy_path_would_accept(aliases):
    caption = 'LCB Sinner'
    assert teacher.resolve_caption(caption, aliases, exact_only=True)['resolved'] is False


def test_an_alias_naming_two_identities_is_ambiguous_and_resolved_to_nothing():
    aliases = [
        dict(identity_id=10101, sinner_index=1, sinner='Yi Sang', locale='en',
             title='Twin Title', alias=teacher.normalized('Twin Title')),
        dict(identity_id=10201, sinner_index=2, sinner='Faust', locale='en',
             title='Twin Title', alias=teacher.normalized('Twin Title')),
    ]
    result = teacher.resolve_caption('Twin Title', aliases)
    assert result['resolved'] is False
    assert result['reason'] == 'ambiguous_catalogue_alias'
    assert result['identity_ids'] == [10101, 10201]


def test_a_unique_subsequence_resolves_only_while_it_stays_unique():
    long_title = 'The Very Long Unique Identity Title'
    aliases = [dict(identity_id=1, sinner_index=1, sinner='Yi Sang', locale='en',
                    title=long_title, alias=teacher.normalized(long_title))]
    result = teacher.resolve_caption('The Very Long Unique Identi', aliases)
    assert result['resolved'] is True
    assert result['method'] == 'unique_subsequence'
    assert result['candidate_count'] == 1


def test_the_subsequence_test_requires_order_and_consumes_once():
    assert teacher._subsequence('abc', 'axbxc') is True
    assert teacher._subsequence('abc', 'abc') is True
    assert teacher._subsequence('cba', 'abc') is False
    assert teacher._subsequence('zzz', 'abc') is False
    assert teacher._subsequence('', 'abc') is True


# --- the emblem teacher ranks labelled references only -------------------

def test_a_low_contrast_sample_is_refused_rather_than_matched():
    import numpy as np
    sample = (np.zeros((32, 32), dtype='float32'), .5)
    assert teacher.nearest_badge(sample, [dict(sample=sample, sinner_index=1,
                                                sinner='Yi Sang', source='test')]) is None


def test_nearest_badge_ranks_by_distance_and_reports_its_margin():
    import numpy as np
    near = np.zeros((32, 32), dtype='float32')
    far = np.ones((32, 32), dtype='float32')
    references = [
        dict(sample=(far, 9.0), sinner_index=2, sinner='Faust', source='a'),
        dict(sample=(near, 9.0), sinner_index=1, sinner='Yi Sang', source='b'),
    ]
    best = teacher.nearest_badge((near, 9.0), references)
    assert best['sinner'] == 'Yi Sang' and best['sinner_index'] == 1
    assert best['runner_up'] == 'Faust'
    assert best['margin'] == pytest.approx(1.0)


# --- the measured caption and level bands --------------------------------

def test_the_skill_line_above_the_title_never_joins_the_caption():
    # Measured on 1878 retained frames: the "Entry SP" line's centre sits 183..196
    # below the card origin and the printed title 204..230, so a caption window that
    # starts at 185 lets every slot's skill line into its own title.
    origin_x, origin_y = teacher.card_origin(1)
    tokens = [token('Entry SP +20', origin_x + 90, origin_y + 188),
              token('Heishou Pack - Wu Branch Adept', origin_x + 90, origin_y + 208)]
    row = teacher.read_caption(tokens, 1)
    assert row['caption'] == 'Heishou Pack - Wu Branch Adept'
    assert 'Entry SP +20' in row['rejected_tokens']


def test_a_level_band_in_the_lower_row_is_read_not_dropped():
    # Measured on the same frames: level bands sit at 161..199 or 218..219, so a
    # window that stops at 205 reports no level at all for the lower stripe.
    origin_x, origin_y = teacher.card_origin(7)
    row = teacher.read_caption([token('Lv.60', origin_x + 90, origin_y + 218)], 7)
    assert row['level'] == 60 and row['caption'] is None


def test_a_level_band_below_the_measured_window_is_a_gap_not_a_level():
    origin_x, origin_y = teacher.card_origin(7)
    row = teacher.read_caption([token('Lv.60', origin_x + 90, origin_y + 230)], 7)
    assert row['level'] is None and row['level_tokens'] == []


# --- the twelve-slot report ---------------------------------------------

def test_a_present_slot_outside_the_grid_is_refused():
    with pytest.raises(ValueError):
        teacher.identity_report([], present_slots=[12])


def test_a_repeated_present_slot_is_refused():
    with pytest.raises(ValueError):
        teacher.identity_report([], present_slots=[3, 3])


def test_the_report_always_states_twelve_slots_and_both_lists():
    report = teacher.identity_report([], present_slots=[1, 5])
    assert report['slot_count'] == teacher.SLOTS and len(report['slots']) == 12
    assert report['slot_states'] == {'measured': 2, 'missing': 10}
    assert report['measured_slots'] == [1, 5]
    assert report['missing_slots'] == [0, 2, 3, 4, 6, 7, 8, 9, 10, 11]
    assert report['all_slots_accounted_for'] is True
    assert report['detector_read'] is False
    assert report['teacher'] == teacher.TEACHER
    assert report['schema_version'] == teacher.REPORT_SCHEMA
    assert [row['grid_slot'] for row in report['slots']] == list(range(12))


def test_an_unmeasured_slot_is_missing_and_never_an_empty_reading():
    report = teacher.identity_report([], present_slots=[0], presence_source='no_border')
    missing = report['slots'][1]
    assert missing['slot_state'] == 'missing'
    assert missing['card_state'] == 'missing_grid_slot'
    assert missing['caption'] is None
    assert missing['resolution'] == dict(resolved=False, reason='slot_missing')
    assert missing['missing_reason'] == 'no_border'
    assert report['presence_source'] == 'no_border'
    assert report['unresolved_reasons'] == {'slot_missing': 11, 'no_catalogue_index': 1}


def test_a_measured_card_without_a_catalogue_stays_a_named_gap():
    report = teacher.identity_report([], present_slots=[4])
    assert report['slots'][4]['resolution'] == dict(resolved=False, reason='no_catalogue_index')
    assert report['resolved_slots'] == [] and report['identity_ids'] == {}


def test_a_measured_card_behind_no_ocr_is_a_caption_gap(aliases):
    report = teacher.identity_report([], present_slots=[4], aliases=aliases)
    assert report['slots'][4]['resolution'] == dict(resolved=False, reason='caption_not_read')


def test_no_frame_pixels_yield_no_emblem_references():
    report = teacher.identity_report([], present_slots=[0])
    assert teacher.learned_references(report, None) == []


def test_only_a_resolved_slot_becomes_a_labelled_reference(aliases):
    pytest.importorskip('cv2')
    import numpy as np
    pixels = np.random.default_rng(7).integers(0, 256, size=(600, 1600, 3), dtype='uint8')
    origin_x, origin_y = teacher.card_origin(0)
    tokens = [token('Heishou Pack - Wu Branch Adept', origin_x + 90, origin_y + 208)]
    report = teacher.identity_report(tokens, present_slots=[0, 1], pixels=pixels, aliases=aliases)
    assert report['resolved_slots'] == [0]
    assert report['slots'][0]['badge'] is None
    assert report['slots'][0]['badge_reason'] == 'no_corner_emblem_references'
    references = teacher.learned_references(report, pixels)
    assert [row['grid_slot'] for row in references] == [0]
    assert references[0]['sinner_index'] == 1
    assert references[0]['identity_id'] == 10114
    assert references[0]['caption'] == 'Heishou Pack - Wu Branch Adept'
    assert references[0]['source'] == 'caption_teacher'
    assert references[0]['sample'][1] > 6.0


# --- the two saved-order verdicts ---------------------------------------

def resolution(sinner_index):
    return dict(resolved=True, sinner_index=sinner_index,
                sinner=teacher.sinner_name(sinner_index), identity_id=10000 + sinner_index)


UNRESOLVED = dict(resolved=False, reason='caption_not_read')
LIVE_ORDER = [6, 2, 4, 9, 12, 7, 11, 10, 3, 1, 8, 5]
LIVE_BADGES = [10, 2, 9, 3, 12, 1, 6, 11, 4, 8, 7, 5]


def report_of(rows):
    """A report with the structure the two saved-order verdicts read."""
    return dict(teacher=teacher.TEACHER,
                slots=[dict(grid_slot=slot, resolution=row) for slot, row in enumerate(rows)],
                identity_ids={slot: row['identity_id'] for slot, row in enumerate(rows)
                              if row.get('resolved') is True})


def test_a_saved_order_that_is_not_twelve_sinners_is_refused():
    with pytest.raises(ValueError):
        teacher.agrees_with_saved_team(report_of([UNRESOLVED] * 12), list(range(1, 12)))


def test_the_team_verdict_needs_twelve_resolved_sinners():
    report = report_of([resolution((slot % 12) + 1) for slot in range(12)])
    verdict = teacher.agrees_with_saved_team(report, list(range(1, 13)))
    assert verdict['verified'] is True
    assert verdict['unread_slots'] == [] and verdict['saved_but_not_read'] == []
    assert verdict['read_but_not_saved'] == []
    rows = [resolution((slot % 12) + 1) for slot in range(12)]
    rows[7] = UNRESOLVED
    verdict = teacher.agrees_with_saved_team(report_of(rows), list(range(1, 13)))
    assert verdict['verified'] is False and verdict['unread_slots'] == [7]


def test_the_team_verdict_compares_multisets_not_membership():
    rows = [resolution((slot % 12) + 1) for slot in range(12)]
    rows[0] = resolution(2)
    verdict = teacher.agrees_with_saved_team(report_of(rows), list(range(1, 13)))
    assert len(verdict['read_slots']) == 12 and verdict['unread_slots'] == []
    assert verdict['saved_but_not_read'] == [1] and verdict['read_but_not_saved'] == [2]
    assert verdict['verified'] is False


def test_the_order_badge_not_the_grid_position_ties_a_card_to_its_seat():
    # The retained live frame reads Hong Lu in grid slot 5 and Faust in grid slot 1
    # with badges 1 and 2. Grid-slot alignment would call that a contradiction; the
    # printed badge seats both correctly, and only the badge may be trusted.
    rows = [UNRESOLVED] * 12
    rows[5], rows[1] = resolution(6), resolution(2)
    verdict = teacher.agrees_with_saved_order(report_of(rows), LIVE_ORDER, LIVE_BADGES)
    assert verdict['agreed_slots'] == [1, 5] and verdict['mismatched'] == []
    assert LIVE_ORDER[LIVE_BADGES[5] - 1] == 6
    assert LIVE_ORDER[5] == 7 != 6
    assert verdict['verified'] is False


def test_a_readable_card_whose_badge_is_unread_is_unaligned_not_agreed():
    rows = [UNRESOLVED] * 12
    rows[5] = resolution(6)
    verdict = teacher.agrees_with_saved_order(report_of(rows), LIVE_ORDER, [None] * 12)
    assert verdict['agreed_slots'] == [] and verdict['unaligned_slots'] == [5]
    assert verdict['mismatched'] == [] and verdict['verified'] is False


def test_the_order_verdict_reports_a_real_contradiction_with_both_indexes():
    rows = [UNRESOLVED] * 12
    rows[5] = resolution(6)
    badges = [None] * 12
    badges[5] = 2
    verdict = teacher.agrees_with_saved_order(report_of(rows), LIVE_ORDER, badges)
    assert [row['grid_slot'] for row in verdict['mismatched']] == [5]
    assert verdict['mismatched'][0]['saved_sinner_index'] == 2
    assert verdict['mismatched'][0]['read_sinner_index'] == 6
    assert verdict['mismatched'][0]['read_sinner'] == 'Hong Lu'


def test_an_unresolved_slot_is_unread_even_where_its_badge_is_known():
    verdict = teacher.agrees_with_saved_order(report_of([UNRESOLVED] * 12), LIVE_ORDER, LIVE_BADGES)
    assert verdict['unresolved_slots'] == list(range(12))
    assert verdict['agreed_slots'] == [] and verdict['unaligned_slots'] == []
    assert verdict['verified'] is False


def test_the_order_verdict_is_verified_only_when_all_twelve_agree():
    rows = [resolution(LIVE_ORDER[LIVE_BADGES[slot] - 1]) for slot in range(12)]
    verdict = teacher.agrees_with_saved_order(report_of(rows), LIVE_ORDER, LIVE_BADGES)
    assert verdict['verified'] is True
    assert verdict['agreed_slots'] == list(range(12))


def test_the_order_verdict_refuses_a_short_badge_list():
    with pytest.raises(ValueError):
        teacher.agrees_with_saved_order(report_of([UNRESOLVED] * 12), LIVE_ORDER, [None] * 11)


# --- sinner names come from the one canonical numbering ------------------

def test_sinner_name_uses_the_single_canonical_numbering():
    assert teacher.sinner_name(1) == 'Yi Sang'
    assert teacher.sinner_name(12) == 'Gregor'
    with pytest.raises(ValueError):
        teacher.sinner_name(0)
    with pytest.raises(ValueError):
        teacher.sinner_name(13)
