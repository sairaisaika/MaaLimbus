"""The geometry anchor says where it came from (D279).

Read: this frame found the party.  Carried: this frame could not, so the last point the
same floor produced was used (D266).  None: nothing to anchor on, and the run refuses
rather than guesses.  The three words are derived from the record `candidates_of` writes,
so a measurement can never be taken on an anchor whose provenance is unknown.
"""
from maalimbus import runner


def test_a_frame_that_read_the_party_says_read():
    assert runner.party_anchor_source({'map_party': [10, 20],
                                       'map_party_source': 'read'}) == 'read'


def test_a_carried_party_says_carried():
    assert runner.party_anchor_source({'map_party': [10, 20],
                                       'map_party_from_cache': True,
                                       'map_party_source': 'carried'}) == 'carried'


def test_no_anchor_says_none_and_not_read():
    assert runner.party_anchor_source({'map_party': None,
                                       'map_candidates_refused': {'party': None}}) == 'none'


def test_the_field_is_derived_when_an_older_record_has_no_source():
    assert runner.party_anchor_source({'map_party_from_cache': True}) == 'carried'
    assert runner.party_anchor_source({'map_party': [1, 2]}) == 'read'
    assert runner.party_anchor_source({}) == 'none'


def test_the_three_words_are_the_whole_vocabulary():
    for record in ({}, {'map_party': None}, {'map_party': [0, 0]},
                   {'map_party_from_cache': True}, {'map_candidates_refused': {}}):
        assert runner.party_anchor_source(record) in ('read', 'carried', 'none')
