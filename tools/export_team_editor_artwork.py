"""Export only public upstream editor artwork, never account screenshots."""
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT/'sources/upstream/LixAssistantLimbusCompany'
PIN = '431b432e22f0b0da08b95d7c478fa213be20b3e8'
SINNERS = ['Yi Sang','Faust','Don Quixote','RyoShu','Meursault','Hong Lu',
           'Heathcliff','Ishmael','Rodion','Sinclair','Outis','Gregor']

def main():
    images=[];manifest=[]
    for relative in ([f'lalc_backend/img/general/sinners/{name}.png' for name in SINNERS]
                     +[f'lalc_backend/img/general/mirror/stars/mirror_{n:02}.png' for n in range(10)]):
        data=(UPSTREAM/relative).read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Expected upstream PNG')
        images.append('data:image/png;base64,'+base64.b64encode(data).decode())
        manifest.append(dict(path=relative,sha256=hashlib.sha256(data).hexdigest()))
    out=ROOT/'desktop/mxu'
    (out/'teamArtwork.ts').write_text('// Public upstream game artwork; see ARTWORK_NOTICE.md.\n'
        +'export const SINNER_IMAGES = '+json.dumps(images[:12])+';\n'
        +'export const STAR_IMAGES = '+json.dumps(images[12:])+';\n',encoding='utf8')
    (out/'artwork-provenance.json').write_text(json.dumps(dict(upstream='https://github.com/HSLix/LixAssistantLimbusCompany',
        commit=PIN,license='AGPL-3.0; game artwork remains Project Moon property',images=manifest),indent=2)+'\n',encoding='utf8')
    (out/'ARTWORK_NOTICE.md').write_text('Editor reference artwork\n\n'
        'Unmodified public sinner portraits and ten base star cards from LixAssistantLimbusCompany, '
        f'commit {PIN}. The source paths and exact SHA256 hashes are in artwork-provenance.json. '
        'Upstream code is AGPL-3.0; the full license accompanies this source repository. '
        'Limbus Company artwork belongs to Project Moon. These are reference icons, not scanned account ownership '
        'or learned identity claims. No account screenshot is included. This does not close the public release artwork audit.\n',encoding='utf8')

if __name__=='__main__':main()
