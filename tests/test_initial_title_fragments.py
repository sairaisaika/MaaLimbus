from maalimbus.initial_gifts import row_target
from maalimbus.vision import Text


def test_same_row_adjacent_title_fragments_retain_full_name():
    records=[Text(' Lamp',(1450,500,78,20),.901225),
             Text('Fluorescent',(1302,496,158,26),.999074)]
    assert row_target(records,(1920,1080),2)[1]=='Fluorescent Lamp'


def test_second_line_and_low_confidence_fragment_do_not_form_full_title():
    assert row_target([Text('Fluorescent',(1302,496,158,12),.99),
                       Text('Lamp',(1450,514,78,12),.99)],(1920,1080),2) is None
    result=row_target([Text('Fluorescent',(1302,496,158,26),.99),
                       Text('Lamp',(1450,500,78,20),.5)],(1920,1080),2)
    assert result[1]!='Fluorescent Lamp'
