from maalimbus.decision_log import lines
from maalimbus.event_log import report

def test_rule_components_and_direction_visible_in_console_and_finished_log():
    row=dict(title='Example',score=20,score_components=dict(trial=60,synergy=-40,already_owned=0,visible_benefit=0))
    text=lines('floor_gift_ranking',dict(ranking=[row]))
    assert '越低' in text[0] and '模型未参与' in text[0]
    assert 'trial=+60' in text[1] and 'synergy=-40' in text[1] and '最终分=20' in text[1]
    assert text[1] in report(dict(decisions=[dict(lines=text)]))

def test_shadow_prediction_does_not_claim_to_choose_purchase():
    text=lines('shop_decision_ranking',dict(currency=2000,reserve=300,refresh_limit=2,reason='gift_plan',
        ranking=[dict(name='Black Card',price=150,manual_weight=95,score=7,status='可购买',chosen=True)],
        learning=dict(neural_value_shadow_applied=True)))
    assert '手动权重=95' in text[1] and '队列分=7' in text[1] and '选择购买' in text[1]
    assert '不改变购买顺序' in text[-1]

def test_theme_weight_is_the_actual_score_not_neural():
    row=dict(name='Pack',weight=40,reason='team_weight')
    text=lines('theme_pack_recommendation',dict(chosen=row,ranking=[row]))
    assert '最终分=40' in text[1] and '选择' in text[1]
