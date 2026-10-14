"""Check whether a wiki line citation still lands near the symbol it names.

Read-only by default. The wiki cites source as `path.py:LINE`, usually next to the
`symbol` it means. Line numbers drift as the module is edited below them, and a
citation that lands on a *different* code line is structurally valid -- `check_wiki.py`
and the citation resolver cannot see it -- so this tool measures the drift explicitly.

A citation fails when the named code span (the identifier in backticks on the same
wiki line, e.g. `_verified_runs`) does not occur in the cited file within
``--window`` lines of the cited line. Citations whose line has no named span are
counted as ``unnamed`` and skipped; they are the "bare path:NNN" residue the wiki
audit already recorded. A named span that never occurs in the cited file at all -- or
that merely repeats the cited module's own name, as in "`run_wiring` (`run_wiring.py:81`)"
-- is counted as ``unattributed``: the tool refuses to call that drift, because the
line number may simply be the honest one for a symbol this measure cannot see.

``--apply`` re-points a drifted citation onto the single definition-like line of the
symbol it names (``def name``/``class name``/``name =``/``name:``), preserving any
``:start-end`` range suffix. Only symbols with exactly one such line in the cited file
are rewritten; everything else is printed as skipped for a human to judge.

Usage::

    python tools/verify_wiki_citations.py                 # summary
    python tools/verify_wiki_citations.py --limit 25      # summary + worst examples
    python tools/verify_wiki_citations.py --json out.json
    python tools/verify_wiki_citations.py --apply        # re-point what is unambiguous
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WIKI = ROOT / 'docs' / 'wiki'
BACKTICK = chr(96)
CITE = re.compile(BACKTICK + r'([A-Za-z0-9_./-]+\.py):(\d+)(?:[-,](\d+))?' + BACKTICK)
SPAN = re.compile(BACKTICK + r'([A-Za-z_][A-Za-z0-9_.]{2,60})' + BACKTICK)


def source_lines(rel):
    path = ROOT / rel
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def nearest_symbol(line, match):
    """The identifier the wiki names beside one citation, or None when it names none.

    The wiki writes either ``path.py:12`` `name` or `name` (``path.py:12``). Only a span
    that looks like a symbol counts -- an underscore, or a leading capital -- so prose
    like `pages` or `hard` is not mistaken for a name.
    """
    spans = [s for s in SPAN.finditer(line) if s.start() != match.start()]
    candidates = []
    after = [s for s in spans if s.start() >= match.end() and s.start() - match.end() <= 40]
    before = [s for s in spans if s.end() <= match.start() and match.start() - s.end() <= 40]
    if after:
        candidates.append(after[0])
    if before:
        candidates.append(before[-1])
    for span in candidates:
        text = span.group(1)
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{2,60}', text) and ('_' in text or text[0].isupper()):
            return text
    return None


def definition_lines(lines, symbol):
    """Line numbers where the symbol is defined rather than merely used."""
    word = re.compile(r'\b' + re.escape(symbol) + r'\b')
    found = []
    for number, line in enumerate(lines, 1):
        if not word.search(line):
            continue
        if re.match(r'\s*(def|class)\s+' + re.escape(symbol) + r'\b', line) or \
                re.match(r'\s*' + re.escape(symbol) + r'\s*[:=]', line):
            found.append(number)
    return found


def count_lines(lines, symbol):
    word = re.compile(r'\b' + re.escape(symbol) + r'\b')
    return [number for number, line in enumerate(lines, 1) if word.search(line)]


def check(window=16, pages=None, max_per_line=2):
    cache = {}
    rows = []
    totals = dict(citations=0, named=0, landed=0, drifted=0, unnamed=0, unresolvable=0, crowded=0,
                  unattributed=0)
    for page in sorted(WIKI.rglob('*.md')):
        if pages and page.name not in pages:
            continue
        for number, line in enumerate(page.read_text(encoding='utf-8').splitlines(), 1):
            matches = list(CITE.finditer(line))
            if len(matches) > max_per_line:
                # A table or a list row that names many citations at once: the symbol next
                # to one of them cannot be attributed to a particular line number, so the
                # row is counted apart instead of being guessed at.
                totals['citations'] += len(matches)
                totals['crowded'] += len(matches)
                continue
            for match in matches:
                rel, cited = match.group(1), int(match.group(2))
                totals['citations'] += 1
                if rel not in cache:
                    cache[rel] = source_lines(rel)
                lines = cache[rel]
                if lines is None:
                    totals['unresolvable'] += 1
                    continue
                symbol = nearest_symbol(line, match)
                if symbol is None:
                    totals['unnamed'] += 1
                    continue
                occurrences = count_lines(lines, symbol)
                if not occurrences or symbol == pathlib.PurePosixPath(rel).stem:
                    # The wiki named a word that is not in the cited file, or named the
                    # module itself: this measure cannot judge that citation, so it says so
                    # instead of reporting drift it cannot see.
                    totals['unattributed'] += 1
                    continue
                totals['named'] += 1
                low, high = max(0, cited - 1 - window), min(len(lines), cited + window)
                text = '\n'.join(lines[low:high])
                landed = symbol in text
                totals['landed' if landed else 'drifted'] += 1
                if not landed:
                    rows.append(dict(page=page.relative_to(ROOT).as_posix(), wiki_line=number, file=rel,
                                     cited=cited, cited_end=(int(match.group(3)) if match.group(3) else None),
                                     symbol=symbol, occurrences=len(occurrences),
                                     only_occurrence=(occurrences[0] if len(occurrences) == 1 else None),
                                     definitions=definition_lines(lines, symbol),
                                     cited_line=(lines[cited - 1].strip()[:120] if 0 < cited <= len(lines) else None),
                                     verdict='drifted'))
    return totals, rows


def read_text(path):
    with open(path, 'r', encoding='utf-8', newline='') as handle:
        return handle.read()


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text)


def apply_fixes(rows, dry_run=False):
    """Re-point the drifted citations whose named symbol has one definition-like line.

    Returns (applied, skipped); each entry is (row, new_line_number_or_reason).
    """
    applied, skipped = [], []
    for row in rows:
        definitions = row.get('definitions') or []
        if len(definitions) == 1:
            new = definitions[0]
        elif not definitions and row.get('only_occurrence'):
            # A constant or a note name that is never *defined* in the file still has one
            # home when it occurs exactly once: that line is where the wiki meant to point.
            new = row['only_occurrence']
        else:
            skipped.append((row, 'the symbol has %d definition-like lines and %d occurrences'
                            % (len(definitions), row.get('occurrences', 0))))
            continue
        if new == row['cited']:
            skipped.append((row, 'the citation already names its definition'))
            continue
        page = ROOT / row['page']
        text = read_text(page)
        lines = text.split('\n')
        number = row['wiki_line']
        if not 0 < number <= len(lines):
            skipped.append((row, 'the wiki line is gone'))
            continue
        match = None
        for candidate in CITE.finditer(lines[number - 1]):
            if candidate.group(1) == row['file'] and int(candidate.group(2)) == row['cited']:
                match = candidate
                break
        if match is None:
            skipped.append((row, 'the citation is no longer on that line'))
            continue
        replacement = BACKTICK + '%s:%d' % (row['file'], new)
        if row.get('cited_end') is not None:
            replacement += '-%d' % (new + (row['cited_end'] - row['cited']))
        replacement += BACKTICK
        lines[number - 1] = lines[number - 1][:match.start()] + replacement + lines[number - 1][match.end():]
        if not dry_run:
            write_text(page, '\n'.join(lines))
        applied.append((row, replacement))
    return applied, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description='Measure drift between wiki line citations and the symbols they name.')
    parser.add_argument('--window', type=int, default=16, help='how many lines either side still count as landed')
    parser.add_argument('--limit', type=int, default=0, help='print this many drifted examples')
    parser.add_argument('--page', action='append', default=None, help='only this wiki file name (repeatable)')
    parser.add_argument('--max-per-line', type=int, default=2,
                        help='lines naming more citations than this are counted apart, not attributed')
    parser.add_argument('--json', default=None, help='write the full result to this path')
    parser.add_argument('--apply', action='store_true', help='re-point the drifted citations that are unambiguous')
    parser.add_argument('--dry-run', action='store_true', help='with --apply, report the rewrites without writing them')
    args = parser.parse_args(argv)

    totals, rows = check(window=args.window, pages=args.page, max_per_line=args.max_per_line)
    print(json.dumps(dict(totals=totals, drifted=len(rows)) | {'window': args.window}, ensure_ascii=False))
    for row in rows[:args.limit]:
        print('drifted %s:%d cites %s:%d for `%s`; the cited line reads %r' % (
            row['page'], row['wiki_line'], row['file'], row['cited'], row['symbol'], row['cited_line']))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(dict(totals=totals, rows=rows), indent=2, ensure_ascii=False),
                                           encoding='utf-8')
    if args.apply:
        applied, skipped = apply_fixes(rows, dry_run=args.dry_run)
        for row, replacement in applied:
            print('re-pointed %s:%d -> `%s` for `%s`' % (row['page'], row['wiki_line'], replacement, row['symbol']))
        for row, reason in skipped:
            print('left for a human %s:%d cites %s:%d for `%s`: %s' % (
                row['page'], row['wiki_line'], row['file'], row['cited'], row['symbol'], reason))
        print(json.dumps(dict(applied=len(applied), skipped=len(skipped), dry_run=bool(args.dry_run))))
    # Named citations are the ones that can be judged; a drift is a documentation defect,
    # not a runtime failure, so this reports rather than fails the build.
    return 0


if __name__ == '__main__':
    sys.exit(main())
