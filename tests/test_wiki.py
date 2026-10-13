"""The docs/wiki layer must not rot away from the repository.

`tools/check_wiki.py` carries the contract the two-language wiki was delivered
under: paired files, a fixed navigation line, mirrored heading structure, legal
Mermaid blocks covering the six diagram kinds the chapters promise, and prose
`path:line` anchors which resolve. These tests keep the repository on the right
side of it, so a page that drifts fails here instead of quietly misleading a
reader; the synthetic cases prove the guard actually reports drift.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('check_wiki', ROOT / 'tools/check_wiki.py')
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

WIKI = ROOT / 'docs' / 'wiki'


@pytest.fixture
def wiki_copy(tmp_path):
    """A throwaway copy of docs/wiki, so a test can break one page and re-check."""
    destination = tmp_path / 'wiki'
    shutil.copytree(WIKI, destination)
    return destination


def test_the_current_wiki_has_zero_problems():
    result = verify.check_wiki(WIKI, ROOT)
    assert result['problems'] == []


def test_the_six_promised_diagram_kinds_are_covered():
    result = verify.check_wiki(WIKI, ROOT)
    missing = set(verify.REQUIRED_DIAGRAMS) - set(result['diagram_types'])
    assert missing == set(), 'the wiki no longer draws %s' % sorted(missing)


def test_the_page_inventory_matches_the_delivered_wiki():
    assert sorted(p.name for p in (WIKI / 'zh_cn').glob('*.md')) == \
        sorted(p.name for p in (WIKI / 'en_us').glob('*.md'))
    assert len(list((WIKI / 'zh_cn').glob('*.md'))) == 10
    assert len(list((WIKI / 'en_us').glob('*.md'))) == 10
    assert (WIKI / 'README.md').exists()


def test_a_broken_navigation_line_is_reported(wiki_copy):
    page = wiki_copy / 'zh_cn' / '1-overview.md'
    lines = page.read_text(encoding='utf-8').split('\n')
    lines[2] = '[English](../en_us/1-overview.md)'
    page.write_text('\n'.join(lines), encoding='utf-8')
    problems = verify.check_wiki(wiki_copy)['problems']
    assert any(problem.startswith('[NAV]') and '1-overview.md' in problem for problem in problems)


def test_a_subpage_navigation_line_that_drops_the_chapter_link_is_reported(wiki_copy):
    page = wiki_copy / 'en_us' / '2.2-modules.md'
    lines = page.read_text(encoding='utf-8').split('\n')
    lines[2] = '[中文](../zh_cn/2.2-modules.md) · [← Index](index.md)'
    page.write_text('\n'.join(lines), encoding='utf-8')
    problems = verify.check_wiki(wiki_copy)['problems']
    assert any(problem.startswith('[NAV]') and '2.2-modules.md' in problem for problem in problems)


def test_an_unclosed_code_fence_is_reported(wiki_copy):
    page = wiki_copy / 'zh_cn' / '1-overview.md'
    with page.open('a', encoding='utf-8') as handle:
        handle.write('\n```mermaid\nflowchart LR\n  A --> B\n')
    problems = verify.check_wiki(wiki_copy)['problems']
    assert any(problem.startswith('[FENCE]') for problem in problems)


def test_heading_structure_drift_between_the_twin_pages_is_reported(wiki_copy):
    page = wiki_copy / 'en_us' / '1-overview.md'
    lines = page.read_text(encoding='utf-8').split('\n')
    del lines[[index for index, line in enumerate(lines) if line.startswith('### The goal chain')][0]]
    page.write_text('\n'.join(lines), encoding='utf-8')
    problems = verify.check_wiki(wiki_copy)['problems']
    assert any(problem.startswith('[HEADING]') for problem in problems)


def test_an_illegal_mermaid_type_is_reported(wiki_copy):
    page = wiki_copy / 'zh_cn' / '1-overview.md'
    with page.open('a', encoding='utf-8') as handle:
        handle.write('\n```mermaid\nflowChart LR\n  A --> B\n```\n')
    problems = verify.check_wiki(wiki_copy)['problems']
    assert any('illegal diagram type' in problem for problem in problems)


def test_an_anchor_in_a_diagram_is_a_label_but_one_in_prose_is_a_citation(wiki_copy):
    page = wiki_copy / 'zh_cn' / '1-overview.md'
    text = page.read_text(encoding='utf-8')
    text += '\n```mermaid\nflowchart LR\n  A[src/nowhere/fenced.py:99] --> B\n```\n'
    text += '\n散文里的 `src/nowhere/prose.py:99` 是引用。\n'
    page.write_text(text, encoding='utf-8')
    problems = verify.check_wiki(wiki_copy)['problems']
    assert not any('fenced.py' in problem for problem in problems)
    assert any('prose.py' in problem for problem in problems)
