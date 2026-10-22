

def _header(text, box):
    from maalimbus.vision import Text
    return Text(text=text, box=box, score=.99)


def test_a_compound_keyword_takes_the_first_column_the_page_offers():
    """A charge+tremor team must not stall just because its keyword names two systems."""
    from maalimbus.initial_gifts import group_target
    size = (1920, 1080)
    records = [_header('Bleed', (300, 240, 64, 32)),
               _header('Tremor', (700, 240, 90, 32))]
    assert group_target(records, size, 'charge+tremor') is not None, (
        'the page has no Charge column, so Tremor is the team\'s column here')
    assert group_target(records, size, 'charge') is None
    assert group_target(records, size, 'tremor') == group_target(records, size, 'charge+tremor')
