"""Every evidence document is written through one writer (D196)."""
import ast
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / 'src')]

from maalimbus.documents import TEXTUALISED, as_document, write_document


def test_a_cycle_is_textualised_and_named(tmp_path):
    loop = {}
    loop['self'] = loop
    path = write_document(tmp_path / 'frame-0001.json', {'scene': 'MAP', 'cycle': loop, 'fine': 1})
    row = json.loads(path.read_text(encoding='utf-8'))
    assert row['scene'] == 'MAP' and row['fine'] == 1
    assert row[TEXTUALISED] == ['cycle']
    assert row['cycle'].startswith('{')


def test_a_plain_document_is_written_whole(tmp_path):
    path = write_document(tmp_path / 'a.json', {'scene': 'MAP', 'floor': 2})
    row = json.loads(path.read_text(encoding='utf-8'))
    assert TEXTUALISED not in row and row['floor'] == 2


def test_a_set_and_an_object_become_text_without_a_marker(tmp_path):
    class Opaque:
        def __repr__(self):
            return '<opaque>'
    path = write_document(tmp_path / 'b.json', {'set': {1}, 'obj': Opaque(), 'keep': 'yes'})
    row = json.loads(path.read_text(encoding='utf-8'))
    # json.dumps(default=str) already textifies these, so the document is complete and
    # nothing had to be dropped: the marker is reserved for what `default=str` cannot do.
    assert TEXTUALISED not in row
    assert row['keep'] == 'yes' and row['obj'] == '<opaque>' and row['set'] == '{1}'


def test_as_document_leaves_a_clean_dict_alone():
    data = {'a': 1, 'b': [1, 2]}
    assert as_document(data) == data and TEXTUALISED not in as_document(data)


def _bare_writes(path):
    """Write calls whose argument is a bare `json.dumps(...)` (no shared writer)."""
    found = []
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, 'attr', None) or getattr(func, 'id', None)
        if name not in ('write_text', 'write'):
            continue
        for argument in node.args:
            if (isinstance(argument, ast.Call) and isinstance(argument.func, ast.Attribute)
                    and argument.func.attr == 'dumps'):
                found.append('%s:%d' % (path.name, node.lineno))
    return found


def test_the_evidence_writers_use_the_shared_writer():
    # The three writers that carry a loop's own objects: the journal row (D194), the frame
    # document (D195) and the self-run summary (D195).  Generated documents elsewhere are
    # not gated -- they cannot meet a framework object in the first place.
    offenders = []
    for relative in ('agent/recognition.py', 'tools/selfrun_finish.py'):
        offenders += _bare_writes(ROOT / relative)
    assert offenders == []


def test_the_runner_writes_its_frame_documents_through_the_writer():
    source = (ROOT / 'src/maalimbus/runner.py').read_text(encoding='utf-8')
    assert "write_document(directory / (str(name) + '.json'), record)" in source
    assert "write_document(Path(self.directory) / 'agent-stall.json', record)" in source


def test_the_guard_can_fail(tmp_path):
    source = tmp_path / 'offender.py'
    source.write_text('import json\nopen("x","w").write_text(json.dumps({"a":1}))\n', encoding='utf-8')
    assert _bare_writes(source) == ['offender.py:2']
