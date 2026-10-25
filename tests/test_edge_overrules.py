"""A drawn edge outranks the distance rule, and only when the rule empties the list (D317).

`-153919` measured the disagreement on three MAP frames: 12 candidates, `map_edge_only
{kept: 1, dropped: 11}`, then `adjacency {before: 1, after: 0}` -- the one box the page
pointed at was the one box `adjacent_to` refused, so the loop clicked nothing while the
game was saying which step it would take.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'src' / 'maalimbus' / 'runner.py').read_text(encoding='utf-8')


def _branch():
    start = SOURCE.index('if edge is not None and picked and not near:')
    return SOURCE[start:start + 900]


def test_the_page_wins_when_the_rule_empties_the_list():
    body = _branch()
    assert 'near = picked' in body
    assert "record['map_edge_overrules_adjacency']" in body


def test_the_branch_sits_between_the_rule_and_the_ordering():
    rule = SOURCE.index('near = adjacent_to(party, picked)')
    branch = SOURCE.index('if edge is not None and picked and not near:')
    ordering = SOURCE.index('ordered = order_candidates(near, kinds)')
    assert rule < branch < ordering, 'an override applied after the sort changes nothing'


def test_the_override_records_the_edge_it_followed():
    body = _branch()
    assert "'edge'" in body and "'kept'" in body


def test_no_edge_still_means_no_candidate():
    # The else path is the old behaviour: `near` stays whatever `adjacent_to` answered, and
    # `candidates_of` answers empty rather than inventing a box.
    branch = SOURCE.index('if edge is not None and picked and not near:')
    after = SOURCE[branch:SOURCE.index('ordered = order_candidates(near, kinds)')]
    assert 'picked = rest' in SOURCE and 'near = []' not in after
