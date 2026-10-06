"""Rank observed owned identities; Maa alone opens filters and dispatches input."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    sinner: str
    name: str
    level: int | None
    keywords: frozenset[str]
    owned: bool
    selectable: bool
    evidence: str
    box: tuple[int,int,int,int]


def choose_identity(candidates, sinner, keywords, *, inventory_complete=False, descending_level_verified=False):
    if not keywords:raise ValueError('Configure formation keywords before filtering')
    if not inventory_complete and not descending_level_verified:
        raise ValueError('Cannot claim highest level from an unverified partial inventory')
    eligible=[c for c in candidates if c.sinner==sinner and c.owned and c.selectable
        and c.keywords & keywords and c.evidence and type(c.level)is int and 1<=c.level<=100]
    if not eligible:return None
    # Mixed keyword teams use OR membership, then highest level, then coverage.
    # A lower-level identity never wins merely by matching both keywords.
    return min(eligible,key=lambda c:(-c.level,-len(c.keywords & keywords),c.name))
