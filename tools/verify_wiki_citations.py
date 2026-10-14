"""Check whether a wiki line citation still lands near the symbol it names.

Read-only and deviceless. The wiki cites source as `path.py:LINE`, usually next to
the `symbol` it means. Line numbers drift as the module is edited below them, and a
citation that lands on a *different* code line is structurally valid -- `check_wiki.py`
and the citation resolver cannot see it -- so this tool measures the drift explicitly.

A citation fails when the named code span (the identifier in backticks on the same
wiki line, e.g. `_verified_runs`) does not occur in the cited file within
``--window`` lines of the cited line. Citations whose line has no named span are
counted as ``unnamed`` and skipped; they are the "bare path:NNN" residue the wiki
audit already recorded.

Usage::

    python tools/verify_wiki_citations.py                 # summary
    python tools/verify_wiki_citations.py --limit 25      # summary + worst examples
    python tools/verify_wiki_citations.py --json out.json
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


def check(window=16, pages=None, max_per_line=2):
    cache = {}
    rows = []
    totals = dict(citations=0, named=0, landed=0, drifted=0, unnamed=0, unresolvable=0, crowded=0)
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
                totals['named'] += 1
                low, high = max(0, cited - 1 - window), min(len(lines), cited + window)
                text = '\n'.join(lines[low:high])
                landed = symbol in text
                totals['landed' if landed else 'drifted'] += 1
                if not landed:
                    rows.append(dict(page=page.relative_to(ROOT).as_posix(), wiki_line=number, file=rel,
                                     cited=cited, symbol=symbol,
                                     cited_line=(lines[cited - 1].strip()[:120] if 0 < cited <= len(lines) else None),
                                     verdict='drifted'))
    return totals, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description='Measure drift between wiki line citations and the symbols they name.')
    parser.add_argument('--window', type=int, default=16, help='how many lines either side still count as landed')
    parser.add_argument('--limit', type=int, default=0, help='print this many drifted examples')
    parser.add_argument('--page', action='append', default=None, help='only this wiki file name (repeatable)')
    parser.add_argument('--max-per-line', type=int, default=2,
                        help='lines naming more citations than this are counted apart, not attributed')
    parser.add_argument('--json', default=None, help='write the full result to this path')
    args = parser.parse_args(argv)

    totals, rows = check(window=args.window, pages=args.page, max_per_line=args.max_per_line)
    print(json.dumps(dict(totals=totals, drifted=len(rows)) | {'window': args.window}, ensure_ascii=False))
    for row in rows[:args.limit]:
        print('drifted %s:%d cites %s:%d for `%s`; the cited line reads %r' % (
            row['page'], row['wiki_line'], row['file'], row['cited'], row['symbol'], row['cited_line']))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(dict(totals=totals, rows=rows), indent=2, ensure_ascii=False),
                                           encoding='utf-8')
    # Named citations are the ones that can be judged; a drift is a documentation defect,
    # not a runtime failure, so this reports rather than fails the build.
    return 0


if __name__ == '__main__':
    sys.exit(main())
