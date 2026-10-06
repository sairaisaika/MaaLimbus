from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class Gift:
    name: str
    keywords: frozenset[str] = frozenset()
    owned: bool = False
    selectable: bool = True
    recognized: bool = True
    tier: int = 1


@dataclass(frozen=True)
class Team:
    slot: int
    keywords: frozenset[str]
    name: str = ''
    allow: frozenset[str] = frozenset()
    block: frozenset[str] = frozenset()
    deployment: tuple[str, ...] = ()
    pack_weights: tuple[tuple[str, int], ...] = ()
    formation_keywords: frozenset[str] = frozenset()
    graces: tuple[str, ...] = ()
    initial_gifts: tuple[int, ...] = ()
    auto_team: bool = False

    def __post_init__(self):
        if not 1 <= self.slot <= 20:
            raise ValueError('Saved team slot must be 1..20')
        if len(self.deployment) != len(set(self.deployment)):
            raise ValueError('A sinner cannot be deployed twice')
        if type(self.auto_team) is not bool:
            raise ValueError('Automatic formation must be explicitly enabled')
        if any(
            not isinstance(g,str) or len(g) not in (1,2,3) or g[:1] not in '0123456789'
            or g[1:] not in ('','+','++') for g in self.graces):
            raise ValueError('Graces use Lix zero-based 0..9 with optional +/++')
        if len({g[0] for g in self.graces})!=len(self.graces):
            raise ValueError('A grace cannot be configured twice')
        if len(set(self.initial_gifts))!=len(self.initial_gifts) or any(
            type(g) is not int or not 1<=g<=10 for g in self.initial_gifts):
            raise ValueError('Initial gift priorities must be unique one-based positions')
        names = set()
        for pair in self.pack_weights:
            if not isinstance(pair,(tuple,list)) or len(pair)!=2:
                raise ValueError('Pack weights must be name/weight pairs')
            name,weight=pair
            if not isinstance(name,str) or not name.strip() or len(name)>100 or name in names:
                raise ValueError('Pack names must be unique nonempty strings')
            if type(weight) is not int or not 0 <= weight <= 100:
                raise ValueError('Pack weight must be integer 0..100; zero blocks selection')
            names.add(name)


def rank_gifts(candidates: Iterable[Gift], team: Team) -> list[dict]:
    """LALC ordering: unowned preferred, unowned other, owned; block wins."""
    ranked = []
    for gift in candidates:
        if not gift.recognized or not gift.selectable or gift.name in team.block:
            continue
        preferred = gift.name in team.allow or bool(gift.keywords & team.keywords)
        group = 2 if gift.owned else (0 if preferred else 1)
        ranked.append({'name': gift.name, 'group': group, 'preferred': preferred,
                       'owned': gift.owned, 'tier': gift.tier,
                       'reason': 'owned' if gift.owned else ('team_synergy' if preferred else 'new_gift')})
    return sorted(ranked, key=lambda x: (x['group'], -x['tier'], x['name']))


@dataclass(frozen=True)
class EnemyBuff:
    name: str
    clash_power: int = 0
    attack_power: int = 0
    hp_percent: int = 0
    damage_percent: int = 0
    known: bool = True
    selectable: bool = True


def rank_enemy_buffs(candidates: Iterable[EnemyBuff], floor: int) -> list[dict]:
    if not 1 <= floor <= 5:
        raise ValueError('Hard dungeon floor must be 1..5')
    # Clash losses have immediate survival cost; HP mostly increases fight length.
    # These are transparent configurable heuristics, not a universal optimum.
    return sorted([
        {'name': b.name, 'penalty': b.clash_power * (100 + floor * 10)
         + b.attack_power * 90 + b.damage_percent * 3 + b.hp_percent,
         'reason': 'minimize_enemy_strength'}
        for b in candidates if b.known and b.selectable
    ], key=lambda x: (x['penalty'], x['name']))


@dataclass(frozen=True)
class ResourceBudget:
    reserve_stamina: int = 0
    max_modules: int = 0
    refill_enabled: bool = False
    max_refills: int = 0
    max_lunacy: int = 0
    reserve_lunacy: int = 0

    def __post_init__(self):
        if min(self.reserve_stamina, self.max_modules, self.max_refills,
               self.max_lunacy, self.reserve_lunacy) < 0:
            raise ValueError('Resource limits must be nonnegative')

    def modules(self, stamina: int | None, already_converted: int = 0) -> int:
        if stamina is None or stamina < 0 or already_converted < 0:
            return 0
        return max(0, min((stamina - self.reserve_stamina) // 20,
                          self.max_modules - already_converted))

    def authorize_refill(self, *, lunacy: int | None, cost: int | None,
                         spent: int, refills: int) -> bool:
        return bool(self.refill_enabled and lunacy is not None and cost is not None
                    and cost > 0 and min(lunacy, spent, refills) >= 0
                    and refills < self.max_refills and spent + cost <= self.max_lunacy
                    and lunacy - cost >= self.reserve_lunacy)


@dataclass
class RunLedger:
    team_slots: tuple[int, ...]
    rotation: int = 0
    cleared_floors: set[int] = field(default_factory=set)
    final_victory: bool = False
    reward_received: bool = False
    entry_returned: bool = False
    completed_runs: int = 0

    def __post_init__(self):
        if not self.team_slots or any(not 1 <= s <= 20 for s in self.team_slots):
            raise ValueError('Configure at least one valid saved team')

    def complete(self) -> bool:
        if self.cleared_floors != {1, 2, 3, 4, 5} or not (
            self.final_victory and self.reward_received and self.entry_returned
        ):
            return False
        self.completed_runs += 1
        self.rotation = (self.rotation + 1) % len(self.team_slots)
        self.cleared_floors.clear()
        self.final_victory = self.reward_received = self.entry_returned = False
        return True
