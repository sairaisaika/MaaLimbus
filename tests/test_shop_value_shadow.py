"""A trained candidate cannot silently become a live purchasing controller."""
from types import SimpleNamespace
from maalimbus.shop_value_shadow import rank_preview


def test_missing_value_model_preserves_rule_order_and_input_limits(tmp_path):
    offers=[SimpleNamespace(name='B',price=10),SimpleNamespace(name='A',price=20)]
    result,trace=rank_preview(offers,dict(coins=100,reserve_coins=50),tmp_path)
    assert result==offers and not trace['neural_value_shadow_applied']
    assert not trace['buy_learning_applied']


def test_malformed_or_unverified_candidate_falls_back_without_stopping_pipeline(tmp_path):
    offers=[SimpleNamespace(name='A',price=20)]
    (tmp_path/'weights.json').write_text('[broken',encoding='utf-8')
    (tmp_path/'modelcard.json').write_text('{}',encoding='utf-8')
    result,trace=rank_preview(offers,{},tmp_path)
    assert result==offers and trace['reason']=='invalid_value_candidate_rule_fallback'
    assert not trace['buy_learning_applied']
