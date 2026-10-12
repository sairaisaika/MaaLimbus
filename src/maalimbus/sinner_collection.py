"""Only the observed HOME -> Sinners menu transition, never team edits."""
from .vision import Text,find
from .storage import read_json,write_json
from .learning_dataset import local_file,digest
from pathlib import Path
from .deployment import CENTERS
from .storage import SINNERS


def library_controls(record):
    if record.get('scene')!='TEAM_LIBRARY' or record.get('size')!=[1920,1080]:
        raise ValueError('Fresh actual team library required')
    texts=[Text(x['text'],tuple(x['box']),x['score']) for x in record.get('ocr',[])]
    for label,roi in ((r'^Details$',(.60,.04,.95,.35)),(r'^TEAMS$',(.03,.08,.20,.8)),
                      (r'^TEAMS\s*#\s*[1-9][0-9]?$',(.15,.12,.38,.23))):
        if len(find(texts,label,roi,record['size'],.9))!=1:
            raise ValueError('Independent actual library controls missing')


def inventory_view_target(record,slot):
    library_controls(record)
    if type(slot) is not int or not 1<=slot<=12:raise ValueError('Sinner index must be1..12')
    x,y=CENTERS[SINNERS[slot-1]]
    # The game library's canonical12 positions, not the saved deployment order.
    return [round(x*1.5)-12,round(y*1.5)-12,24,24]


def finish_returned_details(root,intent,closure):
    """Archive a proven detail-view round trip, without claiming inventory scan."""
    from .overlay_dismissal import identity_details
    root=Path(root).resolve();state=read_json(intent);closed=read_json(closure)
    if state.get('pending') is not True:return False
    if closed.get('pending') is not False or closed.get('closer',{}).get('kind')!='identity_details':
        raise ValueError('Actual detail-view closure required')
    before=local_file(root,state['before']);detail=local_file(root,closed['before']);after=local_file(root,closed['successor'])
    for path,expected_json,expected_png in ((before,state['before_sha256'],state['png_sha256']),
             (detail,closed['before_sha256'],closed['png_sha256'])):
        if digest(path)!=expected_json or digest(local_file(root,str(path.with_suffix('.png'))))!=expected_png:
            raise ValueError('Inventory navigation proof changed')
    inventory_view_target(read_json(before),state['sinner_index'])
    if not identity_details(read_json(detail)):raise ValueError('Independent detail-view controls absent')
    library_controls(read_json(after))
    if digest(local_file(root,str(after.with_suffix('.png'))))!=closed['successor_png_sha256']:
        raise ValueError('Returned library image changed')
    state.update(pending=False,observed_view='identity_details',inventory_complete=False,
        returned_library=str(after),returned_library_png_sha256=closed['successor_png_sha256'],
        detail_closure_sha256=digest(local_file(root,closure)))
    write_json(intent,state);return True


def home_sinners_target(record):
    size=record.get('size')
    if size!=[1920,1080] or record.get('scene')!='HOME':
        raise ValueError('Fresh independent HOME required for Sinners navigation')
    texts=[Text(x['text'],tuple(x['box']),x['score']) for x in record.get('ocr',[])]
    for label,region in ((r'^Window$',(.61,.86,.68,.96)),(r'^Drive$',(.73,.86,.81,.96))):
        if len(find(texts,label,region,size,.9))!=1:
            raise ValueError('Independent HOME navigation controls missing')
    matches=find(texts,r'^Sinners$',(.67,.86,.74,.96),size,.9)
    if len(matches)!=1:raise ValueError('Unique Sinners menu control missing')
    return list(matches[0].box)


def reconcile(root,intent,frame):
    """Read-only fresh library successor may resolve the one retained menu input."""
    root=Path(root).resolve()
    state=read_json(intent)
    if state.get('pending') is not True:return False
    fresh=local_file(root,frame);record=read_json(fresh)
    if record.get('scene')!='TEAM_LIBRARY':return False
    library_controls(record)
    before=local_file(root,state['before'])
    if (state.get('expected_successor')!='TEAM_LIBRARY' or digest(before)!=state.get('before_sha256') or
            digest(local_file(root,str(before.with_suffix('.png'))))!=state.get('png_sha256')):
        raise ValueError('Original collection intent proof changed')
    home_sinners_target(read_json(before))
    if digest(local_file(root,str(fresh.with_suffix('.png'))))!=record.get('image_sha256'):
        raise ValueError('Fresh collection successor PNG changed')
    state.update(pending=False,successor=str(fresh),successor_json_sha256=digest(fresh),
                 successor_png_sha256=record['image_sha256'])
    write_json(intent,state)
    return True
