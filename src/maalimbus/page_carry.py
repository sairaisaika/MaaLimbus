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
