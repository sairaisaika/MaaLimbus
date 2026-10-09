"""Read-only final payout proof; inputs and task success never imply receipt."""
import hashlib
import re
from pathlib import Path

from .storage import read_json
from .vision import Text, find

PROOFS = {'claim': 'claim_proof', 'confirm': 'confirm_proof',
          'receipt': 'receipt_proof', 'pass': 'pass_receipt_proof'}


def load_frame(path):
    path = Path(path)
    record = read_json(path)
    digest = hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()
    if record.get('image_sha256') != digest or record.get('size') != [1920, 1080]:
        raise ValueError('Receipt frame bytes or layout differ')
    return record, dict(frame=str(path), png_sha256=digest)


def token(record, pattern, band):
    texts = [Text(t['text'], tuple(t['box']), t['score']) for t in record.get('ocr', [])]
    hits = find(texts, pattern, band, record['size'], .9)
    if len(hits) != 1:
        raise ValueError('Receipt caption/control missing or ambiguous')
    return hits[0]


def verify(transaction, home_path, reports):
    scope = transaction.get('scope')
    if (not isinstance(scope,str) or not scope or any(transaction.get(k) is not True for k in
            ('claim_sent', 'confirm_sent', 'receipt_ack_sent', 'pass_ack_sent'))):
        raise ValueError('Complete reward input intent chain missing')
    amount, level = transaction.get('receipt_visible_amount'), transaction.get('pass_level')
    if type(amount) is not int or not 0 < amount <= 999999 or type(level) is not int or level < 0:
        raise ValueError('Actual receipt amounts missing')
    if set(reports) != set(PROOFS):
        raise ValueError('Complete reward input reports missing')
    frames, proof = {}, []
    for action, key in PROOFS.items():
        frame, bound = load_frame(transaction[key])
        report = reports[action]
        entries = report.get('steps')
        if (report.get('run_ledger', {}).get('run') != scope
                or type(report.get('clicks_sent')) is not int or report['clicks_sent'] != 1
                or not isinstance(entries, list) or len(entries) != 1):
            raise ValueError('Reward input report scope/count differs')
        entry = entries[0]
        if (entry.get('label') != 'paid_reward_'+action or entry.get('action') != 'click'
                or entry.get('observation', {}).get('image_sha256') != bound['png_sha256']):
            raise ValueError('Reward input not bound to receipt chain frame')
        x, y, w, h = entry['target']
        px, py = entry['click_point']
        if w <= 0 or h <= 0 or not x <= px < x+w or not y <= py < y+h or not 350 <= entry['delay_ms'] <= 750:
            raise ValueError('Reward touch evidence outside bounds')
        frames[action] = frame
        proof.append(bound)
    offer = transaction.get('offer')
    if (frames['claim'].get('scene') != 'RUN_REWARD_DIALOG'
            or frames['claim'].get('reward_cost') != offer
            or offer not in (dict(currency='enkephalin_modules',cost=6,weekly=1),
                             dict(currency='enkephalin_modules',cost=5,weekly=0))
            or transaction.get('reserved_modules') != offer['cost']):
        raise ValueError('Actual currency/cost/weekly claim evidence differs')
    token(frames['claim'], r'^Claim$', (.62,.72,.71,.79))
    confirm = frames['confirm']
    if offer['weekly'] == 0:
        if confirm.get('scene') != 'RUN_REWARD_CONFIRM':
            raise ValueError('Actual confirmation scene differs')
        token(confirm, r'^Claim the rewards\?$', (.35,.42,.65,.56))
    else:
        if confirm.get('scene') != 'RUN_REWARD_BONUS':
            raise ValueError('Actual bonus confirmation scene differs')
        lines = find([Text(t['text'],tuple(t['box']),t['score']) for t in confirm['ocr']],
                     r'.+', (.32,.44,.68,.53), confirm['size'], .9)
        question = ' '.join(t.text for t in sorted(lines,key=lambda t:(t.box[1],t.box[0])))
        if re.sub(r"['’]", '', question) != 'Spend your Weekly Bonuses, to claim the bonus rewards?':
            raise ValueError('Actual bonus question differs')
    token(confirm, r'^(?:[x×✕]\s*)?Cancel$', (.34,.64,.46,.73))
    token(confirm, r'^Confirm$', (.56,.64,.66,.73))
    for action, caption, band in (
            ('claim',r'^Claim$',(.62,.72,.71,.79)),
            ('confirm',r'^Confirm$',(.56,.64,.66,.73)),
            ('receipt',r'^Confirm$',(.43,.60,.58,.70)),
            ('pass',r'^Confirm$',(.43,.60,.58,.70))):
        control=token(frames[action],caption,band)
        if list(control.box)!=reports[action]['steps'][0]['target']:
            raise ValueError('Reward input target differs from the proven control')
    token(frames['receipt'], r'^Rewards Acquired$', (.39,.30,.61,.39))
    received = token(frames['receipt'], r'^[1-9]\d{0,5}$', (.47,.48,.54,.56))
    token(frames['receipt'], r'^Confirm$', (.43,.60,.58,.70))
    for pattern, band in ((r'^Pass Level Up$',(.40,.30,.61,.39)),
                          (r'^Pass Level$',(.29,.42,.38,.47)),
                          (r'^Battle Pass XP$',(.39,.42,.57,.49))):
        token(frames['pass'], pattern, band)
    actual_level = token(frames['pass'], r'^\d+$', (.29,.45,.38,.57))
    token(frames['pass'], r'^Confirm$', (.43,.60,.58,.70))
    if int(received.text) != amount or int(actual_level.text) != level:
        raise ValueError('Stored receipt numbers differ from actual captions')
    home, bound = load_frame(home_path)
    if home.get('scene') != 'HOME':
        raise ValueError('Independent HOME successor missing')
    for pattern, band in ((r'^Window$',(.60,.86,.69,.96)), (r'^Drive$',(.73,.86,.80,.96)),
                          (r'^Sinners$',(.66,.86,.74,.96)), (r'^Inventory$',(.46,.90,.55,.97))):
        token(home, pattern, band)
    proof.append(bound)
    return dict(scope=scope, payout_received=True, home_return=True,
                actual_amount=amount, actual_pass_level=level, proofs=proof,
                module_balance_delta_verified=False, state_written=False)
