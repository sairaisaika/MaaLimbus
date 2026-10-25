import pathlib
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from maalimbus import runner  # noqa: E402


def _loop(state):
    loop = runner.MirrorRunner.__new__(runner.MirrorRunner)
    loop.state = state
    loop.last_event = None
    loop.artifacts = {"steps": [], "flow_steps": [], "clicks_sent": 0, "verified_clear": False, "flow": None}
    loop.journal = None
    loop.log = None
    return loop


def test_a_verdict_that_is_not_a_refusal_breaks_the_streak():
    loop = _loop({"map_refused_streak": 2})
    loop._map_verdict(outcome="unjudged", target=[1, 2, 3, 4])
    assert loop.state["map_refused_streak"] == 0


def test_a_superseded_verdict_breaks_the_streak_too():
    loop = _loop({"map_refused_streak": 2})
    loop._map_verdict(outcome="superseded", target=[1, 2, 3, 4])
    assert loop.state["map_refused_streak"] == 0


def test_a_refusal_is_not_reset_by_its_own_verdict():
    loop = _loop({"map_refused_streak": 2})
    loop._map_verdict(outcome="rejected", target=[1, 2, 3, 4])
    assert loop.state["map_refused_streak"] == 2


def test_the_rule_is_the_documented_one_consecutive_refusals():
    loop = _loop({})
    loop._map_verdict(outcome="rejected", target=[1, 2, 3, 4])
    runner.map_refusal_streak(loop.state, lambda event, **fields: None)
    assert loop.state["map_refused_streak"] == 1
    loop._map_verdict(outcome="unjudged", target=[1, 2, 3, 4])
    runner.map_refusal_streak(loop.state, lambda event, **fields: None)
    assert loop.state["map_refused_streak"] == 1, "a non-refusal starts the count again"
