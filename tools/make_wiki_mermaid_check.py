#!/usr/bin/env python
"""Render-check almost-guard for the docs/wiki mermaid blocks.

tools/check_wiki.py freezes what can be judged offline: fence pairing, the diagram
type keyword, the six diagram kinds the chapters promise. It cannot tell whether a
diagram body actually parses — `flowchart TD` on the first line says nothing about
whether a node label closes its brackets, and a broken diagram is a blank box on the
rendered page rather than a checker failure.

This generator writes build/wiki-mermaid-check.html: a self-contained page that holds
every mermaid block in docs/wiki and feeds each one to `mermaid.parse`, printing the
blocks the renderer rejects. It is deliberately not part of the pytest suite — it
needs a browser and a network fetch of the mermaid bundle, which an offline test run
does not have. The procedure is:

    python tools/make_wiki_mermaid_check.py
    python -m http.server 8791 --bind 127.0.0.1     # from the repository root
    # open http://127.0.0.1:8791/build/wiki-mermaid-check.html

The page is served over HTTP on purpose: a `file://` document cannot import the
mermaid ES module, and the import fails silently, leaving the page stuck on
"parsing" with no result. Read `window.__RESULT`, or the summary the page prints.

Read-only apart from the generated page. Exit 1 when the wiki holds no mermaid block
at all, so a silent no-op cannot pass for a clean run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / 'docs' / 'wiki'
DEFAULT_OUT = ROOT / 'build' / 'wiki-mermaid-check.html'

LANGUAGES = ('zh_cn', 'en_us')

FENCE_RE = re.compile(r'^(`{3,})\s*([^\s`]*)\s*$')

# Mermaid 11 is the version the delivery-time render check ran against; the wiki is
# written for that grammar (a state id may not contain a hyphen, an erDiagram entity
# name may).
MERMAID_URL = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'

PAGE_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>parsing</title>
<body>
<h1>wiki mermaid render check</h1>
<p id="status">parsing&hellip;</p>
<pre id="report"></pre>
<script type="module">
import mermaid from '%(mermaid_url)s';

mermaid.initialize({ startOnLoad: false });

const BLOCKS = %(blocks)s;

const results = [];
for (const block of BLOCKS) {
  try {
    await mermaid.parse(block.code);
    results.push({ page: block.page, index: block.index, start: block.start,
                   end: block.end, type: block.type, ok: true });
  } catch (error) {
    results.push({ page: block.page, index: block.index, start: block.start,
                   end: block.end, type: block.type, ok: false,
                   error: String((error && error.message) || error) });
  }
}

const failed = results.filter((row) => !row.ok);
window.__RESULT = results;
document.title = 'done:' + (results.length - failed.length) + '/' + results.length;
document.getElementById('status').textContent =
  (results.length - failed.length) + '/' + results.length + ' block(s) parsed'
  + (failed.length ? ' — ' + failed.length + ' rejected' : '');
document.getElementById('report').textContent = failed.length
  ? failed.map((row) => row.page + ' #' + row.index + ' (' + row.type + ', lines '
      + row.start + '-' + row.end + ')\\n' + row.error).join('\\n\\n')
  : 'all blocks parsed';
</script>
"""


def mermaid_blocks(wiki: Path) -> list:
    """Return every ```mermaid block in the wiki as page/index/start/end/type/code."""
    blocks = []
    for language in LANGUAGES:
        directory = wiki / language
        if not directory.is_dir():
            continue
        for page in sorted(directory.glob('*.md')):
            lines = page.read_text(encoding='utf-8', errors='replace').split('\n')
            relative = language + '/' + page.name
            for start, end, language_tag in fences(lines):
                if language_tag != 'mermaid':
                    continue
                body = lines[start:end]
                blocks.append({
                    'page': relative,
                    'index': len([b for b in blocks if b['page'] == relative]) + 1,
                    'start': start + 1,
                    'end': end + 1,
                    'type': (body[0].strip().split() or ['?'])[0] if body else '?',
                    'code': '\n'.join(body),
                })
    return blocks


def fences(lines: list) -> list:
    """Return (body_start, body_end, language) for every paired code fence."""
    pairs, opener, opener_language = [], None, ''
    for index, line in enumerate(lines):
        match = FENCE_RE.match(line)
        if not match:
            continue
        if opener is None:
            opener, opener_language = index, match.group(2)
        elif len(match.group(1)) >= len(FENCE_RE.match(lines[opener]).group(1)):
            pairs.append((opener + 1, index, opener_language))
            opener, opener_language = None, ''
    return pairs


def render(blocks: list, mermaid_url: str = MERMAID_URL) -> str:
    # `</script>` inside a diagram would close the module early, so escape `<`.
    payload = json.dumps(blocks, ensure_ascii=False).replace('<', r'\u003c')
    return PAGE_TEMPLATE % {'mermaid_url': mermaid_url, 'blocks': payload}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--wiki', default=str(WIKI),
                        help='the docs/wiki directory to read')
    parser.add_argument('--out', default=str(DEFAULT_OUT),
                        help='the page to write')
    arguments = parser.parse_args(argv)

    blocks = mermaid_blocks(Path(arguments.wiki))
    if not blocks:
        print('FAIL    : no mermaid block found under ' + arguments.wiki)
        return 1

    by_language, by_type = {}, {}
    for block in blocks:
        language = block['page'].split('/')[0]
        by_language[language] = by_language.get(language, 0) + 1
        by_type[block['type']] = by_type.get(block['type'], 0) + 1

    out = Path(arguments.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(blocks), encoding='utf-8')

    print('blocks    : ' + str(len(blocks))
          + ' (' + ', '.join(k + ' ' + str(v) for k, v in sorted(by_language.items())) + ')')
    print('types     : ' + ', '.join(k + ' ' + str(v) for k, v in sorted(by_type.items())))
    print('wrote     : ' + str(out))
    print('serve     : python -m http.server 8791 --bind 127.0.0.1')
    if out.is_relative_to(ROOT):
        print('open      : http://127.0.0.1:8791/' + out.relative_to(ROOT).as_posix())
    else:
        print('open      : ' + out.as_uri())
    return 0


if __name__ == '__main__':
    sys.exit(main())
