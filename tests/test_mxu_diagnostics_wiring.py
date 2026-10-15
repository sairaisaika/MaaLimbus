"""The opt-in diagnostics panel is wired into the pinned MXU source, deviceless.

It applies `tools/patch_mxu_client.py` to a private copy of the hash-pinned MXU
source and checks the three things a GUI review would otherwise be needed for:
the panel/section registration in `SettingsPage.tsx`, the Rust command in
`lib.rs`, and that the panel's invoke name matches the command it is declared
with. No window, no device, no build.
"""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import zipfile

import pytest

from maalimbus.runtime_paths import ROOT

UPSTREAM_SHA = 'b350877c03598922b14d1804923e331361acf64534494945274b80b5d28cec35'
INVOKE = 'limbus_resource_diagnostics'


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def pinned_source(tmp_path):
    archive = ROOT/'build/MXU-v2.7.1-source.zip'
    if archive.is_file() and digest(archive) == UPSTREAM_SHA:
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(tmp_path)
        return tmp_path/'MXU-2.7.1'
    upstream = ROOT/'sources/upstream/MXU'
    if (upstream/'src/components/SettingsPage.tsx').is_file():
        target = tmp_path/'MXU-2.7.1'
        shutil.copytree(upstream, target)
        return target
    pytest.skip('no pinned MXU source on this machine')


def patch_module():
    spec = importlib.util.spec_from_file_location('test_patch_mxu_client',
                                                  ROOT/'tools/patch_mxu_client.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def patched(tmp_path_factory):
    source = pinned_source(tmp_path_factory.mktemp('mxu'))
    module = patch_module()
    module.patch(source)
    module.patch(source)  # a second pass must not duplicate any hook
    return source


def test_the_settings_page_registers_the_panel_as_its_own_opt_in_section(patched):
    page = (patched/'src/components/SettingsPage.tsx').read_text(encoding='utf8')
    assert page.count("import { ResourceDiagnosticsPanel } from './ResourceDiagnosticsPanel';") == 1
    assert page.count("<ResourceDiagnosticsPanel />") == 1
    assert page.count("{id:'diagnostics',icon:Activity,") == 1
    assert 'Activity,' in page
    # the nav id must be the anchor the panel actually renders
    panel = (patched/'src/components/ResourceDiagnosticsPanel.tsx').read_text(encoding='utf8')
    assert 'id="section-diagnostics"' in panel


def test_the_panel_and_its_pure_module_are_copied_verbatim_from_the_overlay(patched):
    for overlay, target in (('ResourceDiagnosticsPanel.tsx', 'src/components/ResourceDiagnosticsPanel.tsx'),
                            ('resourceDiagnostics.ts', 'src/utils/resourceDiagnostics.ts')):
        assert digest(patched/target) == digest(ROOT/'desktop/mxu'/overlay)


def test_the_rust_command_is_declared_and_registered_once(patched):
    rust = (patched/'src-tauri/src/lib.rs').read_text(encoding='utf8')
    assert rust.count('mod limbus_diagnostics;') == 1
    assert rust.count(f'limbus_diagnostics::{INVOKE},') == 1
    helper = (patched/'src-tauri/src/limbus_diagnostics.rs').read_text(encoding='utf8')
    assert digest(patched/'src-tauri/src/limbus_diagnostics.rs') == digest(
        ROOT/'desktop/mxu/limbus_diagnostics.rs')
    assert f'pub async fn {INVOKE}(' in helper
    assert '--resource-diagnostics' in helper


def test_the_panel_invokes_exactly_the_command_the_rust_side_declares(patched):
    panel = (patched/'src/components/ResourceDiagnosticsPanel.tsx').read_text(encoding='utf8')
    helper = (patched/'src-tauri/src/limbus_diagnostics.rs').read_text(encoding='utf8')
    assert f"invoke<Snapshot>('{INVOKE}'," in panel
    assert f'pub async fn {INVOKE}(' in helper
    # argument name must be the camelCase form Tauri maps onto interval_ms
    assert '{intervalMs:windowMs}' in panel.replace(' ', '')
    assert 'interval_ms: Option<i64>' in helper


def test_the_panel_is_off_until_the_user_switches_it_on(patched):
    panel = (patched/'src/components/ResourceDiagnosticsPanel.tsx').read_text(encoding='utf8')
    assert 'useState(false)' in panel
    assert 'shouldSample(enabled,inFlight.current)' in panel
    assert 'setInterval' in panel and 'clearInterval' in panel
    assert 'ControllerLease' not in panel and 'controller.lock' not in panel
    assert '@tauri-apps/plugin-fs' not in panel and "'@tauri-apps/api/core'" in panel
