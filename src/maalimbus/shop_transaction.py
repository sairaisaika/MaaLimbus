"""Durable shop intents. No Maa controller, input, or guessed purchase receipt.

Reserve before attempting input. A reservation means the action may have been
sent, so a restart never repeats it. Only a new, hash-bound independent successor
can reconcile it. Shop coins are separate from module/lunacy budgets.
"""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

from .storage import read_json, write_json
from .shop_vision import (currency, offers, refreshes, matching_purchase_question,
                          PRICE_PATTERN, CURRENCY_X, CURRENCY_Y, _inside, _scales)
from .vision import Text


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('Invalid shop ' + label)
    return value


def _key(name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Shop offer needs its complete title')
    return ' '.join(name.split()).casefold()


def _frame(path):
    path = Path(path).resolve()
    record = read_json(path)
    if not isinstance(record, dict) or not isinstance(record.get('ocr'), list):
        raise ValueError('Invalid shop observation')
    size = record.get('size')
    if (not isinstance(size, list) or len(size) != 2
            or any(type(n) is not int or n <= 0 for n in size)):
        raise ValueError('Invalid shop frame size')
    png = path.with_suffix('.png')
    png_hash = hashlib.sha256(png.read_bytes()).hexdigest()
    if png_hash != record.get('image_sha256'):
        raise ValueError('Shop frame PNG hash differs')
    texts = []
    for row in record['ocr']:
        if (not isinstance(row, dict) or not isinstance(row.get('text'), str)
                or type(row.get('score')) not in (int, float)
                or not 0 <= row['score'] <= 1 or not isinstance(row.get('box'), list)
                or len(row['box']) != 4
                or any(type(n) is not int for n in row['box'])):
            raise ValueError('Invalid shop OCR record')
        x, y, width, height = row['box']
        if min(x, y) < 0 or min(width, height) <= 0 or x + width > size[0] or y + height > size[1]:
            raise ValueError('Shop OCR box outside image')
        texts.append(Text(row['text'], tuple(row['box']), row['score']))
    proof = dict(path=str(path), json_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                 png_sha256=png_hash)
    return record, texts, size, proof


def _verify(proof):
    if (not isinstance(proof, dict) or not isinstance(proof.get('path'), str)
            or any(not isinstance(proof.get(key), str)
                   or not re.fullmatch(r'[0-9a-f]{64}', proof[key])
                   for key in ('json_sha256', 'png_sha256'))):
        raise ValueError('Invalid retained shop proof; preserve pending')
    record, texts, size, current = _frame(proof['path'])
    if current != proof:
        raise ValueError('Retained shop proof changed; preserve pending')
    return record, texts, size


def _coins(texts, size):
    sx, sy = _scales(size)
    candidates = [t for t in texts if t.score >= .9 and PRICE_PATTERN.fullmatch(t.text)
                  and _inside(t.box, CURRENCY_X, CURRENCY_Y, sx, sy)]
    if len(candidates) != 1:
        raise ValueError('Unique high-confidence shop currency not proven')
    return currency(candidates, size)


def _shelf(texts, size):
    found = offers([t for t in texts if t.score >= .9], size)
    return [dict(name=o.name, price=o.price, click=list(o.click)) for o in found]


def _notice(texts, record):
    """The native ``E.G.O Gift GET!`` notice a shop purchase raises over the shelf.

    The notice's own identity -- its title band and its single Confirm -- is read by
    the shop reader, never by this transaction, and nothing is clicked from here.  A
    scene that is not the notice is refused: the caller only reaches this method
    because the page was named GIFT_GET, so an unread notice must stop the run rather
    than let a later frame pass as one.
    """
    from .shop_skill_vision import read_overlay
    result = read_overlay(texts, record.get('size'), scene=record.get('scene'),
                          require_scene='GIFT_GET')
    if not result['available']:
        raise ValueError('Native E.G.O Gift GET notice not proven')
    if not result['complete'] or not result['target']:
        raise ValueError('Notice Confirm not proven; never click an unread notice')
    return result


class ShopTransaction:
    """One durable store per run; visit IDs must come from proven shop entry.

    ``begin_visit`` keeps completed purchases for the entire run. A second visit
    requires ``close_visit`` with a fresh MAP successor; UNKNOWN never resets a
    refresh limit. All mutation failures preserve previous persisted bytes.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.data = read_json(self.path) if self.path.exists() else None
        if self.data is not None:
            d = self.data
            if (not isinstance(d, dict) or d.get('version') != 1
                    or not isinstance(d.get('scope'), str) or not d['scope']
                    or not isinstance(d.get('visits'), dict)
                    or not isinstance(d.get('bought'), list)
                    or d.get('pending') is not None and not isinstance(d.get('pending'), dict)):
                raise ValueError('Invalid shop transaction; do not overwrite')
            for visit in d['visits'].values():
                if not isinstance(visit, dict) or type(visit.get('refreshes')) is not int or visit['refreshes'] < 0:
                    raise ValueError('Invalid persisted shop visit')
            if d.get('current_visit') not in d['visits']:
                raise ValueError('Invalid persisted current shop visit')
            for bought in d['bought']:
                if not isinstance(bought, dict):
                    raise ValueError('Invalid persisted shop receipt')
                _key(bought.get('name'))
                _integer(bought.get('price'), 'persisted receipt price', 1)
            pending = d.get('pending')
            if pending == {}:
                raise ValueError('Empty persisted shop intent is not a completed action')
            if pending:
                if (pending.get('scope') != d['scope'] or pending.get('visit') != d['current_visit']
                        or pending.get('kind') not in ('purchase', 'refresh')
                        or pending.get('stage') not in ('card_intent', 'confirm_intent',
                                                        'overlay_intent', 'refresh_intent')
                        or not isinstance(pending.get('before'), dict)
                        or not isinstance(pending.get('shelf'), list)):
                    raise ValueError('Invalid persisted shop intent')
                _integer(pending.get('price'), 'persisted price', 1)
                _integer(pending.get('coins'), 'persisted coins')
                if pending['kind'] == 'purchase':
                    _key(pending.get('name'))
                    if pending['stage'] not in ('card_intent', 'confirm_intent', 'overlay_intent'):
                        raise ValueError('Invalid purchase intent stage')
                    if pending['stage'] == 'confirm_intent' and not isinstance(pending.get('question'), dict):
                        raise ValueError('Purchase Confirm needs its retained question proof')
                    if pending['stage'] == 'overlay_intent':
                        overlay = pending.get('overlay_acknowledgement')
                        if (not isinstance(overlay, dict)
                                or not isinstance(overlay.get('frame'), dict)
                                or not isinstance(overlay.get('before'), dict)
                                or overlay.get('kind') != 'ego_gift_get_notice'
                                or overlay.get('scope') != d['scope']
                                or overlay.get('visit') != d['current_visit']):
                            raise ValueError('Notice acknowledgement needs its retained notice proof')
                elif pending['stage'] != 'refresh_intent':
                    raise ValueError('Invalid refresh intent stage')

    def _save(self, data):
        write_json(self.path, data)
        self.data = data

    def _bound(self, scope, visit):
        if not self.data or self.data['scope'] != scope or self.data.get('current_visit') != visit:
            raise ValueError('Shop intent belongs to another run/visit')
        if self.data['visits'][visit].get('closed'):
            raise ValueError('Shop visit already closed')

    def _ready(self, scope, visit):
        self._bound(scope, visit)
        if self.data['pending']:
            raise ValueError('Unresolved shop intent; never repeat input')

    @property
    def bought_names(self):
        return [entry['name'] for entry in (self.data or {}).get('bought', [])]

    def refreshes_used(self, scope, visit):
        self._bound(scope, visit)
        return self.data['visits'][visit]['refreshes']

    def begin_visit(self, scope, visit, frame_path, learning_context=None):
        if not isinstance(scope, str) or not scope or not isinstance(visit, str) or not visit:
            raise ValueError('Shop requires explicit run scope and visit')
        if self.data and self.data['scope'] != scope:
            raise ValueError('Archive prior shop scope explicitly before starting another')
        record, texts, size, proof = _frame(frame_path)
        if record.get('scene') != 'SHOP' or not _shelf(texts, size):
            raise ValueError('Independent shop shelf required')
        _coins(texts, size)
        if self.data:
            if self.data['pending']:
                raise ValueError('Unresolved shop intent; never reset visit')
            if visit in self.data['visits']:
                self._bound(scope, visit)
                return False  # Idempotent startup keeps limit and exact bytes.
            previous = self.data['visits'][self.data['current_visit']]
            if not previous.get('closed'):
                raise ValueError('A fresh MAP exit is required before a new shop visit')
            if proof['png_sha256'] == previous['entry']['png_sha256']:
                raise ValueError('Replayed shop entry')
        data = copy.deepcopy(self.data) if self.data else dict(
            version=1, scope=scope, visits={}, bought=[], pending=None)
        data['current_visit'] = visit
        data['visits'][visit] = dict(entry=proof, refreshes=0, closed=False,
                                     overlay_acknowledgements=[])
        if learning_context is not None:
            if (not isinstance(learning_context,dict) or set(learning_context)!=
                    {'keywords','wanted','reserve_coins'} or
                    any(not isinstance(learning_context[k],list) or
                        any(not isinstance(x,str) or not x for x in learning_context[k])
                        for k in ('keywords','wanted'))):
                raise ValueError('Invalid captured shop learning context')
            _integer(learning_context['reserve_coins'],'captured reserve')
            data['visits'][visit]['learning_context']=copy.deepcopy(learning_context)
        self._save(data)
        return True

    def _before(self, frame_path):
        record, texts, size, proof = _frame(frame_path)
        if record.get('scene') != 'SHOP':
            raise ValueError('Shop action needs a fresh shelf')
        return texts, size, proof, _coins(texts, size), _shelf(texts, size)

    def reserve_purchase(self, scope, visit, offer, coins, frame_path, reserve_coins=0):
        self._ready(scope, visit)
        name = offer.name if hasattr(offer, 'name') else offer['name']
        price = offer.price if hasattr(offer, 'price') else offer['price']
        _integer(price, 'price', 1)
        _integer(coins, 'currency')
        _integer(reserve_coins, 'reserve')
        if _key(name) in {_key(n) for n in self.bought_names}:
            raise ValueError('Shop title already receipted in this run')
        texts, size, proof, observed_coins, shelf = self._before(frame_path)
        matching = [o for o in shelf if _key(o['name']) == _key(name) and o['price'] == price]
        if len(matching) != 1 or observed_coins != coins or price > coins-reserve_coins:
            raise ValueError('Fresh exact shop title/price/currency not proven')
        data = copy.deepcopy(self.data)
        data['pending'] = dict(kind='purchase', stage='card_intent', scope=scope, visit=visit,
                               name=name, price=price, coins=coins, before=proof,
                               shelf=shelf, click=matching[0]['click'])
        self._save(data)
        return matching[0]['click']

    def reserve_refresh(self, scope, visit, cost, coins, limit, frame_path, kind='regular', reserve_coins=0):
        self._ready(scope, visit)
        _integer(cost, 'refresh cost', 1)
        _integer(coins, 'currency')
        _integer(limit, 'refresh limit')
        _integer(reserve_coins, 'reserve')
        if kind != 'regular':
            raise ValueError('Keyword refresh policy not verified')
        if self.refreshes_used(scope, visit) >= limit:
            raise ValueError('Shop visit refresh limit reached')
        texts, size, proof, observed_coins, shelf = self._before(frame_path)
        refresh = refreshes([t for t in texts if t.score >= .9], size)['regular']
        if refresh.cost != cost or refresh.box is None or observed_coins != coins or cost > coins-reserve_coins:
            raise ValueError('Fresh shop refresh cost/currency not proven')
        data = copy.deepcopy(self.data)
        # Count attempts, including uncertain ones, before input; restart cannot
        # evade the configured cap by crashing between click and reconciliation.
        data['visits'][visit]['refreshes'] += 1
        data['pending'] = dict(kind='refresh', stage='refresh_intent', scope=scope, visit=visit,
                               price=cost, coins=coins, before=proof, shelf=shelf,
                               click=list(refresh.box))
        self._save(data)
        return list(refresh.box)

    def _pending(self, scope, visit, kind, frame_path):
        self._bound(scope, visit)
        pending = self.data['pending']
        if not pending or pending.get('kind') != kind:
            raise ValueError('Matching pending shop action required')
        _verify(pending['before'])
        if pending.get('question'):
            _verify(pending['question'])
        record, texts, size, proof = _frame(frame_path)
        previous = pending.get('question') or pending['before']
        if proof['png_sha256'] == previous['png_sha256']:
            raise ValueError('Shop successor is a stale original frame')
        return pending, record, texts, size, proof

    def reserve_confirm(self, scope, visit, frame_path):
        pending, record, texts, size, proof = self._pending(scope, visit, 'purchase', frame_path)
        if pending['stage'] != 'card_intent':
            raise ValueError('Shop Confirm already reserved; never repeat')
        if record.get('scene') != 'SHOP_PURCHASE':
            raise ValueError('Independent shop purchase question required')
        target = matching_purchase_question(texts, pending['name'], pending['price'], size)
        if target is None:
            raise ValueError('Full matching purchase title/price/question not proven')
        data = copy.deepcopy(self.data)
        data['pending'].update(stage='confirm_intent', question=proof, confirm=target)
        self._save(data)
        return target

    def reserve_overlay_acknowledgement(self, scope, visit, frame_path):
        """Anchor the one input that clears a purchase's own ``E.G.O Gift GET!`` notice.

        A real purchase raises this notice over the shelf, so the shelf that proves the
        coins is behind it.  The notice is not a receipt and this method never records
        one: it re-proves the notice against the retained frame, binds the acknowledgement
        to that frame's own PNG hash and to the pending intent, and only then returns the
        notice's own Confirm box for the caller's planner to click.

        It is deliberately single-use per visit and per intent.  Once reserved, a restart
        can never send the acknowledgement again, and a second different notice cannot
        claim the same slot.  An unread notice raises instead of clicking, so an unknown
        pending action is preserved rather than cleared.
        """
        pending, record, texts, size, proof = self._pending(scope, visit, 'purchase', frame_path)
        if pending['stage'] != 'confirm_intent':
            raise ValueError('The purchase card intent was not confirmed yet')
        if pending.get('overlay_acknowledgement'):
            raise ValueError('Notice acknowledgement already reserved; never repeat')
        notice = _notice(texts, record)
        # A notice that re-states an already retained frame is not a successor: both the
        # shelf the purchase started from and the question that was answered are refused,
        # because neither can be the different page the notice has to be.
        retained = [pending['before']]
        if pending.get('question'):
            retained.append(pending['question'])
        if any(proof['png_sha256'] == kept['png_sha256'] for kept in retained):
            raise ValueError('Notice successor repeats a retained frame')
        previous = pending.get('question') or pending['before']
        acknowledgement = dict(scope=scope, visit=visit, kind='ego_gift_get_notice',
                               title=notice['title'], title_box=notice['title_box'],
                               confirm=notice['confirm'], target=notice['target'],
                               scene=record.get('scene'), before=previous, frame=proof,
                               refused=[], note='the notice proves no purchase; the '
                               'returning shelf still has to prove the coin delta')
        data = copy.deepcopy(self.data)
        data['pending'].update(stage='overlay_intent', overlay_acknowledgement=acknowledgement)
        data['visits'][visit].setdefault('overlay_acknowledgements', []).append(acknowledgement)
        self._save(data)
        return list(notice['target'])

    def reconcile_purchase(self, scope, visit, frame_path):
        pending, record, texts, size, proof = self._pending(scope, visit, 'purchase', frame_path)
        # GET overlays need a separate native receipt parser. Until that parser is
        # supplied, only an independent shelf with exact coin delta AND removed
        # offer is sufficient; a generic GET/caller-provided title proves nothing.
        if record.get('scene') != 'SHOP':
            raise ValueError('Shop purchase receipt/shelf still unknown; preserve pending')
        coins = _coins(texts, size)
        shelf = _shelf(texts, size)
        if coins != pending['coins'] - pending['price'] or not shelf:
            raise ValueError('Exact shop purchase currency delta not proven')
        if any(_key(o['name']) == _key(pending['name']) for o in shelf):
            raise ValueError('Purchased offer disappearance not proven')
        # All other slots must be retained; a sparse OCR read cannot masquerade
        # as the disappearance of the chosen card.
        remaining = sorted((_key(o['name']), o['price']) for o in pending['shelf']
                           if _key(o['name']) != _key(pending['name']))
        actual = sorted((_key(o['name']), o['price']) for o in shelf)
        if actual != remaining:
            raise ValueError('Independent complete successor shelf not proven')
        data = copy.deepcopy(self.data)
        data['bought'].append(dict(name=pending['name'], price=pending['price'],
                                   visit=visit, before=pending['before'],
                                   question=pending.get('question'), successor=proof,
                                   overlay_acknowledgement=pending.get('overlay_acknowledgement')))
        data['pending'] = None
        self._save(data)
        return True

    def reconcile_refresh(self, scope, visit, frame_path):
        pending, record, texts, size, proof = self._pending(scope, visit, 'refresh', frame_path)
        shelf = _shelf(texts, size)
        fingerprint = lambda rows: sorted((_key(o['name']), o['price']) for o in rows)
        if (record.get('scene') != 'SHOP' or _coins(texts, size) != pending['coins'] - pending['price']
                or not shelf or fingerprint(shelf) == fingerprint(pending['shelf'])
                or len(shelf) != len(pending['shelf'])):
            raise ValueError('Fresh refresh currency delta and complete changed shelf not proven')
        data = copy.deepcopy(self.data)
        data['visits'][visit].setdefault('refresh_receipts', []).append(
            dict(before=pending['before'], successor=proof, price=pending['price']))
        data['pending'] = None
        self._save(data)
        return True

    def close_visit(self, scope, visit, frame_path):
        self._ready(scope, visit)
        record, texts, size, proof = _frame(frame_path)
        _verify(self.data['visits'][visit]['entry'])
        if record.get('scene') != 'MAP' or proof['png_sha256'] == self.data['visits'][visit]['entry']['png_sha256']:
            raise ValueError('Fresh independent MAP exit required; UNKNOWN never resets shop')
        # Caller must independently classify MAP via Maa. This transaction never
        # promotes UNKNOWN to MAP or grants a Leave input of its own.
        data = copy.deepcopy(self.data)
        data['visits'][visit].update(closed=True, exit=proof)
        self._save(data)
