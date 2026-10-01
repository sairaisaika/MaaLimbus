"""Import locale-independent gift icons and keyword groups from pinned LALC.

Only cropped public gift icons are copied, never screenshots or account data.
AGPL source/asset provenance is retained in the generated catalog.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '431b432e22f0b0da08b95d7c478fa213be20b3e8'


def main():
    upstream = ROOT/'sources/upstream/LixAssistantLimbusCompany'
    revision = subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()
    if revision != COMMIT:
        raise RuntimeError('Review the new upstream revision before importing assets')
    source = upstream/'lalc_backend/img/general/ego_gifts'
    destination = ROOT/'assets/resource/base'
    gifts = {}
    for path in sorted(source.glob('*/*.png')):
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        target = destination/'image/gifts'/f'{digest}.png'
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
        gift = gifts.setdefault(path.stem, {'name':path.stem,'keywords':[], 'icons':[]})
        gift['keywords'].append(path.parent.name)
        icon = {'path':target.relative_to(destination).as_posix(),'sha256':digest,
                'source':path.relative_to(upstream).as_posix()}
        if not any(i['sha256']==digest for i in gift['icons']):
            gift['icons'].append(icon)
    catalog = {'version':1,'source':'https://github.com/HSLix/LixAssistantLimbusCompany',
               'commit':COMMIT,'license':'AGPL-3.0','reference_width':1280,
               'gifts':list(gifts.values())}
    (destination/'gift-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'gifts':len(gifts),'source_commit':COMMIT}))


if __name__ == '__main__':
    main()
