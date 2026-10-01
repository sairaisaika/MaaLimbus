"""Retain pinned small UI labels/glyphs for English experimental battle planning."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
COMMIT='431b432e22f0b0da08b95d7c478fa213be20b3e8'


def main():
    upstream=ROOT/'sources/upstream/LixAssistantLimbusCompany'
    assert subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()==COMMIT
    root=ROOT/'assets/resource/base';glyphs={}
    for name in ('win_rate','skill_slash','skill_pierce','skill_blunt'):
        source=upstream/f'lalc_backend/img/{"en" if name=="win_rate" else "general"}/battle/{name}.png'
        target=root/f'image/battle/{name}.png';target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        glyphs[name]={'path':target.relative_to(root).as_posix(),
            'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source':source.relative_to(upstream).as_posix()}
    data={'version':1,'reference_width':1280,'reference_height':720,'names':[],
        'commit':COMMIT,'source':'https://github.com/HSLix/LixAssistantLimbusCompany',
        'license':'AGPL-3.0','glyphs':glyphs,
        'scope':'Small English UI and damage markers only; no artwork, classifier model or runtime'}
    (root/'battle-catalog.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'glyphs':len(glyphs),'locale':'en','runtime_imported':False}))


if __name__=='__main__':main()
