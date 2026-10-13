#!/usr/bin/env python
"""Acceptance guard for the docs/wiki narrative layer.

The wiki explains PROJECT.md, docs/design.md and docs/acceptance.md rather than
replacing them, and it is bound to the code by `relative/path:line` anchors. It is
delivered in two mirrored languages (`zh_cn` / `en_us`). Nothing else in the suite
notices when a page drifts away from the repository, so this checker freezes the
contract the pages were delivered under and exits non-zero the moment one rots:

* `zh_cn/` and `en_us/` mirror each other file by file: every page has a twin.
* Every page except `index.md` and `README.md` carries the fixed navigation line on
  line 3 (line 1 is the title, line 2 is blank).
* A page's `##` / `###` heading numbers, their levels and their order mirror its
  twin's, so a section added to one language alone is reported.
* Code fences pair up and every mermaid block names a diagram type from the
  Mermaid grammar.
* Across the site the six diagram kinds the chapters promise are covered:
  architecture / flow / deployment (`flowchart`), sequence (`sequenceDiagram`),
  state (`stateDiagram-v2`) and data model (`erDiagram`).
* A `path:line` reference in prose resolves to a real file and a line that exists.
  A reference inside a fence is a diagram label, not a citation — a chapter that
  shortens paths inside a diagram must spell the shorthand out in prose
  (docs/wiki/zh_cn/4-business-flows.md:9).
* A twin pair's sizes stay within a sane ratio, so one language is not left
  half-translated.

Read-only. Exit 1 when a page breaks one of those rules.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / 'docs' / 'wiki'

LANGUAGES = ('zh_cn', 'en_us')

# Diagram kinds the chapters promise, and the upstream diagram each one stands for.
REQUIRED_DIAGRAMS = {
    'flowchart': 'architecture / flow / deployment',
    'sequenceDiagram': 'sequence',
    'stateDiagram-v2': 'state',
    'erDiagram': 'data model',
}

# The Mermaid grammar's root keywords. A diagram whose first content line is not one
# of these is a typo the renderer would reject.
LEGAL_DIAGRAMS = {
    'flowchart', 'graph', 'sequenceDiagram', 'stateDiagram-v2', 'stateDiagram',
    'erDiagram', 'classDiagram', 'journey', 'gantt', 'pie', 'mindmap', 'timeline',
    'quadrantChart', 'gitGraph', 'C4Context', 'C4Container', 'C4Component',
    'sankey-beta', 'xychart-beta', 'block-beta', 'packet-beta', 'requirementDiagram',
    'architecture-beta', 'zenuml',
}

FENCE_RE = re.compile(r'^(`{3,})\s*([^\s`]*)\s*$')
HEADING_RE = re.compile(r'^(#{2,3})\s+(.+?)\s*$', re.M)
LABEL_PREFIX_RE = re.compile(r'^(?:图|表|Figure|Table)\s+')
NUMBER_RE = re.compile(r'^(?:[Dd]\d+|\d+(?:[.\-]\d+)*)')

# Only anchored refs (`path/file.ext:line`) are enforced; a bare `file.ext` in prose
# is not a citation which can be resolved, so it is left alone.
EXTENSIONS = (r'(?:py|md|json|jsonc|rs|tsx|ts|mjs|js|toml|yml|yaml|txt|cfg|ini|svg'
              r'|exe|dll|bat|ps1|sh|lock)')
PATH_CHARS = r'[A-Za-z0-9_./\\-]'
REF_RE = re.compile(r'(' + PATH_CHARS + r'+\.' + EXTENSIONS
                    + r'):(\d+)(?:\s*[-\u2013]\s*(\d+))?')


def nav_line(language: str, page: str, parent: str = None) -> str:
    """The fixed line 3 of `page`; the task pages 2.2 / 2.3 append a chapter backlink."""
    other = LANGUAGES[1] if language == LANGUAGES[0] else LANGUAGES[0]
    if language == 'zh_cn':
        line = '[English](../%s/%s) · [← 索引](index.md)' % (other, page)
        if parent:
            line += ' · [← 第 %s 章](%s)' % (parent.split('-', 1)[0], parent)
        return line
    line = '[中文](../%s/%s) · [← Index](index.md)' % (other, page)
    if parent:
        line += ' · [← Chapter %s](%s)' % (parent.split('-', 1)[0], parent)
    return line


def scan_fences(lines: list) -> tuple:
    """Pair code fences. Returns (blocks, unclosed_open_index).

    A block is `(open_index, close_index, language)`; content lives strictly between
    the two indices. A closing fence must use at least as many backticks as its
    opener and carry no info string.
    """
    blocks, open_at, open_len, open_lang = [], None, 0, ''
    for index, line in enumerate(lines):
        match = FENCE_RE.match(line)
        if open_at is None:
            if match:
                open_at, open_len, open_lang = index, len(match.group(1)), match.group(2)
        elif match and len(match.group(1)) >= open_len and not match.group(2):
            blocks.append((open_at, index, open_lang))
            open_at = None
    return blocks, open_at


def prose_only(lines: list, blocks: list) -> str:
    """The page with every fenced block blanked out, so diagram labels are not cited."""
    masked = list(lines)
    for start, end, _ in blocks:
        for index in range(start + 1, end):
            masked[index] = ''
    return '\n'.join(masked)


def diagram_type(lines: list, start: int, end: int) -> str:
    """The Mermaid root keyword of the block, skipping comments and directives."""
    for body in lines[start + 1:end]:
        stripped = body.strip()
        if not stripped or stripped.startswith('%%') or stripped.startswith('---'):
            continue
        return re.split(r'[\s{(\[]', stripped, maxsplit=1)[0]
    return ''


def heading_key(level: str, text: str) -> tuple:
    """A language-independent identity for a heading: level plus its number."""
    text = LABEL_PREFIX_RE.sub('', text)
    match = NUMBER_RE.match(text)
    return (len(level), match.group(0).upper() if match else '')


def page_stem(page: str) -> str:
    """`2.2-modules.md` -> `2.2-modules`, so a `2.2` subpage is told apart from `.md`."""
    return page.rsplit('.', 1)[0]


def parent_page(page: str, siblings: list) -> str:
    """For a `2.2-...` subpage, its `2-...` chapter page, if there is exactly one."""
    stem = page_stem(page)
    if '.' not in stem:
        return None
    major = stem.split('.', 1)[0]
    candidates = [name for name in siblings if name.startswith(major + '-')]
    return candidates[0] if len(candidates) == 1 else None


def check_wiki(wiki: Path = None, root: Path = None) -> dict:
    """Run every rule against `wiki`. Returns problems plus the inventory the tests read."""
    wiki = Path(wiki) if wiki is not None else WIKI
    root = Path(root) if root is not None else ROOT
    problems: list = []

    files = sorted(wiki.rglob('*.md')) if wiki.exists() else []
    if not files:
        return {'problems': ['[WIKI] no markdown files under %s' % wiki], 'files': 0,
                'languages': {}, 'diagram_types': {}, 'pages': {}}

    relative = {f.relative_to(wiki).as_posix() for f in files}
    present = {language: sorted(p[len(language) + 1:] for p in relative
                                if p.startswith(language + '/')) for language in LANGUAGES}

    # --- zh/en file pairing -------------------------------------------------
    for language in LANGUAGES:
        other = LANGUAGES[1] if language == LANGUAGES[0] else LANGUAGES[0]
        for page in set(present[language]) - set(present[other]):
            problems.append('[PAIR] %s has no %s twin: %s' % (language, other, page))

    # --- per-page checks ----------------------------------------------------
    pages: dict = {}
    diagram_types: dict = {}
    for path in files:
        name = path.relative_to(wiki).as_posix()
        lines = path.read_text(encoding='utf-8', errors='replace').split('\n')
        language = name.split('/', 1)[0] if '/' in name else ''
        page = name.split('/', 1)[1] if '/' in name else name
        is_routing = page == 'index.md' or name == 'README.md'

        blocks, unclosed = scan_fences(lines)
        prose = prose_only(lines, blocks)
        if unclosed is not None:
            problems.append('[FENCE] %s: unclosed code fence opened at line %d'
                            % (name, unclosed + 1))

        # Line 3 navigation. README.md and index.md carry their own routing text.
        if not is_routing:
            expected = nav_line(language, page, parent_page(page, present.get(language, [])))
            actual = lines[2] if len(lines) > 2 else ''
            if actual != expected:
                problems.append('[NAV] %s:3: expected %r, found %r' % (name, expected, actual))

        # Mermaid blocks: legal type, and at least one per chapter page.
        mermaid = [(start + 2, diagram_type(lines, start, end)) for start, end, lang in blocks
                   if lang == 'mermaid']
        for line_number, kind in mermaid:
            if kind not in LEGAL_DIAGRAMS:
                problems.append('[MERMAID] %s:%d: illegal diagram type %r'
                                % (name, line_number, kind))
            diagram_types[kind] = diagram_types.get(kind, 0) + 1
        if not mermaid and not is_routing and '.' not in page_stem(page):
            problems.append('[MERMAID] %s: no mermaid block' % name)

        # Anchors are citations only outside a fence.
        broken, resolved = [], 0
        for match in REF_RE.finditer(prose):
            raw, first, last = match.group(1), match.group(2), match.group(3)
            if '/' not in raw and '\\' not in raw:
                continue
            target = root / raw.strip().lstrip('./')
            if not target.exists():
                broken.append('%s:%s (path not found)' % (raw, first))
                continue
            if target.is_dir():
                broken.append('%s:%s (is a directory)' % (raw, first))
                continue
            resolved += 1
            total = len(target.read_text(encoding='utf-8', errors='replace').split('\n'))
            line_number = max(int(first), int(last) if last else 0)
            if line_number > total:
                broken.append('%s:%d (file has only %d lines)' % (raw, line_number, total))
        for item in dict.fromkeys(broken):
            problems.append('[REF] %s: %s' % (name, item))

        pages[name] = {'lines': len(lines), 'mermaid': len(mermaid), 'anchors': resolved,
                       'headings': len(HEADING_RE.findall(prose))}

    # --- heading mirror between the two languages ---------------------------
    for page in sorted(set(present[LANGUAGES[0]]) & set(present[LANGUAGES[1]])):
        twins = {}
        for language in LANGUAGES:
            body = (wiki / language / page).read_text(encoding='utf-8', errors='replace').split('\n')
            blocks, _ = scan_fences(body)
            twins[language] = [(heading_key(*m.groups()), m.group(2))
                               for m in HEADING_RE.finditer(prose_only(body, blocks))]
        left, right = twins[LANGUAGES[0]], twins[LANGUAGES[1]]
        if len(left) != len(right):
            problems.append('[HEADING] %s: %s has %d headings, %s has %d'
                            % (page, LANGUAGES[0], len(left), LANGUAGES[1], len(right)))
        for index, (one, two) in enumerate(zip(left, right)):
            if one[0] != two[0]:
                problems.append('[HEADING] %s: heading %d is %r in %s but %r in %s'
                                % (page, index + 1, one[1], LANGUAGES[0], two[1], LANGUAGES[1]))
                break

    # --- size mirror --------------------------------------------------------
    for page in sorted(set(present[LANGUAGES[0]]) & set(present[LANGUAGES[1]])):
        counts = [pages['%s/%s' % (language, page)]['lines'] for language in LANGUAGES]
        ratio = round(counts[0] / counts[1], 2) if counts[1] else 0
        if ratio < 0.6 or ratio > 1.7:
            problems.append('[MIRROR] %s: %s=%d %s=%d ratio=%s'
                            % (page, LANGUAGES[0], counts[0], LANGUAGES[1], counts[1], ratio))

    # --- required diagram coverage -----------------------------------------
    for kind, meaning in REQUIRED_DIAGRAMS.items():
        if kind not in diagram_types:
            problems.append('[DIAGRAM] no %s block on the site (the %s diagram)'
                            % (kind, meaning))

    return {'problems': problems, 'files': len(files), 'languages': present,
            'diagram_types': diagram_types, 'pages': pages}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--wiki', default=str(WIKI), help='the docs/wiki directory to check')
    parser.add_argument('--root', default=str(ROOT),
                        help='repository root a path:line anchor resolves against')
    args = parser.parse_args(argv)

    result = check_wiki(Path(args.wiki), Path(args.root))
    counts = ', '.join('%s %d' % (language, len(result['languages'].get(language, [])))
                       for language in LANGUAGES)
    diagrams = ', '.join('%s %d' % (kind, result['diagram_types'].get(kind, 0))
                         for kind in REQUIRED_DIAGRAMS)
    readme = Path(args.wiki) / 'README.md'
    print('wiki      : %s (%d markdown files)' % (args.wiki, result['files']))
    print('pages     : %s, README.md %s' % (counts, 'present' if readme.exists() else 'MISSING'))
    print('diagrams  : %s' % diagrams)
    for problem in result['problems']:
        print('PROBLEM   : %s' % problem)
    print('%s — %d problem(s)' % ('ok' if not result['problems'] else 'broken',
                                  len(result['problems'])))
    return 1 if result['problems'] else 0


if __name__ == '__main__':
    sys.exit(main())
