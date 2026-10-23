from maalimbus.pages import RECOVERY_BY_KIND, REFUSAL_KINDS, STOP_KINDS, kind_of, recovery_for


def test_a_runner_stop_reason_has_a_kind():
    # The live case: evidence/runtime/packaged-mirror-20261023-084610
    assert kind_of(stopped_reason='page_unreadable_after_waiting') == 'unreadable_text'
    assert kind_of(stopped_reason='unexpected_successor') == 'bad_saved_state'


def test_every_stop_kind_is_a_known_kind():
    assert set(STOP_KINDS.values()) <= set(REFUSAL_KINDS)


def test_a_stop_reason_never_shadows_a_refusal_name():
    from maalimbus.pages import REFUSALS
    assert not (set(STOP_KINDS) & set(REFUSALS))


def test_the_three_names_are_tried_in_order():
    assert kind_of(reason='no_candidate_node_observed', stopped_reason='unexpected_successor') == 'no_candidate'
    assert kind_of() is None


def test_the_narrowing_still_reads_one_source():
    # Recording may consult three names; the action table must stay derivable from the kind alone.
    for kind in REFUSAL_KINDS:
        assert recovery_for(kind) == RECOVERY_BY_KIND[kind]
