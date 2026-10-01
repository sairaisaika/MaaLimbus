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

    def __post_init__(self):
        if not 1 <= self.slot <= 20:
            raise ValueError('Saved team slot must be 1..20')
        if len(self.deployment) != len(set(self.deployment)):
            raise ValueError('A sinner cannot be deployed twice')


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
