"""通用购买确认框：没有商品名与价格时，用它自己的 Purchase 按钮回答。"""
from __future__ import annotations

import pathlib

from maalimbus.shop_vision import native_purchase_dialog
from maalimbus.vision import Text

REPO = pathlib.Path(__file__).resolve().parents[1]


def _rows():
    return [
        Text('Purchase E.G.O Gifts', (674, 236, 292, 34), 0.999),
        Text('X Cancel', (710, 702, 156, 42), 0.912),
        Text('Purchase', (1094, 706, 126, 34), 0.999),
        Text('Skill, inflict 2 Tremor Potency on target.', (804, 524, 506, 37), 0.99),
    ]


def test_the_generic_question_still_has_its_own_answer():
    dialog = native_purchase_dialog(_rows(), (1920, 1080))
    assert dialog['purchase'].text == 'Purchase'
    assert dialog['purchase'].box == (1094, 706, 126, 34)


def test_the_generic_question_prints_no_price():
    rows = _rows()
    prices = [row.text for row in rows if row.text.strip().isdigit() and len(row.text.strip()) >= 2]
    assert prices == [], 'a generic question prints no price of its own'


def test_the_runner_falls_back_to_the_dialog_control():
    source = (REPO / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    assert "if shop['confirm'] is None:" in source
    assert "shop['confirm']=dialog['purchase']" in source
    assert "shop_generic_dialog_confirm" in source


def test_a_question_without_a_purchase_control_is_not_a_dialog():
    rows = [row for row in _rows() if row.text != 'Purchase']
    assert native_purchase_dialog(rows, (1920, 1080)) is None


def test_the_runner_guards_the_missing_dialog():
    source = (REPO / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')
    assert "if dialog and dialog.get('purchase') is not None:" in source
