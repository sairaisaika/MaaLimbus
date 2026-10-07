from types import SimpleNamespace
import pytest
from maalimbus.adb_preflight import foreground, foreground_any, controller_foreground


def test_a_session_that_starts_the_client_may_read_the_window_in_front(monkeypatch):
    # The launch flow owns start-app, so the client is allowed to be down; the window
    # that is actually focused is still read from the device, never assumed.
    monkeypatch.setattr('maalimbus.adb_preflight.subprocess.run',
                        lambda *a, **k: SimpleNamespace(stdout='mCurrentFocus=Window{u0 launcher/Activity}'))
    assert foreground_any('adb.exe', '127.0.0.1:16416') == 'mCurrentFocus=Window{u0 launcher/Activity}'
    with pytest.raises(RuntimeError):
        foreground('adb.exe', '127.0.0.1:16416')
    monkeypatch.setattr('maalimbus.adb_preflight.subprocess.run',
                        lambda *a, **k: SimpleNamespace(stdout='mCurrentFocus=null'))
    assert foreground_any('adb.exe', '127.0.0.1:16416') == 'mCurrentFocus=null'
    with pytest.raises(ValueError):
        foreground_any('adb.exe', '')


@pytest.mark.parametrize('focus',[
    'mCurrentFocus=Window{u0 com.ProjectMoon.LimbusCompany.other/Activity}',
    'mCurrentFocus=Window{u0 launcher/Activity}',
    'mCurrentFocus=null',
    'mCurrentFocus=Window{u0 com.ProjectMoon.LimbusCompany/Activity}\nmCurrentFocus=null',
])
def test_wrong_ambiguous_and_null_foreground_never_authorize(monkeypatch,focus):
    monkeypatch.setattr('maalimbus.adb_preflight.subprocess.run',lambda *a,**k:SimpleNamespace(stdout=focus))
    with pytest.raises(RuntimeError):foreground('adb.exe','127.0.0.1:16416')


def test_exact_package_and_binding_are_required(monkeypatch):
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        assert kwargs['check'] and kwargs['timeout']==8
        return SimpleNamespace(stdout='mCurrentFocus=Window{u0 com.ProjectMoon.LimbusCompany/Activity}')
    monkeypatch.setattr('maalimbus.adb_preflight.subprocess.run',run)
    info=dict(type='adb',adb_path='adb.exe',adb_serial='127.0.0.1:16416')
    assert 'LimbusCompany' in controller_foreground(info)
    assert calls==[['adb.exe','-s','127.0.0.1:16416','shell','dumpsys','window']]
    for invalid in ({**info,'type':'win32'},{**info,'adb_serial':''},{**info,'adb_serial':'-a'}):
        with pytest.raises(ValueError):controller_foreground(invalid)
    assert len(calls)==1
