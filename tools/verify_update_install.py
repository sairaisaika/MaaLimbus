"""Exercise real packaged Agent install and rollback in a new isolated directory."""
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from maalimbus.storage import write_json
from maalimbus.update_install import install_staged
from maalimbus.update_stage import verify_package


def main():
    staged = json.loads((ROOT/'build/update-stage-verification.json').read_text())['result']
    stage = Path(staged['stage'])
    verify_package(stage/'package')
    sandbox = ROOT/'build'/('update-install-verification-'+uuid.uuid4().hex)
    install = sandbox/'app'
    shutil.copytree(stage/'package', install)
    write_json(install/'config/nested/private-sentinel.json', {'retained': True})
    result = install_staged(stage, install, ROOT/'build/controller.lock')
    assert result['installed'] and result['verification']['agent_self_test']
    assert (Path(result['backup'])/'MaaLimbus.exe').is_file()
    assert json.loads((install/'config/nested/private-sentinel.json').read_text()) == {'retained': True}
    def failed_validation(app):
        raise RuntimeError('Injected verification failure after actual swap')
    rollback = install_staged(stage, install, ROOT/'build/controller.lock', validator=failed_validation)
    assert rollback['rolled_back'] and not rollback['installed']
    assert json.loads((install/'config/nested/private-sentinel.json').read_text()) == {'retained': True}
    report = {'passed': True, 'scope': 'isolated retained development package; real filesystem swap and Agent self-test',
              'desktop_install_changed': False, 'public_release_verified': False, 'network_requested': False,
              'game_input_sent': False, 'install': result, 'rollback': rollback}
    write_json(ROOT/'build/update-install-verification.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
