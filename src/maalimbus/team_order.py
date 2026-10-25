"""Read the deployment order off the page instead of trusting a written-down list.

The team screen fixes where each sinner sits (twelve cards, one per sinner, always
in the same grid) and prints a number on every card: that number *is* the
deployment position.  So the order a run should deploy is a reading of the screen,
not a preference -- the operator's own instruction (m18727): "编队界面基本完全不会变，
你就按照坐标来算就好了，完全不用识别谁是谁，然后能识别出 1-12 的字就够了".

The colour of a badge is not part of an order: a lit (front) card and a dim (back)
card both carry a number, and how many are front changes between encounters, so the
front/back split stays with ``team_vision.card_states`` and the counter.
"""


def order_from_badges(badges, *, count=12):
    """Turn per-card numbers into a deployment order, or say why it cannot.

    ``badges[i]`` is the number printed on card ``i`` (0-based grid position).
    Returns ``(order, reason)`` where ``order`` is the list of 1-based sinner
    positions in deployment order (position 1 first) and ``reason`` names the
    reading that refused it -- never a guess.
    """
    values = list(badges or ())
    if len(values) < count:
        return None, 'badge_count'
    seen = {}
    for slot, badge in enumerate(values[:count]):
        if type(badge) is not int:
            return None, 'badge_missing'
        if not 1 <= badge <= count:
            return None, 'badge_range'
        if badge in seen:
            return None, 'badge_duplicate'
        seen[badge] = slot + 1
    return [seen[number] for number in range(1, count + 1)], 'badges'
