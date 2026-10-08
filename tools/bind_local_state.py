"""Bind a closed development GUI to the verified source private state; retain both."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.runtime_paths import data_directory
from maalimbus.storage import read_json,write_json,ProfileStore
from maalimbus.update_install import closed_app,plain_path,plain_tree,metadata
from maalimbus.controller_lease import ControllerLease


def bind(app,source):
    app,source=plain_path(app),plain_path(source)
    metadata(app)
    if not read_json(app/'build-info.json').get('development_only'):
        raise ValueError('Only a local development installation may bind source state')
    plain_tree(source);plain_tree(app/'config')
    if (source/'user-data-root.json').exists():raise ValueError('Chained binding')
    ProfileStore(source/'user-team-profiles.json').load()
    ledger=read_json(source/'user-run-ledger.json')
    ui=read_json(app/'config/mxu-MaaLimbus.json')
    if ui['settings']['autoRunOnLaunch'] or any(t['enabled'] for i in ui['instances'] for t in i['tasks']):
        raise ValueError('Disable tasks and autorun before binding')
    marker=app/'config/user-data-root.json'
    if marker.exists():raise ValueError('Existing binding requires explicit review')
    before=(source/'user-run-ledger.json').read_bytes()
    lease=ControllerLease.acquire(ROOT/'build/controller.lock')
    backup=app.parent/('private-state-before-binding-'+uuid.uuid4().hex)
    try:
        closed_app(app)
        shutil.copytree(app/'config',backup/'installed-config')
        shutil.copytree(source,backup/'source-config')
        write_json(marker,dict(version=1,directory=str(source)))
        if data_directory(app)!=source or (source/'user-run-ledger.json').read_bytes()!=before:
            raise ValueError('Binding verification failed')
    except Exception:
        if marker.exists():marker.unlink()
        raise
    finally:lease.close()
    return dict(passed=True,backup=str(backup),data_directory=str(source),
                active_scope=(ledger.get('active') or {}).get('id'),
                both_original_states_retained=True,game_input=False,gui_dispatch_verified=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--source-config',type=Path,required=True)
    args=parser.parse_args()
    proof=bind(args.app,args.source_config)
    write_json(ROOT/'build/private-state-binding-verification.json',proof)
    print(json.dumps(proof))
