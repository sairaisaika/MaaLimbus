"""Independent native task nodes avoid MXU's shallow action-param replacement."""
from .storage import KEYWORDS


def collect(get_node):
    keyword = get_node('MirrorInitialKeyword')['attach']['keyword']
    search = get_node('MirrorGiftSearch')['attach']['mode']
    bounds = get_node('MirrorRunBounds')['attach']['steps']
    result = {}
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
    return result
