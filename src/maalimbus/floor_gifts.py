"""Bind each observed gift to its own Mounting Trials; no positional default.

English trial grammar is deliberately finite. Updated/unknown text and Japanese
trials refuse until independently validated, rather than inheriting old artwork.
"""
from dataclasses import dataclass, asdict
import re

from .gift_vision import normalized
from .reward_vision import gift_cards, counter_state, GIFT_COUNTER_BAND
from .vision import find


@dataclass(frozen=True)
class Trial:
    level: int
    kind: str
    amount: int

    @property
    def penalty(self):
        # Survival-first heuristic: offense can change clashes; defense/HP mainly
        # lengthen fights. These weights are policy, not game formulas.
        weights = {'offense': 90, 'defense': 10, 'damage_reduction': 3, 'hp': 1}
        return self.level * 30 + self.amount * weights[self.kind]


@dataclass(frozen=True)
class Offer:
    title: str
    canonical: str
    keywords: frozenset
    box: tuple
    trial: Trial
    owned: bool

    def identity(self):
        return dict(title=self.title, canonical=self.canonical,
                    trial=asdict(self.trial), owned=self.owned)


GRAMMAR = ((r'Defense Level\s*\+\s*(\d+)', 'defense'),
           (r'Offense Level\s*\+\s*(\d+)', 'offense'),
           (r'Damage Taken\s*[-−]\s*(\d+)\s*%', 'damage_reduction'),
           (r'Max HP\s*\+\s*(\d+)\s*%', 'hp'))


def observe(records, size, catalog):
    """Require complete one-to-one title/card/trial correspondence and a counter."""
    state = counter_state({'ocr': [dict(text=r.text, box=r.box, score=r.score)
                                   for r in records], 'size': size}, band=GIFT_COUNTER_BAND)
    boxes = gift_cards(records, size)
    if state is None or not 1 <= len(boxes) <= 6:
        raise ValueError('floor_gift_counter_or_cards_not_proven')
    centers = [b[0]+b[2]/2 for b in boxes]
    bounds = [0]+[(a+b)/2 for a,b in zip(centers,centers[1:])]+[size[0]]
    offers = []
    for index, box in enumerate(boxes):
        left, right = bounds[index]/size[0], bounds[index+1]/size[0]
        titles = find(records, r'.+', (left,.245,right,.30), size,.9)
        if len(titles) != 1:
            raise ValueError('floor_gift_title_not_unique')
        title = titles[0].text
        canonical = catalog.text_identity(title)
        if canonical is None:
            raise ValueError('floor_gift_identity_unknown')
        trials = find(records, r'^Mounting Trials$', (left,.57,right,.62),size,.9)
        levels = find(records, r'^\+\s*\d+$', (left,.62,right,.67),size,.85)
        effects = find(records, r'.+', (left,.68,right,.74),size,.9)
        if len(trials)!=1 or len(levels)!=1 or len(effects)!=1:
            raise ValueError('floor_gift_enemy_trial_not_unique')
        level = int(re.findall(r'\d+', levels[0].text)[0])
        matches = [(kind, int(m[1])) for pattern,kind in GRAMMAR
                   if (m:=re.fullmatch(pattern,effects[0].text.strip(),re.I))]
        if len(matches)!=1 or not 0 < level <= 30 or not 0 < matches[0][1] <= 100:
            raise ValueError('floor_gift_enemy_trial_unknown')
        kind, amount = matches[0]
        owned = bool(find(records,r'^Owned$',(left,.13,right,.25),size,.9))
        offers.append(Offer(title,canonical,frozenset(catalog.entries[canonical]['keywords']),
                            tuple(box),Trial(level,kind,amount),owned))
    if len({normalized(o.title) for o in offers})!=len(offers):
        raise ValueError('floor_gift_duplicate_identity')
    if not 0 <= state['chosen'] <= state['required'] <= len(offers):
        raise ValueError('floor_gift_counter_out_of_range')
    return offers, state


def rank(offers, team, selected):
    selected = {normalized(n) for n in selected}
    ranking = []
    for offer in offers:
        if normalized(offer.title) in selected or offer.canonical in team.block:
            continue
        preferred = offer.canonical in team.allow or bool(offer.keywords & team.keywords)
        # Preference offsets a modest trial, but never unconditionally beats a
        # large clash penalty. Non-synergy gifts have no invented roster benefit.
        score = offer.trial.penalty - (40 if preferred else 0) + (60 if offer.owned else 0)
        ranking.append(dict(title=offer.title, canonical=offer.canonical,
                            score=score, trial=asdict(offer.trial),
                            preferred=preferred, owned=offer.owned))
    return sorted(ranking,key=lambda r:(r['score'],r['title']))
