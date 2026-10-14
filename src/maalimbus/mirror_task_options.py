"""Independent native task nodes avoid MXU's shallow action-param replacement."""
from .storage import KEYWORDS


def collect(get_node):
    keyword = get_node('MirrorInitialKeyword')['attach']['keyword']
    search = get_node('MirrorGiftSearch')['attach']['mode']
    bounds = get_node('MirrorRunBounds')['attach']['steps']
    # The run count is a later node than the rest: a pipeline built before it existed
    # simply carries no value, and that reads as "no number named" rather than as a
    # failure to start the window.
    runs = get_node('MirrorRunCount').get('attach', {}).get('run_count', 'saved')
    battle = get_node('MirrorBattleAssignment')['attach']['mode']
    result = {}
    if battle not in ('saved','win_rate','damage','observe'):
        raise ValueError('Unknown battle assignment mode')
    if battle!='saved':result['battle_assignment']=battle
    if keyword != 'saved':
        if keyword not in {k.lower() for k in KEYWORDS}:
            raise ValueError('Unknown initial gift system')
        result['gift_keyword'] = keyword
    # A task preference never grants permission to pay for gift search.
    if search not in ('saved', 'refuse'):
        raise ValueError('Gift search payment is not supported by task settings')
    if search != 'saved':
        result['gift_search'] = search
    if bounds != 'saved':
        if type(bounds) is not int or not 1 <= bounds <= 2000:
            raise ValueError('Mirror window steps must be 1..2000')
        result['steps'] = bounds
    # The number of complete runs the player asks for, which is not the step bound: zero
    # is "no number named" and the window keeps walking until another bound stops it.
    if runs != 'saved':
        if type(runs) is not int or not 0 <= runs <= 50:
            raise ValueError('Mirror run count must be 0..50')
        result['run_count'] = runs
    return result
