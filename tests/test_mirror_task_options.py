import pytest
from maalimbus.mirror_task_options import collect


def nodes(keyword='saved', search='saved', steps='saved',battle='saved'):
    data={'MirrorInitialKeyword': {'attach': {'keyword': keyword}},
          'MirrorGiftSearch': {'attach': {'mode': search}},
          'MirrorRunBounds': {'attach': {'steps': steps}},
          'MirrorBattleAssignment':{'attach':{'mode':battle}}}
    return data.__getitem__


def test_saved_options_preserve_existing_launch_and_loop_defaults():
    assert collect(nodes()) == {}


def test_distinct_nodes_keep_all_three_runtime_preferences():
    assert collect(nodes('poise', 'refuse', 120)) == dict(
        gift_keyword='poise', gift_search='refuse', steps=120)


@pytest.mark.parametrize('args', [('unknown','saved','saved'),
    ('saved','select','saved'), ('saved','saved',True),
    ('saved','saved',0), ('saved','saved',2001)])
def test_invalid_or_paid_search_options_stop(args):
    with pytest.raises(ValueError):
        collect(nodes(*args))


@pytest.mark.parametrize('mode',['win_rate','damage','observe'])
def test_battle_mode_survives_other_independent_options(mode):
    assert collect(nodes('poise','refuse',120,mode))==dict(
        gift_keyword='poise',gift_search='refuse',steps=120,battle_assignment=mode)


def test_unknown_battle_mode_is_rejected():
    with pytest.raises(ValueError):collect(nodes(battle='unknown'))
