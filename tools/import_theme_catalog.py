"""Import pinned names and tiny fixed UI glyphs, never theme card artwork."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '431b432e22f0b0da08b95d7c478fa213be20b3e8'


def main():
    upstream = ROOT/'sources/upstream/LixAssistantLimbusCompany'
    if subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip() != COMMIT:
        raise RuntimeError('Review changed upstream before importing')
    root = ROOT/'assets/resource/base'
    cfg = upstream/'lalc_backend/config/theme_pack_cfg.json'
    names = json.loads(cfg.read_text(encoding='utf-8'))
    glyphs = {}
    for key in ('theme_pack_detail','pack_search','hard_mode','normal_mode','mirror_theme_pack_new'):
        source = upstream/f'lalc_backend/img/general/mirror/{key}.png'
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        target = root/f'image/themes/{key}.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source,target)
        glyphs[key] = dict(path=target.relative_to(root).as_posix(),sha256=digest,
                           source=source.relative_to(upstream).as_posix())
    data = dict(version=1,reference_width=1280,reference_height=720,
                source='https://github.com/HSLix/LixAssistantLimbusCompany',commit=COMMIT,
                license='AGPL-3.0',glyphs=glyphs,
                names=[dict(name=n,reference_weight=v['weight']) for n,v in names.items()],
                name_source=cfg.relative_to(upstream).as_posix(),
                name_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),
                note='Reference weights are provenance only. Active defaults are neutral 10; team overrides apply.')
    (root/'theme-catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'names':len(names),'glyphs':len(glyphs),'card_artwork_imported':False}))


if __name__ == '__main__':
    main()
