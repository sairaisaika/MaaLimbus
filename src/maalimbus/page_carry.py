"""同一张图不会既是地图又不是地图。

实跑 `evidence/runtime/packaged-mirror-20261031-143700` 的页面序列是
`MAP -> UNKNOWN -> MAP -> UNKNOWN -> MAP`：同一张地图帧隔一帧就认不出来一次，
一来一回就是每层几十分钟。这一层只回答一个问题——这一帧能不能沿用上一帧的页面名。
"""
from __future__ import annotations

CARRY_FROM = ('MAP',)


def carry_page(page, last_named, frame_sha, last_sha, *, carry_from=CARRY_FROM):
    """The page this frame should be read as, when the picture did not change.

    A frame whose bytes are identical to the one that was just read as a map is that same
    map frame: recognition is allowed to answer UNKNOWN, but the picture is not allowed to
    be two different pages at once.
    """
    if page != 'UNKNOWN':
        return page
    if last_named not in carry_from:
        return page
    if not frame_sha or not last_sha or frame_sha != last_sha:
        return page
    return last_named


def unknown_needs_reread(page, *, observe_only=False):
    """读不出名字时要不要立刻再读一次（D360）。

    实测 `-150529`：页面在 MAP 与 UNKNOWN 之间来回跳，而每一次都是一次独立的观察，
    所以“多读一次”比“等 6 s 再读”便宜得多。只读模式（`--observe-only`）不许再发观察。
    """
    return page == 'UNKNOWN' and not observe_only


MAP_STRUCTURE_FLOOR = 4
NODE_SIDE = (150.0, 220.0)


def map_by_structure(boxes, *, floor=MAP_STRUCTURE_FLOOR, side=NODE_SIDE):
    """没有文字时，还有结构：一张地图页面上同时躺着好几个六边形节点框。

    实测（`-150939` 及其前两轮）：MAP 帧的节点框 6–14 个，UNKNOWN 帧 7–8 个，
    而界面页（战斗/商店/结算）0–1 个。判据取 4：远低于地图的最小值，又远高于界面页，
    而且只看「边长 150–220 的框有几个」，不看颜色、不看黄圈、不看文字。
    """
    count = 0
    for box in boxes or ():
        try:
            side_length = float(box[2])
        except (TypeError, IndexError, ValueError):
            continue
        if side[0] <= side_length <= side[1]:
            count += 1
    return count >= floor
