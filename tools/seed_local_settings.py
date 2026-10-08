"""Import private CLI builds into the closed local app; never include them in releases."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import ProfileStore,read_json,write_json
from maalimbus.settings_migration import seed_editors
from maalimbus.update_install import plain_path,plain_tree,closed_app
from maalimbus.controller_lease import ControllerLease


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--source-config',type=Path,required=True)
    args=parser.parse_args()
    app,source=plain_path(args.app),plain_path(args.source_config)
    if not (app/'MaaLimbus.exe').is_file():raise ValueError('Expected local MaaLimbus app')
    plain_tree(source);plain_tree(app/'config')
    teams=ProfileStore(source/'user-team-profiles.json').load()
    interface=read_json(app/'interface.json')
    path=app/'config/mxu-MaaLimbus.json'
    before=read_json(path)
    if before['settings']['autoRunOnLaunch'] or any(t['enabled'] for i in before['instances'] for t in i['tasks']):
        raise ValueError('Disable tasks and autorun before private settings migration')
    after,changed=seed_editors(before,interface,teams)
    files=list(source.glob('user-*.json'))
    for original in files:
        read_json(original)
        destination=app/'config'/original.name
        if destination.exists() and destination.read_bytes()!=original.read_bytes():
            raise ValueError('Local app already owns different private state; refuse overwrite')
    copied=[]
    lease=ControllerLease.acquire(ROOT/'build/controller.lock')
    backup=path.with_name(path.name+'.pre-build-import-'+uuid.uuid4().hex)
    try:
        closed_app(app)
        shutil.copyfile(path,backup)
        for original in files:
            destination=app/'config'/original.name
            if not destination.exists():
                shutil.copyfile(original,destination);copied.append(destination)
        write_json(path,after)
    except Exception:
        if backup.exists():shutil.copyfile(backup,path)
        for destination in copied:destination.unlink()
        raise
    finally:lease.close()
    proof=dict(passed=True,app=str(app),private_files_imported=len(copied),
               global_fields_seeded=len(changed),gui_backup=str(backup),
               source_profiles_changed=False,game_input=False,gui_restart_verified=False)
    write_json(ROOT/'build/local-global-build-import-verification.json',proof)
    print(json.dumps(proof))


if __name__=='__main__':main()
