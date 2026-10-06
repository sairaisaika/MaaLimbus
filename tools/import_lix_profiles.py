"""Import local saved Lix mirror preferences without starting either application."""
import argparse
from datetime import datetime,timezone
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import ProfileStore,read_json,write_json
from maalimbus.lix_profiles import import_profiles


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'config/user-team-profiles.json')
    args=parser.parse_args(); store=ProfileStore(args.output)
    existing=store.load() if store.path.exists() else ()
    source=read_json(args.source); teams=import_profiles(source,existing)
    if store.path.exists():
        backup=ROOT/'evidence/runtime'/('profile-import-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
        backup.mkdir(parents=True)
        (backup/'previous-profiles.json').write_bytes(store.path.read_bytes())
    restored=store.save(teams)
    assert restored==teams
    write_json(ROOT/'build/lix-profile-import-verification.json',dict(
        utc=datetime.now(timezone.utc).isoformat(),source=str(args.source.resolve()),
        source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        saved_team_slots=[t.slot for t in restored],game_input=False,
        auto_team_enabled=[t.slot for t in restored if t.auto_team],
        scope='preferences only; no in-game identities imported or changed'))
    print('Saved Lix rotation/preferences:',[t.slot for t in restored])


if __name__=='__main__':main()
