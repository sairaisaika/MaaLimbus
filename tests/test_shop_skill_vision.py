"""Tests for reading the shop's skill-replacement offers off their own frames.

Three independent groups, kept apart on purpose:

* the **retained live shelf** (``frame-0173`` of
  ``evidence/runtime/window-20261012-024300``) is the only real evidence here.  Its
  skill offer reads ``Replace Heathciffs Skill`` at a price badge the OCR only
  scored ``.83``, and both facts must be reported rather than repaired: the apostrophe
  is not silently reinserted into a sinner's name and the threshold is not lowered to
  make the price look confident.
* the **negative** group feeds deliberately broken pages -- a missing badge, two
  badges in one column, a duplicated announcement, a mangled name -- and requires a
  named reason instead of a guess.
* the **subpage** group is synthetic and declared synthetic.  No live replacement
  subpage has ever been captured, so those fixtures prove the reader's contract
  (exact-once fields, catalogue-bound skill ids, Confirm/Cancel pair) and nothing
  about the real game layout.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maalimbus.shop_skill_vision import (DEFAULT_THRESHOLD, FRAME_FIELDS,  # noqa: E402
                                         SUBPAGE_PROTOCOL, SUBPAGE_VERSION,
                                         load_identity_skills, read_frame,
                                         read_shelf, read_subpage, subpage_dict)
from maalimbus.vision import Text  # noqa: E402

SHOP_FRAME = ROOT / 'evidence/runtime/window-20261012-024300/frame-0173.json'
IDENTITY_CATALOG = ROOT / 'assets/resource/base/identity-catalog.json'

#: The live shelf's gift column, in the order the reader sorts it.
LIVE_GIFTS = ['Curriculum Vitae', 'Polarization', 'Prejudice', 'Scalpel',
              'Uncapped Defibrilator']
LIVE_PRICE = 77
LIVE_PRICE_CONFIDENCE = .834838
LIVE_ANNOUNCEMENT = 'Replace Heathciffs Skill'
LIVE_ANNOUNCEMENT_CONFIDENCE = .979651

#: The identity the synthetic subpage belongs to: Yi Sang's first catalogue row.
SYNTHETIC_IDENTITY = 10101
SYNTHETIC_SKILLS = [1010101, 1010102, 1010103, 1010104]
SYNTHETIC_NAMES = {1010101: 'Sunset Blade', 1010102: 'Endless Suffering',
                   1010103: 'Rip Space', 1010104: 'Silent Chant'}


def live_page():
    """The retained live shelf as the reader sees it: its OCR tokens, untouched."""
    if not SHOP_FRAME.exists():
        pytest.skip('retained live shop evidence is not present')
    record = json.loads(SHOP_FRAME.read_text(encoding='utf-8'))
    records = [Text(token['text'], tuple(token['box']), token['score'])
               for token in record['ocr']]
    return record, records


def page(*texts):
    """A page drawn from ``(text, box, score)`` triples."""
    return [Text(text, box, score) for text, box, score in texts]


def subpage_page(*, price=240, skill=(1010102, 'Endless Suffering', (700, 420, 220, 30), .97),
                 slot=(1010101, 'Sunset Blade', (700, 320, 220, 30), .96),
                 confirm='Confirm', cancel='X Cancel', extra=()):
    """A synthetic replacement subpage.

    The announced skill is ``skill`` (id and printed name); the displaced skill is
    ``slot``.  The regions are the shop's own dialog regions, which is exactly why
    this is only a protocol fixture: nobody has measured where a replacement subpage
    really draws, and the reader must therefore still refuse to authorize anything.
    """
    rows = [('Shop Skill Replacement', (700, 240, 300, 30), .99)]
    if skill is not None:
        rows.append((skill[1], skill[2], skill[3]))
    if slot is not None:
        rows.append((slot[1], slot[2], slot[3]))
    if price is not None:
        rows.append((str(price), (700, 700, 60, 30), .95))
    if confirm is not None:
        rows.append((confirm, (1040, 760, 120, 34), .99))
    if cancel is not None:
        rows.append((cancel, (860, 760, 120, 34), .99))
    rows.extend(extra)
    return page(*rows)


def read_announced(page_rows, **overrides):
    """``read_subpage`` for the synthetic announced skill, with the fixture's names."""
    args = dict(identity_id=SYNTHETIC_IDENTITY, skills=SYNTHETIC_SKILLS,
                skill_id=1010102, name='Endless Suffering',
                skill_names={1010101: 'Sunset Blade', 1010103: 'Rip Space',
                             1010104: 'Silent Chant'},
                replaces=[1010101])
    args.update(overrides)
    return read_subpage(page_rows, (1920, 1080), **args)


def test_the_live_shelf_returns_its_own_gift_column_and_its_own_price():
    record, records = live_page()
    shelf = read_shelf(records, tuple(record['size']), source=SHOP_FRAME)

    assert shelf.gift_names == tuple(sorted(LIVE_GIFTS))
    assert len(shelf.skill_offers) == 1
    offer = shelf.skill_offers[0]
    assert offer.announced == LIVE_ANNOUNCEMENT
    assert offer.announced_confidence == pytest.approx(LIVE_ANNOUNCEMENT_CONFIDENCE)
    assert offer.price == LIVE_PRICE
    assert offer.price_confidence == pytest.approx(LIVE_PRICE_CONFIDENCE)
    assert shelf.authorized is False and shelf.would_spend is False


def test_the_live_shelf_reports_the_low_price_confidence_and_keeps_the_threshold():
    record, records = live_page()
    shelf = read_shelf(records, tuple(record['size']), source=SHOP_FRAME)

    assert shelf.threshold == DEFAULT_THRESHOLD
    assert [row['field'] for row in shelf.low_confidence] == ['price']
    live = [row for row in shelf.low_confidence if row['field'] == 'price'][0]
    assert live['text'] == ' 77'
    assert live['confidence'] == pytest.approx(LIVE_PRICE_CONFIDENCE)
    assert live['confidence'] < DEFAULT_THRESHOLD
    assert 'price_confidence_below_threshold' in shelf.skill_offers[0].reasons


def test_the_live_shelf_refuses_to_repair_the_mangled_sinner_name():
    record, records = live_page()
    shelf = read_shelf(records, tuple(record['size']), source=SHOP_FRAME)
    offer = shelf.skill_offers[0]

    # 'Heathciffs' is one letter away from a real sinner and stays unreadable anyway.
    assert offer.sinner is None
    assert offer.sinner_known is False
    assert 'sinner_text_not_a_canonical_name' in offer.reasons
    assert shelf.unreadable[0]['text'] == LIVE_ANNOUNCEMENT
    assert shelf.unreadable[0]['confidence'] == pytest.approx(LIVE_ANNOUNCEMENT_CONFIDENCE)
    assert 'Heathcliff' in shelf.unreadable[0]['expected']


def test_a_readable_announcement_binds_a_canonical_sinner_with_or_without_the_possessive():
    rows = page(("Replace Heathcliff's Skill", (960, 500, 220, 20), .98),
                ('Replace Ryoshu Skill', (960, 500, 220, 20), .98),
                ('Replace Hong Lu Skill', (960, 500, 220, 20), .98))
    named = read_shelf(rows, (1920, 1080))

    assert [offer.sinner for offer in named.skill_offers] == ['Heathcliff', 'Ryoshu', 'Hong Lu']
    assert all(offer.sinner_known for offer in named.skill_offers)
    assert named.unreadable == ()


def test_the_frame_reader_carries_the_retained_png_hash_and_the_scene():
    reading = read_frame(SHOP_FRAME)

    assert reading['scene'] == 'SHOP'
    assert reading['image_sha256_source'] == 'retained_png'
    assert reading['image_sha256'] == reading['image_sha256_declared']
    assert reading['skill_offers'][0]['price'] == LIVE_PRICE
    assert reading['authorized'] is False and reading['would_spend'] is False
    assert reading['input_sent'] is False and reading['game_controller'] is False


def test_a_frame_whose_png_hash_disagrees_with_its_record_is_refused(tmp_path):
    record, _ = live_page()
    tampered = copy.deepcopy(record)
    tampered['image_sha256'] = '0' * 64
    path = tmp_path / 'frame-0173.json'
    path.write_text(json.dumps(tampered), encoding='utf-8')
    (tmp_path / 'frame-0173.png').write_bytes(b'not the retained pixels')

    with pytest.raises(ValueError, match='hash differs'):
        read_frame(path)


def test_a_frame_missing_a_required_field_is_refused(tmp_path):
    record, _ = live_page()
    for field in FRAME_FIELDS:
        broken = copy.deepcopy(record)
        broken.pop(field)
        path = tmp_path / ('broken-' + field + '.json')
        path.write_text(json.dumps(broken), encoding='utf-8')
        with pytest.raises(ValueError, match='Invalid retained'):
            read_frame(path)


def test_an_announcement_with_no_printed_badge_reports_a_missing_price_not_a_zero():
    rows = page(("Replace Heathcliff's Skill", (960, 500, 220, 20), .98))
    shelf = read_shelf(rows, (1920, 1080))
    offer = shelf.skill_offers[0]

    assert offer.price is None and offer.price_box is None
    assert offer.reasons == ('price_pair_missing', 'price_unknown')
    assert shelf.missing == ({'field': 'price', 'announced': "Replace Heathcliff's Skill"},)


def test_two_badges_in_one_column_are_ambiguous_and_the_first_is_not_preferred():
    rows = page(("Replace Heathcliff's Skill", (960, 500, 220, 20), .98),
                ('147', (960, 460, 60, 32), .97),
                ('152', (960, 470, 60, 32), .96))
    shelf = read_shelf(rows, (1920, 1080))
    offer = shelf.skill_offers[0]

    assert 'price_pair_ambiguous' in offer.reasons
    # Both badges are accepted as candidates and the row is reported; the reading
    # keeps the geometry's own first candidate (nearest in column, then lowest) and
    # never prefers the smaller number, so a caller must not buy on an ambiguous row.
    assert offer.price == 152
    assert shelf.ambiguous[0]['name'] == "Replace Heathcliff's Skill"
    assert [row['price'] for row in shelf.ambiguous[0]['candidates']] == [152, 147]
    assert shelf.missing == ()


def test_a_badge_from_another_column_is_not_paired():
    rows = page(("Replace Heathcliff's Skill", (960, 500, 220, 20), .98),
                ('147', (1200, 460, 60, 32), .97))
    shelf = read_shelf(rows, (1920, 1080))

    assert shelf.skill_offers[0].price is None
    assert shelf.missing[0]['field'] == 'price'


def test_a_badge_below_the_threshold_is_reported_as_low_confidence():
    rows = page(("Replace Heathcliff's Skill", (960, 500, 220, 20), .98),
                ('147', (960, 460, 60, 32), .61))
    shelf = read_shelf(rows, (1920, 1080))

    assert shelf.skill_offers[0].price == 147
    assert shelf.skill_offers[0].price_confidence == pytest.approx(.61)
    assert shelf.low_confidence == ({'field': 'price', 'text': '147', 'confidence': pytest.approx(.61)},)


def test_a_low_confidence_announcement_is_reported_without_hiding_the_offer():
    rows = page(("Replace Heathcliff's Skill", (960, 500, 220, 20), .72),
                ('147', (960, 460, 60, 32), .97))
    shelf = read_shelf(rows, (1920, 1080))
    offer = shelf.skill_offers[0]

    assert offer.announced_confidence == pytest.approx(.72)
    assert 'announcement_confidence_below_threshold' in offer.reasons
    assert shelf.low_confidence[0]['field'] == 'announcement'


def test_a_duplicated_announcement_is_two_offers_and_never_merged():
    rows = page(("Replace Heathcliff's Skill", (960, 500, 220, 20), .98),
                ("Replace Heathcliff's Skill", (960, 700, 220, 20), .98),
                ('147', (960, 460, 60, 32), .97),
                ('152', (960, 660, 60, 32), .97))
    shelf = read_shelf(rows, (1920, 1080))

    assert len(shelf.skill_offers) == 2
    assert [offer.price for offer in shelf.skill_offers] == [147, 152]
    assert all(offer.sinner == 'Heathcliff' for offer in shelf.skill_offers)


def test_rows_outside_the_shelf_band_are_not_offers():
    rows = page(("Replace Heathcliff's Skill", (960, 120, 220, 20), .98),
                ('147', (960, 80, 60, 32), .97))
    shelf = read_shelf(rows, (1920, 1080))

    assert shelf.skill_offers == () and shelf.missing == ()
    assert shelf.gift_names == () and shelf.unreadable == ()


def test_one_or_two_character_fragments_are_ocr_debris_and_not_gifts():
    rows = page(('C', (900, 300, 20, 20), .99),
                ('Curriculum Vitae', (900, 400, 220, 24), .98))
    shelf = read_shelf(rows, (1920, 1080))

    assert shelf.gift_names == ('Curriculum Vitae',)


def test_a_threshold_outside_the_unit_interval_is_refused():
    for bad in (0, 1.5, -0.2, 'high', None):
        with pytest.raises(ValueError, match='Invalid OCR threshold'):
            read_shelf((), (1920, 1080), threshold=bad)


def test_a_size_that_is_not_the_reference_layout_or_an_integer_scale_is_refused():
    for bad in ((1920, 1079), (1000, 500), (1920, 1080, 1), (1920, 0)):
        with pytest.raises(ValueError):
            read_shelf((), bad)
    # A legitimate rescale still reads: the regions are scaled by the width ratio.
    assert read_shelf((), (1000, 562)).size == (1000, 562)


def test_the_catalogue_binds_every_skill_id_to_exactly_one_identity():
    catalog = load_identity_skills(IDENTITY_CATALOG)

    assert len(catalog) == 128
    assert catalog[SYNTHETIC_IDENTITY] == set(SYNTHETIC_SKILLS)
    assert all(isinstance(identity, int) for identity in catalog)
    assert all(skills and all(type(skill) is int for skill in skills)
               for skills in catalog.values())


def test_the_subpage_protocol_declares_itself_synthetic_before_any_page_exists():
    assert SUBPAGE_PROTOCOL['live_subpage_evidence'] is False
    assert SUBPAGE_PROTOCOL['layout_known'] is False
    assert 'int' in SUBPAGE_PROTOCOL['required'][0]
    assert any('inherit' in line or 'invent' in line for line in SUBPAGE_PROTOCOL['never'])


def test_a_complete_synthetic_subpage_is_read_but_never_authorized():
    reading = read_announced(subpage_page())

    assert reading.complete is True
    assert reading.skill_id == 1010102 and reading.skill_name == 'Endless Suffering'
    assert reading.replaces == 1010101
    assert reading.price == 240
    assert reading.confirm is not None and reading.cancel is not None
    assert reading.authorized is False and reading.would_spend is False
    assert reading.live_subpage_evidence is False


def test_unannounced_skill_ids_are_not_searched_for_at_all():
    # 'Rip Space' and 'Silent Chant' belong to the identity but were never announced;
    # they are not on the fixture page and must not be reported as missing fields.
    reading = read_announced(subpage_page())

    assert reading.complete is True
    assert reading.missing == ()
    assert reading.refused == ()


def test_an_unannounced_skill_id_that_the_catalogue_does_not_bind_is_refused():
    reading = read_announced(subpage_page(), skill_id=9000001)

    assert reading.complete is False
    assert 'skill_not_bound_to_identity' in reading.refused
    assert reading.skill_id is None


def test_the_synthetic_subpage_keeps_its_synthetic_flag_through_the_dict():
    reading = read_announced(subpage_page())
    data = subpage_dict(reading, synthetic=True)

    assert data['synthetic'] is True
    assert data['live_subpage_evidence'] is False
    assert data['authorized'] is False and data['would_spend'] is False
    assert data['version'] == SUBPAGE_VERSION
    assert json.loads(json.dumps(data)) == data
    # Asking for synthetic cannot clear it either.
    assert subpage_dict(reading, synthetic=False)['synthetic'] is False


def test_a_subpage_missing_its_price_reports_the_field_and_stays_incomplete():
    reading = read_announced(subpage_page(price=None))

    assert reading.complete is False and reading.price is None
    assert 'price' in reading.missing
    assert reading.authorized is False


def test_a_subpage_that_does_not_print_the_announced_name_reports_it_missing():
    reading = read_announced(subpage_page(skill=None))

    assert reading.complete is False
    assert reading.skill_id is None and reading.skill_name is None
    assert 'skill_name' in reading.missing


def test_a_subpage_with_two_printed_prices_is_ambiguous():
    reading = read_announced(subpage_page(extra=(('310', (700, 760, 60, 30), .96),)))

    assert reading.complete is False
    assert 'price_ambiguous' in reading.refused


def test_a_skill_id_the_catalogue_does_not_bind_is_refused():
    reading = read_announced(subpage_page(), skill_id=9000001)

    assert reading.complete is False
    assert 'skill_not_bound_to_identity' in reading.refused


def test_a_replacement_slot_that_is_the_new_skill_is_refused():
    # The only printed name on the page is the announced skill's own, so the displaced
    # slot resolves to the very skill being installed; that is refused, not displaced.
    reading = read_announced(subpage_page(slot=None), replaces=[1010102],
                             skill_names={1010102: 'Endless Suffering'})

    assert reading.complete is False
    assert reading.replaces is None
    assert 'replacement_slot_is_the_new_skill' in reading.refused


def test_an_unresolved_replacement_slot_is_a_missing_field_not_a_licence():
    reading = read_announced(subpage_page(slot=None))

    assert reading.complete is False
    assert reading.replaces is None
    assert 'replacement_slot' in reading.missing


def test_a_subpage_without_a_confirm_cancel_pair_is_unproven():
    reading = read_announced(subpage_page(cancel=None))

    assert reading.complete is False
    assert 'confirm_cancel_pair_unproven' in reading.refused
    assert reading.confirm is None and reading.cancel is None


def test_a_caller_supplied_price_still_has_to_be_printed_on_the_page():
    reading = read_announced(subpage_page(price=None), price=240)

    assert reading.complete is False
    assert reading.price == 240
    assert 'price' in reading.missing


def test_a_malformed_subpage_question_is_refused_rather_than_guessed():
    with pytest.raises(ValueError, match='Identity id'):
        read_announced(subpage_page(), identity_id='10101')
    with pytest.raises(ValueError, match='skills'):
        read_announced(subpage_page(), skills=())
    with pytest.raises(ValueError, match='non-negative integer'):
        read_announced(subpage_page(), price=-1)
    with pytest.raises(ValueError, match='printed names'):
        read_announced(subpage_page(), skill_names={'1010102': 'Endless Suffering'})
    with pytest.raises(ValueError, match='announced skill id'):
        read_announced(subpage_page(), skill_id='1010102')
    with pytest.raises(ValueError, match='announced skill name'):
        read_announced(subpage_page(), name='')
