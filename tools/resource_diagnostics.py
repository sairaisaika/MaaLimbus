"""One read-only resource snapshot as JSON; never writes config/ or evidence/."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.resource_diagnostics import DEFAULT_INTERVAL_MS, GPU_TIMEOUT_S, sample


def parse_target(text):
    role,_,pid=text.partition('=')
    if not role or not pid.isdigit(): raise argparse.ArgumentTypeError(f'expected ROLE=PID, got {text!r}')
    return role,int(pid)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interval-ms', type=int, default=DEFAULT_INTERVAL_MS,
        help='Sampling window; 100 = one fully busy core, so a process may exceed 100')
    parser.add_argument('--target', type=parse_target, action='append', default=None,
        metavar='ROLE=PID', help='Sample this pid only; repeatable, default discovers MaaLimbus roles')
    parser.add_argument('--no-gpu', action='store_true', help='Skip the bounded nvidia-smi query')
    parser.add_argument('--gpu-timeout-s', type=float, default=GPU_TIMEOUT_S,
        help='Hard timeout for the single nvidia-smi call')
    args=parser.parse_args()
    gpu=None
    if not args.no_gpu:
        from maalimbus.resource_diagnostics import NvidiaSmiProvider
        gpu=NvidiaSmiProvider(timeout_s=args.gpu_timeout_s)
    print(json.dumps(sample(args.interval_ms, targets=args.target, gpu_provider=gpu),indent=2))


if __name__=='__main__': main()
