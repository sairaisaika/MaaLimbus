"""Install a validated staged update after all app/controller processes have exited."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from maalimbus.update_install import install_staged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--install', type=Path, required=True)
    args = parser.parse_args()
    result = install_staged(args.stage, args.install, ROOT/'build/controller.lock')
    print(json.dumps(result, indent=2))
    return 0 if result['installed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
