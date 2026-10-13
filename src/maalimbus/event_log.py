"""The run log a person reads: one line per step, then the reason it stopped.

`events.jsonl` already records everything, but it is written for machines: one JSON
object per event, no shared context, and the verdict of a step is only visible by
joining the `window_intent` line with the observation that follows it. The reported
complaint was that the log does not make clear why the task went red and stopped.

This module renders the same facts the runner already holds -- the step list from
`MirrorRunner.summary()` -- into a fixed-width trace plus a named stop reason and a
sentence saying what that reason means and what to do about it. It never sends
input and never invents a fact it was not given: a step line prints the page, the
verdict and the plan's own reason, and anything it cannot name is printed as it is.
"""
from datetime import datetime

#: the actions a plan can carry, spelled for a person
ACTION_WORDS = {'click': 'click', 'swipe': 'swipe', 'node': 'node', 'record': 'no input'}

#: what a stop reason means, and the next thing to look at
GLOSSARY = {
    'mirror_settings_rejected': '镜牢启动设置未能应用：已保留旧局与事务证据，尚未发送游戏输入。请查看下面的具体错误和本次画面。',
    'floor_gift_unpriced_choices_insufficient': '可完整识别的试炼礼物不足以完成本次选择；未知试炼已排除，未猜测权重。',
    'floor_gift_enemy_trial_not_unique': '礼物卡自身的敌人等级或试炼文本缺失/不唯一；保留 pending，等待识别修复，不重复选择。',
    'window_steps_passed': 'every planned input in this window was proven by the page '
                           'that followed it.',
    'unexpected_successor': 'the input was sent but the page did not change and the '
                            'screen did not repaint, so the game never received it. On an '
                            'emulator this is the signature of a swallowed tap: check the '
                            'run log\'s "input helpers" line first, then the clicked box.',
    'starlight_available_balance_not_proven': 'the Grace page\'s "Available" starlight '
                                              'counter could not be read from the '
                                              'header, so the budget for buying cards is '
                                              'unknown and the planner refuses to spend.',
    'configured_grace_costs_not_proven': 'the Grace page\'s card prices could not be read '
                                         'from the board, so no purchase can be proven; '
                                         'the run re-reads the page a bounded number of '
                                         'times before stopping.',
    'configured_graces_incomplete_within_budget': 'the Graces configured for this team '
                                                  'cost more starlight than the page '
                                                  'offers this run, and the run does not '
                                                  'enter the dungeon with only part of '
                                                  'them bought. The detail line names '
                                                  'the requested cards, the bought ones '
                                                  'and the prices, so the working set is '
                                                  'the configured Graces (team profile '
                                                  'or --graces) against the balance the '
                                                  'page printed.',
    'page_is_observe_only': 'the page has no proven control, so the runner records it '
                            'instead of guessing a tap. Look at the frame named below: a '
                            'page that should have a plan is a missing plan, not a '
                            'missing tap.',
    'unknown_dialog_close_not_anchored': 'a modal covered the page but its own close '
                                         'control could not be read, so nothing was '
                                         'tapped: pressing Confirm could spend Lunacy or '
                                         'accept something the run never chose.',
    'map_click_opened_no_panel': 'the map node was clicked but no node panel appeared; '
                                 'the next candidate node is tried instead.',
    'map_candidates_not_observed_yet': 'the map was observed mid-fade with no readable '
                                       'node, which the next round resolves.',
    'the_same_plan_repeated': 'the same page kept offering the same plan, which is a loop '
                              'rather than progress; the guard stops the window.',
    'claim_family_made_no_progress': 'claiming the finished run walked the reward modals '
                                     'without ever completing, so the claim budget ran '
                                     'out.',
    'initial_gift_counter_or_transaction_missing': 'the initial-gift counter or its '
                                                   'transaction was unavailable, so a '
                                                   'selection cannot be verified.',
    'hard_switch_successor_not_proven': 'the theme pack was set to Hard but the page did '
                                        'not prove the switch.',
    'loop_deadline_exceeded': 'the run used up its own time budget and stopped in a '
                              'bounded way; the steps above are what it managed.',
    'mirror_loop_failed': 'the loop raised instead of stopping: read the traceback in '
                          'events.jsonl (event `mirror_loop_error`).',
}
#: reasons that are per-transaction failures and share one explanation
UNVERIFIED = ('grace purchase', 'initial gift', 'floor gift', 'floor gift refusal',
              'floor gift receipt', 'initial receipt', 'deployment input')


def explain(reason):
    """One sentence for a stop reason, falling back to the reason itself."""
    if not reason:
        return 'no reason was recorded.'
    if reason in GLOSSARY:
        return GLOSSARY[reason]
    if reason.startswith('unverified_') or reason.startswith('floor_gift_') \
            or reason.startswith('initial_gift_'):
        return ('a transaction could not observe the successor it needs to commit, so '
                'nothing was written to the run ledger: ' + reason)
    return reason.replace('_', ' ')


def _point(target):
    if not target:
        return ''
    x, y, width, height = (list(target) + [0, 0, 0, 0])[:4]
    return f'({x + width // 2},{y + height // 2})'


def step_lines(step, index=None):
    """The one or two log lines one recorded step deserves."""
    number = step.get('step') if step.get('step') is not None else index
    page = step.get('page_before') or step.get('scene_before') or '?'
    after = step.get('page_after') or step.get('scene_after')
    plan = step.get('plan') or {}
    action = ACTION_WORDS.get(step.get('action') or plan.get('action'), 'input')
    target = step.get('target') or plan.get('target')
    verdict = 'ok' if step.get('passed') else 'FAILED'
    if step.get('stopped') and not step.get('passed'):
        verdict = 'STOPPED'
    landing = f' -> {after}' if after and after != page else ''
    what = action if action == 'no input' else f'{action} {_point(target)}'.strip()
    head = f'  #{str(number):>3}  {page:<14} {what:<18} {verdict}{landing}'.rstrip()
    lines = [head]
    reason = plan.get('reason') or step.get('reason')
    if reason:
        lines.append(f'       why: {reason}')
    detail = step.get('detail')
    if isinstance(detail, dict) and detail:
        lines.append('       detail: ' + ' '.join(f'{key}={value}'
                                                  for key, value in detail.items()))
    if step.get('click_point'):
        lines.append('       sent: tap ' + ','.join(str(value) for value in step['click_point']))
    if not step.get('passed') and step.get('observation'):
        frame = step.get('frame')
        if frame:
            lines.append(f'       frame: {frame}.png')
    return lines


def report(result, *, title='MaaLimbus mirror run', extra=(), now=None):
    """The whole human-readable log for one finished window."""
    stamp = (now or datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
    steps = list(result.get('steps') or [])
    clicks = result.get('clicks_sent', sum(1 for step in steps if step.get('clicks_sent')))
    lines = [f'{title} — {stamp}',
             f'device: {result.get("controller") or "?"} {result.get("address") or ""}'.rstrip()]
    ledger = result.get('run_ledger') or {}
    if ledger:
        lines.append('ledger: run {run} team {team} rotation {rotation} ({path})'.format(
            run=ledger.get('run'), team=ledger.get('team'), rotation=ledger.get('rotation'),
            path=ledger.get('path')))
    observed = result.get('observation')
    if observed and observed.get('scene'):
        lines.append(f'page: {observed["scene"]} (before any input)')
    lines.extend(str(line) for line in extra if line)
    lines.append('')
    if result.get('flow_steps'):
        lines.append('navigation flow:')
        for step in result['flow_steps']:
            lines.append('  ' + ' '.join(f'{key}={value}' for key, value in step.items()))
        lines.append('')
    if not steps:
        lines.append('  (no step was planned)')
    for index, step in enumerate(steps, start=1):
        lines.extend(step_lines(step, index))
    lines.append('')
    passed = bool(result.get('passed'))
    lines.append('镜牢通关实证: '+('已验证' if result.get('verified_clear') else '尚未验证'))
    reason = result.get('reason')
    if passed:
        lines.append(f'PASSED after {len(steps)} steps ({clicks} clicks sent): {reason}')
    else:
        lines.append(f'STOPPED after {len(steps)} steps ({clicks} clicks sent): {reason}')
    lines.append('  ' + explain(reason))
    if result.get('error'):
        lines.append('  error: ' + str(result['error']).splitlines()[0])
    return '\n'.join(lines) + '\n'
