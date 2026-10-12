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


# --- sinner names come from the one canonical numbering ------------------

def test_sinner_name_uses_the_single_canonical_numbering():
    assert teacher.sinner_name(1) == 'Yi Sang'
    assert teacher.sinner_name(12) == 'Gregor'
    with pytest.raises(ValueError):
        teacher.sinner_name(0)
    with pytest.raises(ValueError):
        teacher.sinner_name(13)
