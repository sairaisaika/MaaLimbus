import json
from types import SimpleNamespace
import pytest
from maalimbus.runtime_paths import data_directory, ledger_path


def binding(app, target):
    (app/'config').mkdir(parents=True)
    (app/'config/user-data-root.json').write_text(json.dumps({'version':1,'directory':str(target)}))


def test_shared_state_keeps_actual_active_scope(tmp_path, monkeypatch):
    import recognition
    from recognition import loop_store, Journal
    from maalimbus.storage import RunStore
    source=tmp_path/'source'; source.mkdir()
    store=RunStore(source/'user-run-ledger.json',[SimpleNamespace(slot=7)])
    original=store.start()
    app=tmp_path/'app'; binding(app,source)
    monkeypatch.delenv('MAALIMBUS_DATA_PATH',raising=False)
    monkeypatch.setattr(recognition,'ROOT',app)
    settings=SimpleNamespace(run_store='config/user-run-ledger.json',observe_only=False,team=2)
    actual,scope=loop_store(settings,Journal(tmp_path/'evidence'))
    assert scope==original and settings.team==7
    assert actual.path==source/'user-run-ledger.json'
    assert not (app/'config/user-run-ledger.json').exists()


def test_mxu_environment_and_all_private_files_share_binding(tmp_path,monkeypatch):
    source=tmp_path/'source';source.mkdir()
    app=tmp_path/'app';binding(app,source)
    monkeypatch.setenv('MAALIMBUS_DATA_PATH',str(app/'config'))
    assert data_directory(app)==source
    assert ledger_path('config/user-run-ledger.json',app)==source/'user-run-ledger.json'
    assert ledger_path('evidence/ledger.json',app)==app/'evidence/ledger.json'


def test_missing_or_chained_target_stops(tmp_path,monkeypatch):
    monkeypatch.delenv('MAALIMBUS_DATA_PATH',raising=False)
    source=tmp_path/'source';source.mkdir()
    app=tmp_path/'app';binding(app,source)
    (source/'user-data-root.json').write_text('{}')
    with pytest.raises(ValueError,match='Chained'):data_directory(app)
    (source/'user-data-root.json').unlink(); source.rmdir()
    with pytest.raises(ValueError,match='unavailable'):data_directory(app)


def test_traversal_ledger_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='Unsafe'):ledger_path('config/../ledger.json',tmp_path)
