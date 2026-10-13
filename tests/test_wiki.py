"""The docs/wiki layer must not rot away from the repository.

`tools/check_wiki.py` carries the contract the two-language wiki was delivered
under: paired files, a fixed navigation line, mirrored heading structure, legal
Mermaid blocks covering the six diagram kinds the chapters promise, a closing
"what this chapter does not establish" section on every content page, and prose
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
    """The delivered wiki must satisfy every rule at once, with nothing filtered out.

    The synthetic cases below prove the guard reports drift; this one proves the pages
    themselves are finished. While a chapter's closing section is still being written
    this is the test that goes red, which is the point.
    """
    assert verify.check_wiki(WIKI, ROOT)['problems'] == []


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


def test_a_content_page_that_loses_its_unverified_section_is_reported(wiki_copy):
    page = wiki_copy / 'zh_cn' / '1-overview.md'
    lines = page.read_text(encoding='utf-8').split('\n')
    kept = [line for line in lines if not verify.unverified_section(line)]
    assert len(kept) < len(lines), 'the fixture page no longer closes with such a section'
    page.write_text('\n'.join(kept), encoding='utf-8')
    problems = verify.check_wiki(wiki_copy)['problems']
    assert any(problem.startswith('[UNVERIFIED]') and '1-overview.md' in problem
               for problem in problems)


def test_the_unverified_marker_must_be_a_heading_not_a_sentence(tmp_path):
    wiki = tmp_path / 'wiki'
    (wiki / 'zh_cn').mkdir(parents=True)
    (wiki / 'en_us').mkdir(parents=True)
    (wiki / 'en_us' / '1-overview.md').write_text('# Overview\n', encoding='utf-8')
    page = wiki / 'zh_cn' / '1-overview.md'

    page.write_text('# 概览\n\n本页有一处未验收的断言。\n', encoding='utf-8')
    problems = verify.check_wiki(wiki, ROOT)['problems']
    assert any(problem.startswith('[UNVERIFIED]') and 'zh_cn/1-overview.md' in problem
               for problem in problems), 'a sentence is not the section'

    page.write_text('# 概览\n\n本页有一处未验收的断言。\n\n## 未验收 / 待核实\n', encoding='utf-8')
    problems = verify.check_wiki(wiki, ROOT)['problems']
    assert not any(problem.startswith('[UNVERIFIED]') and 'zh_cn/1-overview.md' in problem
                   for problem in problems)


def test_index_pages_and_the_readme_are_exempt_from_the_unverified_section(tmp_path):
    wiki = tmp_path / 'wiki'
    for language, title in (('zh_cn', '索引'), ('en_us', 'Index')):
        directory = wiki / language
        directory.mkdir(parents=True)
        (directory / 'index.md').write_text('# %s\n\n- 站点地图\n' % title, encoding='utf-8')
    (wiki / 'README.md').write_text('# Wiki\n\n- 站点地图\n', encoding='utf-8')
    problems = verify.check_wiki(wiki, ROOT)['problems']
    assert not any(problem.startswith('[UNVERIFIED]') for problem in problems)


def test_every_documented_unverified_section_spelling_is_recognised():
    spellings = ['未验收', '待核实', '未覆盖', '存疑', 'Unverified', 'Not covered',
                 'Not verified', 'Open questions', 'Caveats', 'Known gaps']
    for spelling in spellings:
        for level in ('##', '###'):
            assert verify.unverified_section('%s %s' % (level, spelling)), spelling
            assert verify.unverified_section('%s %s / 清单' % (level, spelling)), spelling
    assert not verify.unverified_section('本页讨论若干未验收之处，但不设标题。')
    assert not verify.unverified_section('未验收')
    assert not verify.unverified_section('#### 未验收')
    assert not verify.unverified_section('**未验收**')


# The wording the 17 delivered zh/en pages actually use (lead's dump of 2026-10-12). Hard
# coded on purpose: this is the regression net under the stem table, so re-wording a
# section, or trimming a stem too far, fails here and names the phrasing that broke.
REAL_UNVERIFIED_HEADINGS = [
    ('zh_cn/1-overview.md', '## 本章未覆盖'),
    ('zh_cn/2-architecture.md', '## 本章的未解问题'),
    ('zh_cn/2.2-modules.md', '## 未验收 / 待核实'),
    ('zh_cn/2.3-decisions.md', '## 未验收 / 待核实'),
    ('zh_cn/3-runtime.md', '## 未验收 / 存疑清单（本章）'),
    ('zh_cn/4-business-flows.md', '## 4.8 未验收 / 待核实清单'),
    ('zh_cn/5-state-and-data.md', '### 未验收 / 存疑'),
    ('zh_cn/6-deployment.md', '## 6.5 未验收 / 待核实清单'),
    ('zh_cn/7-quality.md', '## 7.3 已知边界与未验收项'),
    ('en_us/1-overview.md', '## Not covered by this chapter'),
    ('en_us/2-architecture.md', '## Open questions left by this chapter'),
    ('en_us/2.2-modules.md', '## Not verified / open questions'),
    ('en_us/3-runtime.md', '## Not-yet-verified / open items (this chapter)'),
    ('en_us/4-business-flows.md', '## 4.8 Unverified / To Be Confirmed'),
    ('en_us/5-state-and-data.md', '### Unverified / open questions'),
    ('en_us/6-deployment.md', '## 6.5 Unverified / To Confirm'),
    ('en_us/7-quality.md', '## 7.3 Known boundaries and unaccepted items'),
]


@pytest.mark.parametrize('page,heading', REAL_UNVERIFIED_HEADINGS,
                         ids=[row[0] for row in REAL_UNVERIFIED_HEADINGS])
def test_the_headings_the_delivered_wiki_really_uses_are_recognised(page, heading):
    assert verify.unverified_section(heading), '%s: %r is no longer recognised' % (page, heading)
