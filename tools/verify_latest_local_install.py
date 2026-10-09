"""Audit the installed local settings/Agent without launching GUI or game input."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.update_install import private_hashes, self_test
from make_local_app import packaged_interface


def main():
    app=ROOT/'dist/MaaLimbus'
    log=(ROOT/'build/local-app-latest-settings-install.txt').read_text(encoding='utf8')
    result=json.loads(log[log.index('{'):])
    backup=Path(result['installation']['backup'])
    before=private_hashes(backup)
    after=private_hashes(app)
    assert len(before)==18 and all(after.get(name)==sha for name,sha in before.items())
    info=json.loads((app/'build-info.json').read_text())
    assert info['source_commit']=='67c71d693ebb778159bf5a4f8673372f134519ae' and not info['source_dirty']
    assert json.loads((app/'interface.json').read_text(encoding='utf8'))==packaged_interface()
    assert (app/'assets/resource/base/pipeline/mirror.json').read_bytes()==(ROOT/'assets/resource/base/pipeline/mirror.json').read_bytes()
    proof=self_test(app)
    assert proof['agent_self_test']
    toc=list((ROOT/'build/local-app-20261009103412').rglob('Analysis-00.toc'))
    assert toc
    for path in toc:
        content=path.read_text(encoding='utf8').lower()
        assert 'maafgohelper' not in content
    output=ROOT/'build/latest-local-settings-installed-verification.json'
    output.write_text(json.dumps(dict(source_commit=info['source_commit'],
        private_files_preserved=len(before),backup=str(backup),installed_agent=proof,
        interface_matches_source=True,pipeline_matches_source=True,
        frozen_analysis_has_fgo_modules=False,gui_interaction_verified=False,
        device_input=False),indent=2)+'\n')
    print(output)


if __name__=='__main__':main()
