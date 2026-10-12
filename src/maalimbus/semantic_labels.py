"""Automatic native-teacher semantic proposals, separate from NN predictions."""
from .storage import read_json
from .learning_dataset import local_file,digest
from .owned_inventory import owned_page,reconcile_titles


def collect(root,index_path,inventory_path):
    index_file=local_file(root,index_path);index=read_json(index_file)
    inventory=read_json(local_file(root,inventory_path))
    if inventory['index_sha256']!=digest(index_file):raise ValueError('Inventory catalogue revision changed')
    lookup={x['id']:x for x in index['identities']};labels=[]
    for page in inventory['sinners']:
        frame=local_file(root,page['frame']);record=read_json(frame)
        image=local_file(root,str(frame.with_suffix('.png')))
        if digest(frame)!=page['frame_sha256'] or digest(image)!=page['image_sha256']:
            raise ValueError('Native teacher evidence changed')
        if record.get('image_sha256')!=digest(image) or owned_page(record)!=page['sinner_index']:
            raise ValueError('Independent owned-page teacher differs')
        actual=reconcile_titles(index,page['sinner_index'],record['inventory_observations'],record.get('inventory_locale','en'))
        if actual['owned']!=page['owned']:raise ValueError('Owned identity reconciliation changed')
        for owned in actual['owned']:
            item=lookup[owned['id']];systems=item.get('wiki_systems')
            labels.append(dict(kind='owned_identity_semantics',personality_id=item['id'],
                sinner_index=item['sinner_index'],owned=True,level=owned['level'],uptie=owned['uptie'],
                systems=systems['keywords'] if systems is not None else None,
                unknown_systems=systems['unknown_keywords'] if systems is not None else None,
                teacher='native_owned_filter_and_exact_title_plus_revisioned_wiki_id',
                catalogue_sha256=digest(index_file),frame=str(frame),frame_sha256=digest(frame),
                image_sha256=digest(image),reviewed=False,training_eligible=False,
                model_applied=False,input_authorized=False))
    return dict(schema_version=1,labels=labels,automatic_teacher_proposals=True,
        neural_predictions=False,model_trained=False,training_eligible=False,
        inventory_complete=inventory['inventory_complete'],unobserved_ownership='unknown')
