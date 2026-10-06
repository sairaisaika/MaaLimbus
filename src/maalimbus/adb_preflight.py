"""Read-only binding/foreground checks; never launches or sends Android input."""
import re
import subprocess

PACKAGE = 'com.ProjectMoon.LimbusCompany'


def foreground(adb, address):
    if not isinstance(address,str) or not address or address.startswith('-'):
        raise ValueError('Explicit ADB serial is required')
    result = subprocess.run([str(adb), '-s', address, 'shell', 'dumpsys', 'window'],
                            capture_output=True, text=True, timeout=8, check=True)
    lines = [line.strip() for line in result.stdout.splitlines() if 'mCurrentFocus=' in line]
    if len(lines)!=1 or not re.search(r'\s'+re.escape(PACKAGE)+r'/',lines[0]):
        raise RuntimeError('Limbus is not the uniquely identified foreground app')
    return lines[0]


def controller_foreground(info):
    if info.get('type')!='adb' or not info.get('adb_path') or not info.get('adb_serial'):
        raise ValueError('Actual Maa Android binding is required')
    return foreground(info['adb_path'],info['adb_serial'])
