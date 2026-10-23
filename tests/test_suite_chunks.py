from tools import suite_chunks


def test_a_chunk_without_a_summary_is_not_a_pass():
    """The whole point: truncated output used to look green."""
    assert suite_chunks.parse('...F')['reported'] is False


def test_a_summary_line_is_the_only_evidence():
    seen = suite_chunks.parse('........  [100%]\n42 passed in 7.56s\n')
    assert seen == {'reported': True, 'passed': 42, 'failed': 0}


def test_failures_are_counted_even_when_some_passed():
    seen = suite_chunks.parse('1 failed, 7 passed in 2.10s')
    assert seen['reported'] is True and seen['failed'] == 1 and seen['passed'] == 7


def test_chunks_cover_every_file_once():
    files = [f'tests/t{i}.py' for i in range(7)]
    got = [f for chunk in suite_chunks.chunks(files, 3) for f in chunk]
    assert got == files
