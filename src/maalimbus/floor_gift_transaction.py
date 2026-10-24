"""Durable floor gift intents. Unknown postconditions never permit another input."""
import hashlib
import json
import os
from pathlib import Path

from .storage import read_json, write_json

#: What this reader writes today.  A ledger without it was written by an older reader,
#: and "older" is the only thing that can explain a field the current rules need but the
#: record does not carry (measured: `selected` empty on a ledger written before D138).
SCHEMA = 2
# D144: fields that describe the ledger itself, not this run's progress.  `prepare`
# builds a fresh record, so anything in this tuple has to be carried across by hand.
CARRIED_FIELDS = ('retired_commit',)

#: The page families that end a floor gift's pick sequence without another pick:
#: the theme-pack shelf and the map both mean this floor's gift step is over.
FINAL_SUCCESSOR_PAGES = ('THEME_PACKS', 'MAP')
#: Every page that can independently prove a floor gift receipt's successor. The
#: settling rule and the retained-evidence recovery path must accept the same set:
#: a proof one of them honours and the other does not is how a cleared notice
#: leaves a receipt that can never be booked.
RECEIPT_SUCCESSOR_PAGES = ('GIFT_GET', 'GIFT_PICK', 'REWARD_CARD') + FINAL_SUCCESSOR_PAGES


def _adopted_title(proof):
    """The card the page already owned, read from its own caption in the retained frame.

    The proof is the picture the commit was judged on.  A card is named by the ``Owned``
    caption printed above it, and the title sits directly under that band -- measured on
    ``packaged-mirror-20261024-161620/frame-0001``: ``Owned`` [1186,218,86,30] with
    ``Melted Eyeball`` [1262,260,184,27] beneath it.  No caption, no card: this returns
    ``None`` so the caller can refuse instead of guessing.
    """
    try:
        record = read_json(Path(proof))
    except Exception:
        return None
    rows = record.get('ocr') or []
    owned = [r for r in rows if str(r.get('text') or '').strip() == 'Owned']
    if len(owned) != 1:
        return None
    box = owned[0]['box']
    below = [r for r in rows
             if str(r.get('text') or '').strip() != 'Owned'
             and box[1] + 10 <= r['box'][1] <= box[1] + 60
             and 0 <= r['box'][0] - box[0] <= 200]
    below.sort(key=lambda r: r['box'][1])
    return str(below[0]['text']).strip() if below else None


class FloorGiftTransaction:
    def __init__(self, path):
        self.path = path
        self.data = read_json(path) if path.exists() else None
        # D141: the reader's generation is a fact about the record, not a guess.
        self.schema = int((self.data or {}).get('schema') or 1) if self.data else SCHEMA
        self._learn_pending_title()

    def _learn_pending_title(self):
        """D142: refresh a pre-D140 record from the proof it kept.

        A ledger written before D140 never recorded the adopted card's name, and `prepare`
        must refuse while a commit is pending, so the refresh belongs where the record is
        loaded.  The proof is the picture the commit was judged on; nothing to read there is
        not a guess to make, so the name stays absent and the receipt stage still refuses.
        """
        d = self.data or {}
        pending = d.get('pending') or {}
        if (d.get('schema') or 1) != 1 or pending.get('kind') != 'commit':
            return
        if pending.get('title') or not pending.get('adopted'):
            return
        title = _adopted_title(pending.get('proof'))
        if not title:
            return
        pending['title'] = title
        pending['title_from'] = 'proof'
        write_json(self.path, d)

    @staticmethod
    def _picks(d):
        """How many of `selected` this run picked itself (an adopted card is not a pick)."""
        return len(d['selected'])-(1 if d.get('adopted') else 0)

    @staticmethod
    def signature(offers):
        value = [o.identity() for o in offers]
        return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

    def prepare(self, scope, offers, count, proof):
        signature = self.signature(offers)
        d = self.data
        if not d or d['scope']!=scope or d['offer']!=signature:
            if d and (d['pending'] or not d.get('completed')):
                raise ValueError('floor_gift_previous_transaction_unresolved')
            if count['chosen']!=0 and not any(getattr(o,'owned',False) for o in offers):
                # A page may arrive with a card the game already selected -- marked
                # Owned -- and that is the baseline, not this run's pick (D136).  A
                # selection with no owned card behind it is still unattributed evidence.
                raise ValueError('floor_gift_selected_without_scoped_evidence')
            history = (d.get('history',[])+[d]) if d else []
            if d: history[-1] = {k:v for k,v in d.items() if k!='history'}
            # `screen_before` is the number of cards the game had already selected when
            # this run first looked.  A three-free page can arrive with one card marked
            # Owned and outlined, so the *screen's* count and the *run's* picks are two
            # different counters (D136): measured 2026-10-24, a fresh ledger with
            # selected=[] met a page showing chosen=1 and stopped the run on a mismatch.
            # A page that arrives with the required cards already selected has no pick
            # to make, but the receipt stage still needs a name to match against the
            # notice.  The card the game marked Owned is the only name the screen gives,
            # so it is recorded as *adopted* rather than chosen (D137/D138): measured
            # 2026-10-24, an adopted selection with selected=[] made the receipt stage
            # refuse with floor_gift_receipt_unknown_repeated_or_pending.
            owned_titles=[o.title for o in offers if getattr(o,'owned',False)]
            adopted_titles=owned_titles[:count['required']] if count['chosen']>=count['required'] else []
            # D144: a field that describes the ledger's own situation -- its generation
            # and the commit a previous run was owed -- is not run state and must not be
            # erased by the record this run builds.  Measured 2026-10-24: the retirement
            # marker was written at load, then a prepare on the same page dropped it and
            # the receipt guard saw a fresh ledger.
            retired=(d or {}).get('retired_commit')
            d = dict(schema=SCHEMA,scope=scope,offer=signature,required=count['required'],
                     screen_before=count['chosen'],selected=list(adopted_titles),
                     adopted=bool(adopted_titles),picked_owned={},pending=None,commit_sent=False,receipts=[],
                     retired_commit=retired,
                     substitutions=[],completed=False,proofs=[str(proof)],history=history)
            self.data=d
            write_json(self.path,d)
        if d.get('screen_before') is None and not d['selected'] and not d['pending'] and not d['commit_sent']:
            # A ledger written before this counter existed cannot say what the page
            # looked like; a page with no picks by this run is exactly where a baseline
            # can still be learned, so learn it instead of ending the run (D136, the
            # same shape as D134's refresh).
            d['screen_before']=count['chosen']
            write_json(self.path,d)
        if (d['pending'] or d['commit_sent'] or d['completed'] or count['required']!=d['required']
                or count['chosen']-int(d.get('screen_before') or 0)!=self._picks(d)):
            raise ValueError('floor_gift_pending_commit_or_counter_mismatch')
        return d

    def intent(self, title, count, proof, *, owned=False):
        d=self.data
        if (d['pending'] or d['commit_sent'] or title in d['selected']
                or count['chosen']-int(d.get('screen_before') or 0)!=self._picks(d)):
            raise ValueError('floor_gift_selection_would_repeat')
        d['pending']=dict(kind='pick',title=title,before=count['chosen'],proof=str(proof))
        # A gift the run already owns cannot be granted twice: the game answers such a
        # pick with a different gift under its own name (live: 'Portable Battery Socket'
        # came back as 'Faint Vestige').  The flag is kept so the receipt stage can label
        # the substitution instead of refusing a notice the game really printed.
        d.setdefault('picked_owned',{})[title]=bool(owned)
        path=Path(proof)
        if path.is_file() and path.with_suffix('.png').is_file():
            d['pending'].update(before_json_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                before_png_sha256=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest())
        write_json(self.path,d)

    def recover_pick(self, scope, offers, count, proof, catalog):
        """Resolve one sent pick from its retained original and fresh exact counter.

        Does not replay input. Missing/changed original or unknown successor keeps
        pending intact. Older intents still require original PNG metadata and the
        complete offer signature, never a saved default or a guessed selection.
        """
        from .floor_gifts import observe
        from .vision import Text
        d=self.data;pending=(d or {}).get('pending')
        if not pending or pending['kind']!='pick' or d['scope']!=scope:
            raise ValueError('floor_gift_recovery_scope_or_pick_not_proven')
        before=Path(pending['proof']); original=read_json(before)
        old_hash=hashlib.sha256(before.with_suffix('.png').read_bytes()).hexdigest()
        if old_hash!=original.get('image_sha256') or original.get('scene')!='GIFT_PICK':
            raise ValueError('floor_gift_original_pick_png_not_proven')
        if pending.get('before_png_sha256',old_hash)!=old_hash or pending.get(
                'before_json_sha256',hashlib.sha256(before.read_bytes()).hexdigest())!=hashlib.sha256(before.read_bytes()).hexdigest():
            raise ValueError('floor_gift_original_pick_proof_changed')
        old_offers,old_count=observe([Text(r['text'],tuple(r['box']),r['score']) for r in original['ocr']],original['size'],catalog)
        fresh=read_json(Path(proof)); fresh_hash=hashlib.sha256(Path(proof).with_suffix('.png').read_bytes()).hexdigest()
        if fresh_hash!=fresh.get('image_sha256') or fresh_hash==old_hash or fresh.get('scene')!='GIFT_PICK':
            raise ValueError('floor_gift_fresh_pick_successor_not_proven')
        # The count may carry a third key naming which evidence it used (`evidence:
        # owned_caption`, D133); this check is about the two numbers, so it compares
        # those and not the whole dict.
        if (self.signature(old_offers)!=d['offer']
                or old_count.get('required')!=d['required']
                or pending['title'] not in [o.title for o in old_offers if not o.unpriced]):
            raise ValueError('floor_gift_original_pick_offer_not_proven')
        # The ledger can be older than this reader: `before` was written by whichever
        # build reserved the pick, and a reader that can now see the `Owned` caption
        # (D133) reads one more selected card on the very same retained frame.  The
        # offers and the title are what prove the pick; when they agree and only the
        # count moved, the count is refreshed instead of the run being stopped
        # (measured 2026-10-24: stored before=0, re-read chosen=1 on
        # packaged-mirror-20261024-144625/frame-0010).
        if old_count.get('chosen')!=pending['before']:
            pending['before']=old_count.get('chosen')
            d['pending']=pending
            d.setdefault('history',[]).append({'event':'ledger_before_count_refreshed',
                                              'scope':scope,'now':pending['before']})
            write_json(self.path,d)
        if (count.get('chosen'),count.get('required'))==(pending['before'],d['required']):
            # The reservation is still on the books but the screen did not move: the
            # pick never landed.  Release it and let the loop plan again -- a
            # reservation that cannot be observed must not end the run (D135).  Measured
            # 2026-10-24 (`packaged-mirror-20261024-160525`): 0 clicks, one read, the
            # same one selected card on the frame.
            d['pending']=None
            d.setdefault('history',[]).append({'event':'ledger_pick_did_not_land','scope':scope})
            write_json(self.path,d)
            return False
        self.observe_pick(offers,count,proof)
        return True

    def observe_pick(self, offers, count, proof):
        d=self.data; p=d['pending']
        if (not p or p['kind']!='pick' or self.signature(offers)!=d['offer']
                or (count.get('chosen'),count.get('required'))!=(p['before']+1,d['required'])):
            raise ValueError('floor_gift_selection_postcondition_not_proven')
        d['selected'].append(p['title']);d['pending']=None
        d['proofs'].append(str(proof));write_json(self.path,d)

    # The screen a taken pick lands on.  Measured 2026-10-24 over every archived
    # `select_takes_the_picked_floor_gifts` click that had a later read: 13 of 13 left
    # GIFT_PICK, and the successor was GIFT_GET (the received-gift screen).  So "one more
    # selected card on the same page" was never the normal evidence; the normal evidence
    # is that the page carried the pick away.
    POST_PICK_PAGES = ('GIFT_GET',)

    def observe_pick_left(self, page, proof):
        """A pick whose screen changed: the successor page is the receipt (D135)."""
        d=self.data; p=d['pending']
        if not p or p['kind']!='pick' or page not in self.POST_PICK_PAGES:
            raise ValueError('floor_gift_selection_postcondition_not_proven')
        d['selected'].append(p['title']);d['pending']=None
        d['proofs'].append(str(proof));write_json(self.path,d)

    def commit(self, proof):
        d=self.data
        adopted = bool(d.get('adopted')) or (not d['selected']
                                            and int(d.get('screen_before') or 0) >= d['required'])
        if d['pending'] or d['commit_sent'] or (len(d['selected'])!=d['required'] and not adopted):
            raise ValueError('floor_gift_commit_not_ready')
        # A page that arrived with enough cards already selected needs no pick at all:
        # the requirement is satisfied by the screen, and the only remaining input is
        # Select.  Measured 2026-10-24 (`packaged-mirror-20261024-161442`): the ledger
        # had screen_before 1, selected [], and commit refused with p:False c:False
        # sel:0 req:1 (D137).
        d['commit_sent']=True
        d['pending']=dict(kind='commit',proof=str(proof),adopted=bool(adopted))
        if adopted:
            # The adopted title travels with the commit so a receipt can be attributed
            # even when the ledger was written before `selected` learned about adoption
            # (D138 landed 2026-10-24; ledgers written before it carry selected []).
            d['pending']['title']=d['selected'][0] if d['selected'] else None
        write_json(self.path,d)

    def refuse_owned(self, offers, count, proof):
        d=self.data
        if (d['pending'] or d['commit_sent'] or d['selected'] or d['completed']
            or count!={'chosen':0,'required':1} or self.signature(offers)!=d['offer']
            or len(offers)!=1 or not offers[0].owned
            or offers[0].selection_source!='single_free_select_button'):
            raise ValueError('floor_gift_owned_refusal_not_proven')
        d['pending']=dict(kind='refuse_owned',title=offers[0].title,proof=str(proof))
        write_json(self.path,d)

    def observe_refusal(self, page, proof, *, map_floor=None, next_reward_offer=None):
        d=self.data;p=d['pending']
        if not p or p['kind']!='refuse_owned':raise ValueError('floor_gift_refusal_intent_missing')
        known_map=page=='MAP' and map_floor in range(1,6)
        known_reward=(page=='REWARD_CARD' and next_reward_offer
            and next_reward_offer.get('count')=={'chosen':0,'required':1}
            and next_reward_offer.get('title')=='Select Encounter Reward Card')
        if not (known_map or known_reward):raise ValueError('floor_gift_refusal_successor_not_proven')
        d['refusal']=dict(title=p['title'],before=p['proof'],successor=str(proof))
        d['completed']=True;d['pending']=None
        write_json(self.path,d)

    def refusal_confirm_intent(self, scope, proof):
        d=self.data;p=d.get('pending')
        if d['scope']!=scope or not p or p['kind']!='refuse_owned' or p.get('confirm_sent'):
            raise ValueError('floor_gift_refusal_confirm_would_repeat')
        p.update(confirm_sent=True,confirm_proof=str(proof));write_json(self.path,d)


    def notice_matches_a_pick(self, title):
        """Whether a printed GIFT_GET notice can answer one of this run's unclaimed picks.

        A notice naming a gift the run picked is a receipt. A notice naming some other
        E.G.O Gift is still the device's own answer to the press that was just submitted:
        live run ``pi-20261014-072228`` pressed ``Select 2/2`` for 'Prejudice' and
        'Uncapped Defibrilator' and the notice page printed 'Dark Vestige', a name from
        neither the pick page nor the selection, so the run keeps going and the receipt
        stage labels what was printed instead of claiming it. A notice with no printed
        name, or with no unclaimed pick left to answer, is never accepted.
        """
        d=self.data or {}
        if not title:return False
        seen=[r['title'] for r in d.get('receipts',[])]
        return bool([n for n in d.get('selected',[]) if n not in seen])

    def retire_from_another_run(self, run_directory, reason='a_previous_run_left_it_open'):
        """D143: a pending commit whose proof belongs to another run can never be seen.

        The gift ledger is keyed by the scope of the *game* run, so a process that
        resumed the same exploration inherits the previous process's pending commit.
        Its receipt was printed to that process, not this one: measured on
        `evidence/runtime/packaged-mirror-20261024-163315`, which started on GIFT_GET
        with `pending {kind: commit, adopted: True, title: 'Melted Eyeball'}` and could
        never book it.  The proof the commit was judged on sits in the producing run's
        own directory, so the directory -- not a clock -- is the evidence.  A pending
        whose proof cannot be placed is kept: an unreadable path is not proof of
        another run.
        """
        d = self.data or {}
        pending = d.get('pending')
        if not isinstance(pending, dict) or not pending:
            return None
        proof = str(pending.get('proof') or '')
        if not proof:
            return None
        try:
            here = os.path.dirname(os.path.abspath(proof))
            mine = os.path.abspath(str(run_directory))
        except (OSError, ValueError):
            return None
        if not mine or here == mine:
            return None
        retired = dict(kind=pending.get('kind'), title=pending.get('title'),
                       proof=proof, reason=reason)
        d.setdefault('abandoned', []).append(dict(intent='retire', **retired))
        d['pending'] = None
        # The commit was sent, so its receipt is owed; retiring it says the proof of
        # what was owed is outside this run (D143).  Drawing a receipt here would book
        # a delivery nobody saw, so only the fact is recorded.
        d['retired_commit'] = dict(title=retired.get('title'), proof=proof, reason=reason)
        write_json(self.path, d)
        return retired

    def receipt_intent(self, title, proof, *, on_notice_page=False):
        from .initial_gifts import same_name
        d=self.data;p=d.get('pending')
        expected=[n for n in d['selected'] if same_name(n,title)]
        seen=[r['title'] for r in d['receipts']]
        printed=(p or {}).get('granted')
        if not expected and printed and same_name(printed,title):
            # The notice prints the name the game substituted for the next unclaimed
            # pick; the pick itself is still the one this run chose.
            unclaimed=[n for n in d['selected'] if n not in seen]
            if len(unclaimed)==1:expected=unclaimed
        claimed=(p or {}).get('title')
        if not expected and claimed and title and not seen and (p or {}).get('adopted'):
            expected=[claimed]
        if not expected and (p or {}).get('adopted') and title:
            # An adopted selection was never pressed as a pick: the game had already
            # marked the card Owned, so the first notice after Select is its answer to
            # *that* screen, and there is no substitution to look up beforehand.  The
            # adopted title is the expectation and the printed name is kept beside it
            # (D139).  Measured 2026-10-24: packaged-mirror-20261024-162043 stopped on
            # this exact guard with commit_sent true and selected ['Melted Eyeball'].
            unclaimed=[n for n in d['selected'] if n not in seen]
            if len(unclaimed)==1:expected=unclaimed
        if not expected and on_notice_page and self.notice_matches_a_pick(title):
            # The device answered the submitted selection with a gift under its own
            # name. The next unclaimed pick is the one that press answered; its own
            # printed name is kept beside it as the labelled, auditable observation.
            expected=[n for n in d['selected'] if n not in seen][:1]
        if d.get('retired_commit') and not p:
            # A commit whose receipt belongs to another run was retired at load (D143):
            # this run owes nothing it could observe, so the stage is a no-op, not a stop.
            return
        if not d['commit_sent'] or not p or p['kind']!='commit' or len(expected)!=1 or expected[0] in seen:
            raise ValueError('floor_gift_receipt_unknown_repeated_or_pending')
        d['pending']=dict(kind='receipt',title=expected[0],proof=str(proof))
        if title and not same_name(title,expected[0]):d['pending']['printed']=title
        write_json(self.path,d)

    def observe_receipt(self, page, title, proof, *, next_free_offer=None, next_reward_offer=None):
        from .initial_gifts import same_name
        d=self.data;p=d.get('pending')
        if not p or p['kind']!='receipt':
            if not receipt_owed(self.data):
                # D152: a ledger that owes no receipt has no intent to observe.  Measured
                # 2026-10-24 (`packaged-mirror-20261024-183743`): commit_sent true, no
                # pending, nothing selected -- the stage stopped on a debt the same file
                # already said was not owed (D148).
                return
            raise ValueError('floor_gift_receipt_intent_missing')
        seen=[r['title'] for r in d['receipts']]+[p['title']]
        remaining=[n for n in d['selected'] if n not in seen]
        granted=(title or '').strip() or None
        next_pick=remaining[0] if remaining else None
        next_receipt=(page=='GIFT_GET' and any(same_name(granted,n) for n in remaining))
        # A gift this run already owns cannot be granted twice: the game answers that
        # pick with a different gift printed under its own name (live: the owned
        # 'Portable Battery Socket' came back as 'Faint Vestige').  That notice is the
        # real successor of the pick just confirmed, so it is retained as a labelled
        # observation -- which pick it answers, what the page printed, and whether the
        # pick was a known duplicate -- instead of stopping the run on a name mismatch.
        substituted=(page=='GIFT_GET' and granted is not None and next_pick is not None
            and not same_name(granted,p['title'])
            and not any(same_name(granted,n) for n in remaining))
        free_successor=(not remaining and page=='GIFT_PICK' and next_free_offer
            and next_free_offer.get('count')=={'chosen':0,'required':1}
            and next_free_offer.get('source') in ('single_free_select_button','three_free_select_button')
            and next_free_offer.get('offer'))
        reward_successor=(not remaining and page=='REWARD_CARD' and next_reward_offer
            and next_reward_offer.get('count')=={'chosen':0,'required':1}
            and next_reward_offer.get('title')=='Select Encounter Reward Card')
        final_successor=(not remaining and page in FINAL_SUCCESSOR_PAGES) or bool(free_successor or reward_successor)
        if not (next_receipt or final_successor or substituted):
            raise ValueError('floor_gift_receipt_successor_not_proven')
        label=None
        if substituted:
            label=dict(expected=next_pick,printed=granted,
                       expected_owned=bool((d.get('picked_owned') or {}).get(next_pick)),
                       proof=str(proof))
            d.setdefault('substitutions',[]).append(label)
        record=dict(title=p['title'],receipt=p['proof'],successor=str(proof))
        if p.get('printed'):record['printed']=p['printed']
        d['receipts'].append(record)
        d['completed']=final_successor
        if free_successor:d['next_free_offer']=next_free_offer
        if reward_successor:d['next_reward_offer']=next_reward_offer
        d['pending']=None if final_successor else dict(kind='commit',proof=str(proof))
        if substituted:d['pending']['granted']=granted
        write_json(self.path,d)
        return label


def refusal_confirm_target(record):
    """Exact current question and both controls, independent of background gift."""
    from .vision import Text,find
    records=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
    size=record.get('size') or (1920,1080)
    question=find(records,r'^Continue without choosing an E\.G\.O Gift\?$',(.34,.44,.67,.52),size,.9)
    cancel=find(records,r'^[X×]?\s*Cancel$',(.35,.65,.46,.72),size,.9)
    confirm=find(records,r'^Confirm$',(.55,.65,.66,.72),size,.9)
    if len(question)!=1 or len(cancel)!=1 or len(confirm)!=1:return None
    return list(confirm[0].box)


def retained_notice_name(proof, evidence_root=None):
    """Gift name a retained GIFT_GET proof frame printed, hash-checked.

    Recovery reads what the retained frame actually said; it never re-sends input.
    '' when the frame is present but printed no name.
    """
    from .initial_gifts import receipt_name
    from .vision import Text
    path=Path(proof)
    if evidence_root is not None and not path.resolve().is_relative_to(Path(evidence_root).resolve()):
        raise ValueError('floor_gift_retained_notice_outside_evidence')
    if not path.is_file():raise ValueError('floor_gift_retained_notice_missing')
    record=read_json(path);png=path.with_suffix('.png')
    if record.get('scene')!='GIFT_GET' or not png.is_file():
        raise ValueError('floor_gift_retained_notice_page_not_proven')
    if hashlib.sha256(png.read_bytes()).hexdigest()!=record.get('image_sha256'):
        raise ValueError('floor_gift_retained_notice_image_changed')
    return receipt_name([Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])],
                        record.get('size') or (1920,1080)) or ''


def adopt_legacy_single_pick(transaction, result_path, evidence_root, scope, catalog):
    """Explicit migration of one retained 0→1 input, never automatic recovery.

    Verify the original session's scope, exact target, actual touch, before/after
    frames and hashes. No subsequent input may follow the adopted selection.
    This records an observed selection, never a gift receipt or completed floor.
    """
    from .floor_gifts import observe
    from .vision import Text
    root=Path(evidence_root).resolve(); path=Path(result_path).resolve()
    if transaction.data is not None or not path.is_relative_to(root):
        raise ValueError('floor_gift_legacy_migration_not_allowed')
    result=read_json(path)
    if result.get('run_ledger',{}).get('run')!=scope or not result.get('steps'):
        raise ValueError('floor_gift_legacy_scope_not_proven')
    step=result['steps'][-1]
    if (step.get('page_before')!='GIFT_PICK' or step.get('page_after')!='GIFT_PICK'
        or step.get('reason')!='the_floor_gift_card_must_be_picked_before_select'
        or step.get('clicks_sent')!=1 or not step.get('passed')):
        raise ValueError('floor_gift_legacy_input_not_proven')
    observations=[]; proofs=[]
    for key in ('observation','settled'):
        stored=step[key]; stem=stored['frame']
        if not isinstance(stem,str) or not stem.startswith('frame-') or not stem[6:].isdigit():
            raise ValueError('floor_gift_legacy_frame_invalid')
        frame_path=path.parent/(stem+'.png'); data=read_json(frame_path.with_suffix('.json'))
        digest=hashlib.sha256(frame_path.read_bytes()).hexdigest()
        if digest!=stored['image_sha256'] or digest!=data['image_sha256'] or data['scene']!='GIFT_PICK':
            raise ValueError('floor_gift_legacy_frame_hash_or_scene_mismatch')
        texts=[Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']]
        observations.append(observe(texts,data['size'],catalog));proofs.append(frame_path)
    (before,bcount),(after,acount)=observations
    if bcount!={'chosen':0,'required':acount['required']} or acount['chosen']!=1 or transaction.signature(before)!=transaction.signature(after):
        raise ValueError('floor_gift_legacy_postcondition_not_proven')
    target=tuple(step['plan']['target']); matches=[o for o in before if o.box==target]
    point=step.get('click_point',[])
    if len(matches)!=1 or len(point)!=2 or not (target[0]<=point[0]<=target[0]+target[2] and target[1]<=point[1]<=target[1]+target[3]):
        raise ValueError('floor_gift_legacy_target_not_proven')
    transaction.prepare(scope,before,bcount,proofs[0])
    transaction.intent(matches[0].title,bcount,proofs[0])
    transaction.observe_pick(after,acount,proofs[1])
    transaction.data['legacy_migration']=str(path)
    write_json(transaction.path,transaction.data)
    return transaction.data

def receipt_owed(data):
    """D148: is anything in this ledger still owed a receipt?

    A commit that was sent and then retired (D143) leaves `commit_sent True` with
    `pending None` -- a debt with no name.  Measured 2026-10-24
    (`packaged-mirror-20261024-170840`): the receipt stage stopped a run on that record
    while its screen had no notice to print and nothing pending to match.
    """
    pending = data.get('pending') or {}
    if pending.get('kind') == 'commit':
        return True
    booked = {r.get('title') for r in (data.get('receipts') or [])}
    unbooked = [n for n in (data.get('selected') or []) if n not in booked]
    return bool(unbooked)
