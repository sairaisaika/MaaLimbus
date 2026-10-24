"""The packaged assets must say what the repository says (D125).

A fix that lives only in `assets/` changes nothing for the packaged application: the theme
alias of D124 reached the repository and not `dist/MaaLimbus`, so the next live run stopped
again with the same `not proven` after 36.9 s.  The suite compares the files that decide a
reading, so the drift is caught here instead of by a wasted run.
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT / 'assets/resource/base'
DIST = ROOT / 'dist/MaaLimbus/assets/resource/base'
FILES = ('theme-catalog.json', 'pipeline/mirror.json')


@pytest.mark.parametrize('name', FILES)
def test_the_packaged_copy_says_what_the_repository_says(name):
    source, packaged = REPO / name, DIST / name
    if not packaged.exists():
        pytest.skip('this checkout has no packaged application')
    assert source.read_bytes() == packaged.read_bytes(), (
        f'{name} differs between assets/ and dist/MaaLimbus; a reading that depends on it '
        'will behave differently in the packaged run')


def test_the_theme_alias_reaches_the_packaged_catalog():
    packaged = DIST / 'theme-catalog.json'
    if not packaged.exists():
        pytest.skip('this checkout has no packaged application')
    data = json.loads(packaged.read_text(encoding='utf-8'))
    assert data.get('aliases'), 'the packaged catalog lost the D124 alias'
