import pytest
from maalimbus.mirror_task_options import collect


def nodes(keyword='saved', search='saved', steps='saved', battle='saved', runs='saved'):
    data={'MirrorInitialKeyword': {'attach': {'keyword': keyword}},
          'MirrorGiftSearch': {'attach': {'mode': search}},
          'MirrorRunBounds': {'attach': {'steps': steps}},
          'MirrorRunCount': {'attach': {'run_count': runs}},
          'MirrorBattleAssignment':{'attach':{'mode':battle}}}
    return data.__getitem__


def test_saved_options_preserve_existing_launch_and_loop_defaults():
    assert collect(nodes()) == {}


def test_distinct_nodes_keep_all_three_runtime_preferences():
    assert collect(nodes('poise', 'refuse', 120)) == dict(
        gift_keyword='poise', gift_search='refuse', steps=120)


def test_the_named_run_count_is_kept_apart_from_the_step_bound():
    """Two independent settings: the step bound is one window, the count is whole runs."""
    assert collect(nodes(steps=120, runs=3)) == dict(steps=120, run_count=3)


def test_no_named_run_count_is_not_a_zero_count():
    """'saved' leaves the launch's own setting alone; the window is not told 'stop at 0'."""
    assert collect(nodes(runs='saved')) == {}


def test_a_run_count_without_a_step_bound_still_travels():
    assert collect(nodes(runs=2)) == dict(run_count=2)


@pytest.mark.parametrize('args', [('unknown','saved','saved'),
    ('saved','select','saved'), ('saved','saved',True),
    ('saved','saved',0), ('saved','saved',2001)])
def test_invalid_or_paid_search_options_stop(args):
    with pytest.raises(ValueError):
        collect(nodes(*args))


@pytest.mark.parametrize('runs', [True, False, -1, 51, 'many', 1.0])
def test_invalid_run_counts_stop(runs):
    with pytest.raises(ValueError):
        collect(nodes(runs=runs))


@pytest.mark.parametrize('mode',['win_rate','damage','observe'])
def test_battle_mode_survives_other_independent_options(mode):
    assert collect(nodes('poise','refuse',120,mode))==dict(
        gift_keyword='poise',gift_search='refuse',steps=120,battle_assignment=mode)


def test_unknown_battle_mode_is_rejected():
    with pytest.raises(ValueError):collect(nodes(battle='unknown'))
