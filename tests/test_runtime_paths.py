from pathlib import Path

from maalimbus.runtime_paths import application_root


def test_frozen_resources_belong_to_installation_not_extraction_or_cwd(tmp_path):
    app = tmp_path / 'installed'
    exe = app / 'agent' / 'MaaLimbusAgent.exe'
    assert application_root(executable=exe, frozen=True,
                            source_file=tmp_path/'temporary'/'main.py') == app
    assert application_root(executable=app/'runner'/'MaaLimbusRunner.exe',
                            frozen=True) == app


def test_development_root_and_explicit_replay_root(tmp_path):
    root = Path(__file__).resolve().parents[1]
    assert application_root(frozen=False) == root
    assert application_root(frozen=True, override=tmp_path) == tmp_path
