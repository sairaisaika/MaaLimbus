"""Assemble private partial inventory from hash-bound owned-gallery observations."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.learning_dataset import digest,local_file
from maalimbus.owned_inventory import owned_page,reconcile_titles


def assemble(root,frames,index_path):
    root=Path(root);index=read_json(local_file(root,index_path));latest={}
    for value in frames:
        path=local_file(root,value);record=read_json(path)
        if 'inventory_observations' not in record:continue
        sinner=owned_page(record)
        image=local_file(root,str(path.with_suffix('.png')))
        if digest(image)!=record.get('image_sha256'):
            raise ValueError('Owned inventory image changed')
        for row in record['inventory_observations']:
            if row.get('evidence')!={'frame':str(path),'image_sha256':digest(image)}:
                raise ValueError('Inventory observation detached from its frame')
        row=reconcile_titles(index,sinner,record['inventory_observations'],record.get('inventory_locale','en'))
        row.update(frame=str(path),frame_sha256=digest(path),image_sha256=digest(image),utc=record['utc'])
        if sinner not in latest or row['utc']>latest[sinner]['utc']:latest[sinner]=row
    return dict(schema_version=1,index_sha256=digest(local_file(root,index_path)),
        sinners=[latest[k] for k in sorted(latest)],sinners_observed=len(latest),
        inventory_complete=False,missing_sinners=[k for k in range(1,13) if k not in latest],
        account='local_observed_account',unobserved_ownership='unknown',
        equipment_modified=False,resources_spent=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',type=Path,default=ROOT/'assets/resource/base/identity-index.json')
    p.add_argument('--output',type=Path,default=ROOT/'build/private-owned-inventory.json')
    a=p.parse_args();frames=sorted((ROOT/'evidence/runtime').glob('sinner-sample-20261012-*/frame-*.json'))
    result=assemble(ROOT,frames,a.index);write_json(a.output,result)
    print('sinners:',result['sinners_observed'],'matched:',sum(len(s['owned']) for s in result['sinners']),
          'unresolved:',sum(len(s['unresolved']) for s in result['sinners']),'complete:',False)
