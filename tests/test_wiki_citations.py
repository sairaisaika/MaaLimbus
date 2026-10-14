"""The citation drift measure must be able to fail, not only to print.

`tools/verify_wiki_citations.py` reports rather than enforces how far the wiki's
`path.py:line` citations have moved from the symbol they name: a citation that lands on a
different code line is structurally valid, so neither `tools/check_wiki.py` nor the
citation resolver can see it. These tests pin the judgements it does make -- a named
citation inside the window lands, one outside it is drifted, a citation with no symbol
beside it is not judged, and a path that does not exist is unresolvable -- and then run
the report against the real tree so the repository's own numbers stay well-formed.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('verify_wiki_citations', ROOT / 'tools/verify_wiki_citations.py')
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

SOURCE = '\n'.join(('def planted_symbol():' if number == 30 else 'line %d' % number)
                   for number in range(1, 61)) + '\n'


def _tree(tmp_path, monkeypatch, page_text):
    (tmp_path / 'docs' / 'wiki' / 'en_us').mkdir(parents=True)
    (tmp_path / 'src').mkdir()
    (tmp_path / 'docs' / 'wiki' / 'en_us' / '1-test.md').write_text(page_text, encoding='utf-8')
    (tmp_path / 'src' / 'mod.py').write_text(SOURCE, encoding='utf-8')
    monkeypatch.setattr(verify, 'ROOT', tmp_path)
    monkeypatch.setattr(verify, 'WIKI', tmp_path / 'docs' / 'wiki')


def test_a_citation_near_its_symbol_lands(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, 'the rule is `src/mod.py:32` `planted_symbol`\n')
    totals, rows = verify.check()
    assert (totals['named'], totals['landed'], totals['drifted'], rows) == (1, 1, 0, [])


def test_a_citation_that_moved_away_from_its_symbol_is_reported(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, 'the rule is `src/mod.py:5` `planted_symbol`\n')
    totals, rows = verify.check()
    assert totals['drifted'] == 1
    assert rows[0]['symbol'] == 'planted_symbol'
    assert rows[0]['cited'] == 5
    assert rows[0]['cited_line'] == 'line 5'


def test_prose_without_a_symbol_beside_it_is_not_judged(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, 'the loop lives in `src/mod.py:30` and nowhere else\n')
    totals, rows = verify.check()
    assert (totals['named'], totals['unnamed'], totals['drifted'], rows) == (0, 1, 0, [])


def test_a_path_that_does_not_exist_is_unresolvable(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, 'the rule is `src/gone.py:12` `planted_symbol`\n')
    totals, rows = verify.check()
    assert (totals['unresolvable'], totals['named'], rows) == (1, 0, [])


def test_a_row_naming_many_citations_is_counted_apart(tmp_path, monkeypatch):
    page = '| a | `src/mod.py:30` `planted_symbol` | `src/mod.py:5` `other_symbol` | `src/gone.py:1` `x_y` |\n'
    _tree(tmp_path, monkeypatch, page)
    totals, rows = verify.check()
    assert totals['crowded'] == 3
    assert (totals['named'], totals['drifted'], totals['unresolvable'], rows) == (0, 0, 0, [])


def test_a_symbol_the_cited_file_never_mentions_is_not_called_drift(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, 'the rule is `src/mod.py:5` `absent_symbol`\n')
    totals, rows = verify.check()
    assert (totals['unattributed'], totals['named'], totals['drifted'], rows) == (1, 0, 0, [])


def test_naming_the_module_itself_is_not_called_drift(tmp_path, monkeypatch):
    (tmp_path / 'docs' / 'wiki' / 'en_us').mkdir(parents=True)
    (tmp_path / 'src').mkdir()
    (tmp_path / 'docs' / 'wiki' / 'en_us' / '1-test.md').write_text(
        'wiring lives in `run_wiring` (`src/run_wiring.py:81`)\n', encoding='utf-8')
    (tmp_path / 'src' / 'run_wiring.py').write_text('# run_wiring wires it\n' + 'x\n' * 50, encoding='utf-8')
    monkeypatch.setattr(verify, 'ROOT', tmp_path)
    monkeypatch.setattr(verify, 'WIKI', tmp_path / 'docs' / 'wiki')
    totals, rows = verify.check()
    assert (totals['unattributed'], totals['named'], rows) == (1, 0, [])


def test_apply_repoints_a_citation_onto_its_one_definition(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, 'the rule is `src/mod.py:5` `planted_symbol`\n')
    totals, rows = verify.check()
    assert totals['drifted'] == 1
    applied, skipped = verify.apply_fixes(rows)
    assert (len(applied), skipped) == (1, [])
    page = (tmp_path / 'docs' / 'wiki' / 'en_us' / '1-test.md').read_text(encoding='utf-8')
    assert '`src/mod.py:30`' in page and '`src/mod.py:5`' not in page
    again, rows_again = verify.check()
    assert (again['drifted'], rows_again) == (0, [])


def test_apply_refuses_a_symbol_with_two_definitions(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch, 'the rule is `src/mod.py:200` `planted_symbol`\n')
    (tmp_path / 'src' / 'mod.py').write_text(
        'planted_symbol = 1\n' + 'x\n' * 40 + 'planted_symbol = 2\n', encoding='utf-8')
    totals, rows = verify.check()
    assert totals['drifted'] == 1
    applied, skipped = verify.apply_fixes(rows)
    assert applied == []
    assert skipped and 'definition-like' in skipped[0][1]
    page = (tmp_path / 'docs' / 'wiki' / 'en_us' / '1-test.md').read_text(encoding='utf-8')
    assert '`src/mod.py:200`' in page


def test_the_real_wiki_report_accounts_for_every_citation():
    totals, rows = verify.check()
    assert totals['citations'] > 1000
    assert totals['crowded'] > 0
    assert totals['named'] + totals['unnamed'] + totals['unresolvable'] + totals['crowded'] \
        + totals['unattributed'] == totals['citations']
    assert all(row['verdict'] == 'drifted' and row['symbol'] for row in rows)
