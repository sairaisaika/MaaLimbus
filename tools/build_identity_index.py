"""Build an explicit partial ID index from retained revisioned localization data."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.owned_inventory import build_index
from fetch_identity_catalog import fetch_json,raw_url,state_path,LLC_REPO

if __name__=='__main__':
    source=ROOT/'build/upstream/state/63737d08adfb-Personalities.json.json'
    catalog=read_json(ROOT/'assets/resource/base/identity-catalog.json')
    index=build_index(read_json(source)['payload']['dataList'],catalog,dict(
        url='https://github.com/LocalizeLimbusCompany/LocalizeLimbusCompany',
        revision=catalog['commit']['LocalizeLimbusCompany/LocalizeLimbusCompany'],
        retained_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        wiki_url='https://limbuscompany.huijiwiki.com/wiki/Data%3APersonalities.json',
        wiki_imported=False,wiki_access_status=403))
    entries={x['id']:x for x in index['identities']}
    for directory,locale in (('EN','en'),('JP','jp')):
        path=directory+'/Personalities.json'
        payload,status=fetch_json(raw_url(LLC_REPO,index['provenance']['revision'],path),
            state_path(ROOT/'build/upstream/state',LLC_REPO,path))
        for item in payload['dataList']:
            if item.get('id') in entries:
                entries[item['id']]['titles'][locale]=item['title']
    target=ROOT/'assets/resource/base/identity-index.json';write_json(target,index)
    print(json.dumps(index['coverage']))
