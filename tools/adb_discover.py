"""Read-only: report what MaaToolkit's own ADB discovery finds. Sends no input."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from maa.library import Library
from maa.toolkit import Toolkit

from maalimbus.adb_device import discover, input_policy, INPUT_NAMES, SCREENCAP_NAMES, names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--address', required=True)
    args = parser.parse_args()
    Library.open(args.binary, agent_server=False)
    devices = Toolkit.find_adb_devices()
    print(f'discovered {len(devices)} device(s):')
    for device in devices:
        print(f"  name={device.name!r} address={device.address} adb={device.adb_path}")
        print(f"    screencap_methods={int(device.screencap_methods)} "
              f"{names(int(device.screencap_methods), SCREENCAP_NAMES)}")
        print(f"    input_methods={int(device.input_methods)} "
              f"{names(int(device.input_methods), INPUT_NAMES)}")
        print(f"    config={dict(device.config or {})}")
    record = discover(args.address)
    allowed, reason = input_policy(record)
    print(f'target {args.address}: source={record["source"]} name={record.get("name")!r}')
    print(f'  screencap={record["screencap_names"]} input={record["input_names"]}')
    print(f'  input_allowed={allowed} reason={reason}')


if __name__ == '__main__':
    main()
