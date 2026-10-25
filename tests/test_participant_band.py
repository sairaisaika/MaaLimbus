"""The participant counter is read wherever the panel puts it (2026-10-25).

The operator's screenshot of the pre-battle page shows `Total Participants 12/12` in the
right-hand column while this function's own band read nothing, and the run stopped on
`deployment_transaction_or_counter_missing` after two cheap re-reads.  The labelled banner
moved with the layout, so the fallback band reads the right column and the card rows stay
outside it: a bare `N/M` printed on a card is not this page's counter.
"""

from maalimbus.team_vision import RIGHT_COLUMN_ROI, participants


def _row(text, box, score=.99):
    return type('Row', (), {'text': text, 'box': box, 'score': score})()


def test_the_labelled_banner_in_the_right_column_is_the_counter():
    size = (1920, 1080)
    records = [_row('12 / 12', [1600, 640, 120, 40])]
    assert participants(records, size) == (12, 12)


def test_a_counter_inside_a_card_is_not_the_page_counter():
    size = (1920, 1080)
    records = [_row('3 / 4', [500, 600, 60, 30])]
    assert participants(records, size) is None


def test_the_band_is_the_right_column_of_the_panel():
    assert RIGHT_COLUMN_ROI[0] >= .75 and RIGHT_COLUMN_ROI[2] <= 1.0
    assert RIGHT_COLUMN_ROI[1] < .6 < RIGHT_COLUMN_ROI[3]
