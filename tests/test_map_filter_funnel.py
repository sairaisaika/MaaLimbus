"""过滤漏斗：每一层记录的是它自己的输入，不是同一个值记两次（D410）。"""
from __future__ import annotations

import inspect

from maalimbus import runner


def test_every_stage_of_the_funnel_is_named():
    source = inspect.getsource(runner)
    for key in ("'raw'", "'after_decoration'", "'before_pick'"):
        assert key in source, key


def test_no_stage_records_the_same_length_twice():
    """同一个值记两次就是装饰，不是仪表。"""
    source = inspect.getsource(runner)
    rights = [line.split('=', 1)[1].strip()
              for line in source.splitlines()
              if "record['map_filter_funnel']" in line and '[' in line and '=' in line
              and 'if' not in line]
    assert len(rights) >= 3, rights
    assert len(set(rights)) == len(rights), rights
