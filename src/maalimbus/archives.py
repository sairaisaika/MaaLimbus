"""Prevalidate portable Windows ZIPs before writing any member."""
from pathlib import Path, PurePosixPath
import re
import zipfile


def safe_name(name):
    path = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or '\x00' in name
            or path.is_absolute() or '..' in path.parts or not path.parts
            or any(p.endswith((' ', '.')) or re.search(r'[<>"|?*\x00-\x1f]', p)
                   or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I)
                   for p in path.parts)):
        raise ValueError('Unsafe archive path')
    return path.as_posix()


def extract_checked(archive, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Extraction requires a new directory')
    seen, kinds, total = set(), {}, 0
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if len(members) > 20000:
            raise ValueError('Too many archive members')
        for member in members:
            name = safe_name(member.orig_filename)
            canonical = name.casefold()
            mode = (member.external_attr >> 16) & 0o170000
            if canonical in seen or mode not in (0, 0o100000, 0o040000) or member.flag_bits & 1:
                raise ValueError('Duplicate, special or encrypted archive member')
            seen.add(canonical)
            kinds[canonical] = member.is_dir()
            total += member.file_size
            if total > 1_500_000_000 or member.file_size > 500_000_000:
                raise ValueError('Archive exceeds portable package limits')
        for name in seen:
            for parent in PurePosixPath(name).parents:
                if str(parent) in kinds and not kinds[str(parent)]:
                    raise ValueError('Archive file conflicts with a directory')
        # No file is created until every member passes the checks above.
        source.extractall(destination)
