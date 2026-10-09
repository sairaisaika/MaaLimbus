import pytest
from maalimbus.mirror_preferences import apply,collect
from maalimbus.policies import Team
from maalimbus.storage import ProfileStore,write_json,SINNERS


def fixture(tmp_path):
    store=ProfileStore(tmp_path/'user-team-profiles.json')
    store.save([Team(2,frozenset({'Charge'}),allow=frozenset({'Existing'}),
        deployment=SINNERS,graces=('1','3'),grace_budget=100),Team(7,frozenset({'Poise'}))])
    edit=dict(slot=2,allow='Battery',block='Risk',preferred='Bus',avoided='Factory',weight=75)
    return store,edit


def test_preference_editor_preserves_roster_system_star_other_team_and_prior_preferences(tmp_path):
    store,edit=fixture(tmp_path);old=store.load()
    changed=apply(tmp_path,edit,gifts={'Battery','Risk'},packs={'Bus','Factory'})
    assert changed.allow=={'Existing','Battery'} and changed.block=={'Risk'}
    assert dict(changed.pack_weights)=={'Bus':75,'Factory':0}
    assert (changed.deployment,changed.keywords,changed.graces,changed.grace_budget)==(
        old[0].deployment,old[0].keywords,old[0].graces,old[0].grace_budget)
    assert store.load()[1]==old[1]
    assert apply(tmp_path,edit,gifts={'Battery','Risk'},packs={'Bus','Factory'})==changed


@pytest.mark.parametrize('change',[dict(slot=True),dict(allow='Unknown'),dict(weight=True),
    dict(weight=0),dict(avoided='Bus')])
def test_invalid_preferences_preserve_all_profiles(tmp_path,change):
    store,edit=fixture(tmp_path);before=store.path.read_bytes();edit.update(change)
    with pytest.raises(ValueError):apply(tmp_path,edit,gifts={'Battery','Risk'},packs={'Bus','Factory'})
    assert store.path.read_bytes()==before


def test_active_team_edit_rejects_but_idempotent_saved_preferences_are_accepted(tmp_path):
    store,edit=fixture(tmp_path)
    write_json(tmp_path/'user-run-ledger.json',dict(version=1,active=dict(team=2,id='current')))
    before=store.path.read_bytes()
    with pytest.raises(ValueError,match='active'):apply(tmp_path,edit,gifts={'Battery','Risk'},packs={'Bus','Factory'})
    assert store.path.read_bytes()==before
    edit.update(allow='saved',block='saved',preferred='saved',avoided='saved')
    assert apply(tmp_path,edit,gifts=set(),packs=set())==store.load()[0]


def test_disabled_editor_does_not_resolve_inactive_child_options():
    assert collect(lambda name: {'attach':{'enabled':False}} if name=='MirrorPreferenceEdit' else
                   pytest.fail('inactive child was read')) is None
