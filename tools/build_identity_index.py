"""Build an explicit partial ID index from retained revisioned localization data."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.owned_inventory import build_index,wiki_systems
from fetch_identity_catalog import fetch_json,raw_url,state_path,LLC_REPO

if __name__=='__main__':
    source=ROOT/'build/upstream/state/63737d08adfb-Personalities.json.json'
    catalog=read_json(ROOT/'assets/resource/base/identity-catalog.json')
    supplement=read_json(ROOT/'assets/resource/base/wiki-identity-supplement.json')
    index=build_index(read_json(source)['payload']['dataList']+supplement['dataList'],catalog,dict(
        url='https://github.com/LocalizeLimbusCompany/LocalizeLimbusCompany',
        revision=catalog['commit']['LocalizeLimbusCompany/LocalizeLimbusCompany'],
        retained_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        wiki_url='https://limbuscompany.huijiwiki.com/wiki/Data%3APersonalities.json',
        wiki_imported=True,wiki_method=supplement['method'],wiki_revision=supplement['revision'],
        wiki_license=supplement['license'],wiki_attribution=supplement['attribution'],
        wiki_supplement_sha256=hashlib.sha256((ROOT/'assets/resource/base/wiki-identity-supplement.json').read_bytes()).hexdigest(),
        raw_api_access_status=403))
    entries={x['id']:x for x in index['identities']}
    system_path=ROOT/'assets/resource/base/wiki-identity-systems.json'
    systems_source=read_json(system_path);systems=wiki_systems(systems_source,set(entries))
    for identity,entry in entries.items():
        entry['static_keywords']=entry['keywords']
        entry['wiki_systems']=systems.get(identity)
        if identity in systems:entry['keywords']=systems[identity]['keywords']
    index['provenance']['wiki_systems']=dict(url=systems_source['source'],revision=systems_source['revision'],
        sha256=hashlib.sha256(system_path.read_bytes()).hexdigest(),license=systems_source['license'],
        attribution=systems_source['attribution'])
    for directory,locale in (('EN','en'),('JP','jp')):
        path=directory+'/Personalities.json'
        payload,status=fetch_json(raw_url(LLC_REPO,index['provenance']['revision'],path),
            state_path(ROOT/'build/upstream/state',LLC_REPO,path))
        for item in payload['dataList']:
            if item.get('id') in entries:
                entries[item['id']]['titles'][locale]=item['title']
    for item in supplement['dataList']:
        entries[item['id']]['titles']['en']=item['en_title']
    index['provenance']['supplement_en_title_source']=supplement['en_title_source']
    counts=[sum(x['sinner_index']==s for x in index['identities']) for s in range(1,13)]
    if counts!=supplement['playable_counts'] or len(entries)!=supplement['playable_id_count']:
        raise ValueError('Index differs from independently observed Wiki ID coverage')
    index['coverage'].update(wiki_revision_complete=True,wiki_playable_count=len(entries),
        wiki_systems_count=len(systems),wiki_systems_missing=supplement['playable_id_count']-len(systems),
        missing_aliases={locale:[x['id'] for x in index['identities'] if locale not in x['titles']]
                         for locale in ('en','jp')})
    target=ROOT/'assets/resource/base/identity-index.json';write_json(target,index)
    print(json.dumps(index['coverage']))
