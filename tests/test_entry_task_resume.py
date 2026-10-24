"""D73: the packaged entry task can resume a run that is already in progress.

The packaged task had no node for RESUME_DIALOG. Two live runs clicked the mirror card, landed
on that dialog and ended on ``LimbusUnknown``
(``unknown_or_bounded_transition_exhausted``): the task could not resume the run it had just
been asked to continue. The node below is anchored on the live frame's own OCR box.

A third live run (``packaged-mirror-20261023-230250``) showed the same dialog is reachable from
``MirrorEnter`` as well: after leaving a suspended exploration and entering the mirror again the
game answers with the dialog, so every node that can land on it has to lead back to the resume
node -- a reachability the gate below checks per node, not once for the whole task.
"""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE = json.loads((ROOT / 'assets/resource/base/pipeline/mirror.json').read_text(encoding='utf-8'))
#: the live ``RESUME_DIALOG`` frame's OCR rows, in 1920x1080 pixels
#: (evidence/runtime/packaged-mirror-20261023-224524/frame-0026.json)
LIVE_RESUME = [902, 579, 114, 34]
LIVE_HALT = [848, 647, 222, 33]
SIZE = [1920, 1080]


def _roi(name='MirrorResume'):
    return PIPELINE[name]['custom_recognition_param']['roi']


def _inside(box, roi):
    x, y, w, h = box
    width, height = SIZE
    left, top, right, bottom = x / width, y / height, (x + w) / width, (y + h) / height
    return bool(roi[0] <= left and right <= roi[2] and roi[1] <= top and bottom <= roi[3])


def _problems(pipeline, locales):
    """The gate, as a function, so a counter-example can be built from real data."""
    found = []
    node = pipeline.get('MirrorResume')
    if node is None:
        return ['no MirrorResume node']
    if node['custom_recognition_param'].get('scene') != 'RESUME_DIALOG':
        found.append('the node does not read the resume dialog')
    if not node['custom_recognition_param'].get('token'):
        found.append('the node has no token, so it can never own a click box')
    if node.get('action') != 'Click' or node.get('target') is not True:
        found.append('the node does not click the box its recognition found')
    roi = node['custom_recognition_param'].get('roi') or [0, 0, 0, 0]
    for from_node in ('MirrorHard', 'MirrorDrive', 'MirrorEnter'):
        if 'MirrorResume' not in (pipeline.get(from_node) or {}).get('next', []):
            found.append(f'{from_node} lands on the dialog but cannot reach the node')
    if not _inside(LIVE_RESUME, roi):
        found.append('the live resume button is outside the roi the node reads')
    if _inside(LIVE_HALT, roi):
        found.append('the roi also covers Halt Exploration')
    for locale, words in locales.items():
        if not words.get('resume'):
            found.append(f'the {locale} locale has no resume word')
    return found


def _locales():
    return {name: json.loads((ROOT / f'assets/resource/{name}/locale.json').read_text(encoding='utf-8'))
            for name in ('en', 'jp')}


def test_the_packaged_task_satisfies_every_part_of_the_gate():
    assert _problems(PIPELINE, _locales()) == []


def test_the_node_reads_the_page_it_is_for():
    assert PIPELINE['MirrorResume']['custom_recognition_param']['scene'] == 'RESUME_DIALOG'


def test_the_live_resume_button_is_inside_the_roi_and_halt_is_not():
    assert _inside(LIVE_RESUME, _roi())
    assert not _inside(LIVE_HALT, _roi())


def test_the_click_box_comes_from_the_recognition_not_a_coordinate():
    node = PIPELINE['MirrorResume']
    assert node['action'] == 'Click'
    assert node['target'] is True, 'a coordinate target would bypass the recognition'


def test_the_node_falls_to_the_named_unknown_terminal():
    assert PIPELINE['MirrorResume']['on_error'] == ['LimbusUnknown']


def test_every_node_that_lands_on_the_dialog_leads_back_here():
    for name in ('MirrorHard', 'MirrorDrive', 'MirrorEnter'):
        assert 'MirrorResume' in PIPELINE[name]['next'], name


def test_the_counter_example_a_node_without_a_token_is_caught():
    broken = json.loads(json.dumps(PIPELINE))
    broken['MirrorResume']['custom_recognition_param'].pop('token')
    assert 'the node has no token, so it can never own a click box' in _problems(broken, _locales())


def test_the_counter_example_an_roi_over_the_halt_button_is_caught():
    broken = json.loads(json.dumps(PIPELINE))
    broken['MirrorResume']['custom_recognition_param']['roi'] = [.38, .50, .62, .68]
    assert 'the roi also covers Halt Exploration' in _problems(broken, _locales())


def test_the_counter_example_a_missing_locale_word_is_caught():
    locales = _locales()
    locales['en'] = {k: v for k, v in locales['en'].items() if k != 'resume'}
    assert 'the en locale has no resume word' in _problems(PIPELINE, locales)


def test_the_counter_example_a_node_that_cannot_reach_the_resume_node_is_caught():
    """The third live run's shape: enter the mirror again and the dialog is all there is."""
    broken = json.loads(json.dumps(PIPELINE))
    broken['MirrorEnter']['next'] = [n for n in broken['MirrorEnter']['next'] if n != 'MirrorResume']
    assert ('MirrorEnter lands on the dialog but cannot reach the node'
            in _problems(broken, _locales()))
