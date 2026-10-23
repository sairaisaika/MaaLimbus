"""What "being on the map" means, and what the MAP branch must record after a click.

The runner grew 22 inline ``page == 'MAP'`` tests.  They are not the same kind of
test: some ask *is this the map* (a naming question), some decide *did the click
land* (a contract question).  Mixing them is how a page ends up with special-case
code in three files.

This module owns the naming question so the branches stop repeating it, and it
owns the one bookkeeping rule that must fire whenever a MAP click settles onto
the node panel:

* a settled ``NODE_PANEL`` means the click was understood by the game, so a
  pending navigation probe is answered -- even when the party did not move yet.
"""
from __future__ import annotations

MAP_PAGE = 'MAP'
NODE_PANEL_PAGE = 'NODE_PANEL'


def is_map(page: str | None) -> bool:
    """True when the classifier says the frame is the dungeon map."""
    return page == MAP_PAGE


def after_settle(state: dict, page: str, settled_page: str) -> bool:
    """Record what a settled MAP click proved.  Returns True when it changed state."""
    if is_map(page) and settled_page == NODE_PANEL_PAGE:
        if state.get('navigation_probe_pending'):
            state['navigation_probe_pending'] = False
            return True
    return False
