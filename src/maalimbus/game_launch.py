"""Native Maa launch with durable intent and independent foreground confirmation."""
from .adb_preflight import PACKAGE, foreground_any, controller_foreground
from .session_flow import LAUNCH_INTENT
from .jobs import wait_job
from .storage import read_json, write_json


def open_game(controller, directory, journal, *, check_any=foreground_any,
              check_game=controller_foreground, rounds=5):
    info=controller.info
    if info.get('type')!='adb' or not info.get('adb_path') or not info.get('adb_serial'):
        raise ValueError('Cold launch needs a Maa Android controller; connect the Windows game first')
    current=check_any(info['adb_path'],info['adb_serial'])
    path=directory/'user-open-game-transaction.json'
    tx=read_json(path) if path.exists() else None
    if tx is not None and (tx.get('version')!=1 or tx.get('serial')!=info['adb_serial']):
        raise ValueError('Unresolved launch belongs to another controller')
    # An existing foreground game is already open. Never replay its title/menu.
    if current and PACKAGE+'/' in current:
        proof=check_game(info)
        if tx is not None:
            tx.update(completed=True,foreground=proof);write_json(path,tx)
        journal.record('game_open_observed',foreground=proof,input_sent=False)
        return dict(passed=True,reason='game_already_foreground',input_sent=False,foreground=proof)
    if tx is not None and not tx.get('completed'):
        raise ValueError('Launch confirmation pending; refuse a second start')
    tx=dict(version=1,serial=info['adb_serial'],intent=LAUNCH_INTENT,
            before_foreground=current,start_sent=True,completed=False)
    write_json(path,tx)
    journal.record('game_launch_intent',intent=LAUNCH_INTENT,serial=info['adb_serial'])
    wait_job(controller.post_start_app(LAUNCH_INTENT),timeout=30)
    for _ in range(rounds):
        try:
            proof=check_game(info)
        except (RuntimeError,OSError):
            continue
        tx.update(completed=True,foreground=proof);write_json(path,tx)
        return dict(passed=True,reason='game_foreground_after_native_launch',
                    input_sent=True,foreground=proof)
    return dict(passed=False,reason='launch_foreground_not_proven',input_sent=True,pending=True)
