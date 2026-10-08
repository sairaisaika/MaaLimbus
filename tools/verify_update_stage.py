"""Stage a retained development ZIP using derived release metadata, without network/install/input."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.update_stage import stage_release, file_digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-record',type=Path,default=ROOT/'build/windows-package-latest.json')
    args=parser.parse_args()
    retained=json.loads(args.package_record.read_text(encoding='utf-8'))
    archive=Path(retained['archive'])
    assert file_digest(archive)==retained['sha256']
    # Stable release metadata here is deliberately derived, not published GitHub proof.
    version=retained.get('version') or json.loads((Path(retained['app'])/'interface.json').read_text(encoding='utf-8'))['version']
    name=f'MaaLimbus-win-x64-{version}.zip'
    sums=(retained['sha256']+'  '+name+'\n').encode()
    metadata={'tag_name':version,'assets':[
        {'name':name,'size':archive.stat().st_size,'digest':'sha256:'+retained['sha256'],
         'browser_download_url':f'https://github.com/sairaisaika/MaaLimbus/releases/download/{version}/'+name},
        {'name':'SHA256SUMS','size':len(sums),'digest':'sha256:'+hashlib.sha256(sums).hexdigest(),
         'browser_download_url':f'https://github.com/sairaisaika/MaaLimbus/releases/download/{version}/SHA256SUMS'}]}
    def transport(url,path,size,deadline,proxy):
        assert proxy is None
        if url.endswith('/SHA256SUMS'):
            path.write_bytes(sums);return
        with archive.open('rb') as source,path.open('xb') as target:
            while data:=source.read(65536):
                if time.monotonic()>=deadline:raise TimeoutError('Fixture deadline')
                target.write(data)
    result=stage_release(metadata,ROOT/'build/update-replay',transport=transport,timeout=120)
    assert result['status']=='staged' and result['files']==retained['files']
    assert not result['installed'] and not result['executed']
    info=json.loads((Path(result['package'])/'build-info.json').read_text(encoding='utf-8'))
    assert info['development_only'] and not info['verified_dungeon_clear']
    report={'passed':True,'scope':'retained development ZIP and derived stable release metadata; offline transport',
            'network_requested':False,'installed':False,'executed':False,'game_input_sent':False,
            'source_package_commit':info['source_commit'],'result':result,
            'public_release_verified':False,'verified_clear':False}
    (ROOT/'build/update-stage-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
