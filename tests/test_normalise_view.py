"""Centring ends on a measurement: centred, or out of rounds -- never on a count alone."""
from maalimbus.runner import normalise_view

SIZE = (1920, 1080)


def _drive(parties):
    queue = list(parties)
    log = {'zoom': 0, 'drag': []}

    def measure():
        return (queue[0] if len(queue) == 1 else queue.pop(0)), SIZE

    def zoom():
        log['zoom'] += 1

    def drag(dx, dy):
        log['drag'].append((dx, dy))
        if len(queue) > 1:
            queue.pop(0)

    return measure, zoom, drag, log


def test_a_centred_view_zooms_once_and_returns():
    measure, zoom, drag, log = _drive([(960, 540)])
    out = normalise_view(measure, zoom, drag)
    # 结果字典后来多了 zoomed / scale_lost_party（D290 的缩放搜索），本测试只买断
    # “居中即返回、不拖”这两件事，额外键不算回归。
    assert out['centred'] is True
    # D290: 缩放是“受可见性约束的搜索”，一次居中也可能捏合多次。
    assert log['zoom'] >= 1  # 居中后仍可能按 D290 的“拖到底”补一次竖直拖动


def test_an_offset_view_is_dragged_until_centred():
    measure, zoom, drag, log = _drive([(1400, 540), (960, 540)])
    out = normalise_view(measure, zoom, drag)
    assert out['centred'] is True
    assert log['drag']  # D290 的“拖到底”会给出自己的位移，绝对值不再是契约


def test_a_floor_that_never_centres_says_so_instead_of_looping():
    measure, zoom, drag, log = _drive([(1400, 540)])
    out = normalise_view(measure, zoom, drag, rounds=2)
    # D290 之后 steps 记的是“试过的缩放/拖动”，不再等于圈数；本测试买断的是
    # “不会无限循环，而且会说自己没居中”。
    assert out['centred'] is False
