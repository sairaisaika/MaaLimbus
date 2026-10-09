"""Software startup update check; no game controller or game input."""
import json
import re
from pathlib import Path

from .releases import ReleaseClient
from .storage import write_json
from .update_install import metadata
from .update_stage import stage_release, StageError


def check_project_update(app, *, client_factory=ReleaseClient):
    """Explicit software-settings check: cache/limits, never stage or install."""
    current=metadata(app)['version']
    check=client_factory(app/'config/user-update-state.json').check()
    release=check.get('release') or {};tag=release.get('tag_name','')
    valid=bool(re.fullmatch(r'v?\d+\.\d+\.\d+',tag))
    newer=valid and tuple(map(int,tag.lstrip('v').split('.')))>tuple(map(int,current.lstrip('v').split('.')))
    status=check['status']
    if status in ('available','cached'):
        status='update_available' if newer else 'current' if valid else 'unsupported_release_tag'
    result=dict(current_version=current,available_version=tag or None,status=status,
        retry_at=check.get('retry_at'),requested=check['requested'],newer_available=newer,
        installed=False,downloaded=False,game_input_sent=False)
    write_json(app/'config/user-update-check-result.json',result)
    return result


def update_enabled(app):
    path = app/'config/mxu-MaaLimbus.json'
    if not path.exists():
        return True
    if path.stat().st_size > 2*1024*1024:
        raise StageError('Invalid GUI settings')
    data = json.loads(path.read_text(encoding='utf-8'))
    choice = data.get('globalOptionValues', {}).get('software_auto_update')
    if choice is None:
        return True
    if not isinstance(choice, dict) or choice.get('type') != 'select' or choice.get('caseName') not in ('enabled', 'disabled'):
        raise StageError('Invalid software update preference')
    return choice['caseName'] == 'enabled'


def startup_update(app, work, *, client_factory=ReleaseClient, stage=stage_release, install):
    """Network failure leaves the verified local app usable; ambiguous install does not."""
    app, work = Path(app), Path(work)
    current = metadata(app)['version']
    result = dict(status='disabled', installed=False, game_input_sent=False,
                  version_before=current, version_after=current)
    if update_enabled(app):
        check = client_factory(app/'config/user-update-state.json').check()
        result.update(status=check['status'], requested=check['requested'], retry_at=check['retry_at'])
        release = check.get('release')
        tag = release.get('tag_name', '') if isinstance(release, dict) else ''
        version = lambda value: tuple(map(int, value.lstrip('v').split('.')))
        if (check['status'] in ('available', 'cached') and
                re.fullmatch(r'v?\d+\.\d+\.\d+', tag) and version(tag) > version(current)):
            try:
                staged = stage(release, work/'stages', timeout=60,
                               cache=app/'config/user-update-state.json')
                if staged.get('status') != 'staged':
                    result.update(status='download_deferred')
                else:
                    proof = install(Path(staged['stage']), app)
                    result.update(status=proof['status'], installed=proof['installed'],
                                  install_proof=proof)
                    if proof['status'] not in ('installed', 'rolled_back'):
                        raise StageError('Update requires inspection before launch')
                    result['version_after'] = metadata(app)['version']
            except Exception:
                # An install may have swapped files: never hide that ambiguity.
                result.update(status='blocked', reason='update_validation_or_install_failed')
                write_json(app/'build/startup-update-result.json', result)
                raise
        elif check['status'] in ('available', 'cached'):
            result['status'] = ('current' if re.fullmatch(r'v?\d+\.\d+\.\d+', tag)
                                else 'unsupported_release_tag')
    write_json(app/'build/startup-update-result.json', result)
    return result
