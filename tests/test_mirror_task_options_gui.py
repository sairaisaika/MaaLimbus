from maalimbus import mirror_task_options


def test_a_single_team_choice_becomes_a_slot_override():
    patch = mirror_task_options.gui_override(
        {'mirror_team_mode': 'single', 'mirror_single_team': 2})
    assert patch == {'MirrorTaskSingleTeam': {'attach': {'slot': 2}}}


def test_a_roster_mode_does_not_invent_a_single_slot():
    patch = mirror_task_options.gui_override(
        {'mirror_team_mode': 'roster', 'mirror_single_team': 2})
    assert patch == {}


def test_saved_keyword_stays_saved_and_a_named_one_overrides():
    assert mirror_task_options.gui_override(
        {'mirror_team_mode': 'single', 'mirror_single_team': 2,
         'mirror_initial_keyword': 'saved'}) == {'MirrorTaskSingleTeam': {'attach': {'slot': 2}}}
    patched = mirror_task_options.gui_override(
        {'mirror_team_mode': 'single', 'mirror_single_team': 3,
         'mirror_initial_keyword': 'tremor'})
    assert patched['MirrorInitialKeyword'] == {'attach': {'keyword': 'tremor'}}


def test_nothing_configured_produces_no_override():
    assert mirror_task_options.gui_override({}) == {}
