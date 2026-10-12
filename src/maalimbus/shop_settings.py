"""Boss-adjacent shop spending settings: a strict, bounded, pure resolver.

The shop rule is a *setting*, not an execution path and not a learning algorithm.  This
module turns three option fields into one validated decision and writes nothing anywhere:

``shop_policy``        ``saved`` / ``manual`` / ``learned``
``shop_refreshes``     ``saved`` / an integer 0..5   (plain refresh limit per shop visit)
``shop_reserve_coins`` ``saved`` / an integer 0..500 (coins never spent in a shop visit)

Resolving is all that happens here.  It returns the chosen policy with the player's own
refresh limit and reserve floor, fully validated.  An explicit choice is used exactly as
written, in either direction, because that is the player's own setting; ``learned_applied``
is always ``False`` here, because this pure resolver takes no decision of its own.  Anything
that later scores an actual shelf runs outside this module, from hash-bound receipts and
successor evidence the run owner keeps.

What ``learned`` means, and what it does not:

* It may only obey the player's own two hard settings here (``shop_refreshes`` and
  ``shop_reserve_coins``) and the existing gift allow/block list.  This module never
  raises, lowers or rewrites either setting.
* Independent learning must never lower a reserve floor the player set.  Lowering the
  reserve is the player's own explicit act, recorded as a deliberate downgrade.
* With no recorded samples, the rule fallback applies — the settings above, no observed
  adjustment — and nothing here claims a model learned to buy anything.

``saved`` means "keep the choice already stored"; with nothing stored it falls back to the
runtime's own defaults — ``manual`` / ``2`` / ``0`` — so an install that never opened these
settings behaves exactly as it did before they existed.

Values are strict integers: a string of digits, a boolean or a float is a refusal, not a
coercion.  Nothing here is a controller, an input, a capture, a budget write or a ledger
write; ``resolve_shop_settings`` is a pure function of its arguments.
"""

from __future__ import annotations

SETTINGS_VERSION = 1

#: The three option fields, in the order the decision card reports them.
FIELDS = ('shop_policy', 'shop_refreshes', 'shop_reserve_coins')

POLICIES = ('saved', 'manual', 'learned')

#: What the UI offers in its drop-downs.  The resolver accepts any integer inside the cap.
REFRESH_CHOICES = ('saved', 0, 1, 2, 3, 5)
RESERVE_CHOICES = ('saved', 0, 100, 200, 300, 500)

#: Absolute ceilings, and the accepted integer range.  The drop-down choices sit inside it.
REFRESH_CAP = 5
RESERVE_CAP = 500
REFRESH_RANGE = (0, 5)
RESERVE_RANGE = (0, 500)

#: The runtime's own behaviour when no setting was ever stored.  ``saved`` resolves to
#: these, so an untouched install cannot behave differently from the pre-setting build.
RUNTIME_DEFAULTS = {'shop_policy': 'manual', 'shop_refreshes': 2, 'shop_reserve_coins': 0}

#: Names of the settings the out-of-module learned layer is allowed to obey, and never
#: rewrite.  They are documented, not consumed here.
LEARNED_OBEYS = ('shop_refreshes', 'shop_reserve_coins')

REASONS = (
    'policy_saved',
    'policy_manual',
    'policy_learned',
    'refresh_saved',
    'refresh_manual',
    'reserve_saved',
    'reserve_manual',
    'reserve_floor_raised',
    'reserve_floor_lowered_by_player',
    'kept_launch_choice',
    'runtime_default_used',
)


def _refuse(message):
    raise ValueError(message)


def _int_or_saved(value, name, low, high):
    """One option value: ``None``/'saved' mean 'not chosen'; otherwise a strict integer."""
    if value is None or value == 'saved':
        return 'saved'
    if isinstance(value, bool) or not isinstance(value, int):
        _refuse('%s must be the string "saved" or an integer %d..%d (got %r)'
                % (name, low, high, value))
    if not low <= value <= high:
        _refuse('%s must be an integer %d..%d (got %r)' % (name, low, high, value))
    return value


def _policy(value):
    if value is None or value == 'saved':
        return 'saved'
    if not isinstance(value, str):
        _refuse('shop_policy must be one of %s (got %r)' % (POLICIES, value))
    wanted = value.strip().casefold()
    if wanted not in POLICIES:
        _refuse('shop_policy %r is not one of %s' % (value, POLICIES))
    return wanted


def _mapping(value, label):
    if value is None:
        return {}
    if not isinstance(value, dict):
        _refuse('%s must be a mapping of the option fields' % label)
    for key in value:
        if key not in FIELDS:
            _refuse('%s names unknown field %r; the option fields are %s'
                    % (label, key, list(FIELDS)))
    return value


def resolve_shop_settings(saved=None, overrides=None):
    """Resolve the stored shop choice and this launch's overrides into one decision.

    ``saved``     the stored choice (``shop_policy`` / ``shop_refreshes`` /
                  ``shop_reserve_coins``); a missing field, a missing mapping or a
                  ``saved`` value means "nothing stored" and the runtime default applies.
    ``overrides`` this launch's explicit option values; a field left out keeps the saved
                  choice, and mode ``saved`` is exactly that.  An explicit refresh limit or
                  coin reserve is honoured as written, including a reserve *below* the stored
                  one, because that is the player's own decision (``reserve_manual`` plus
                  ``reserve_floor_lowered_by_player``); the independent learned layer, which
                  lives outside this module, may never do that lowering itself.

    Returns a JSON-safe decision card.  It never mutates either argument, it writes no
    state, and it takes no learning decision: ``learned_applied`` is always ``False``.
    """
    saved = _mapping(saved, 'saved')
    overrides = _mapping(overrides, 'overrides')
    reasons = []

    policy = _policy(overrides.get('shop_policy'))
    stored_policy = _policy(saved.get('shop_policy'))
    if policy != 'saved':
        reasons.append('policy_manual' if policy == 'manual' else 'policy_learned')
    elif stored_policy != 'saved':
        # ``saved`` means follow what was stored; the card still reports what that is.
        reasons.append('policy_saved')
        policy = stored_policy
    elif 'shop_policy' in overrides:
        reasons.append('kept_launch_choice')
        policy = RUNTIME_DEFAULTS['shop_policy']
    elif 'shop_policy' in saved:
        reasons.append('policy_saved')
        policy = RUNTIME_DEFAULTS['shop_policy']
    else:
        reasons.append('runtime_default_used')
        policy = RUNTIME_DEFAULTS['shop_policy']

    def resolve_int(name, low, high, prefix):
        if name in overrides and _int_or_saved(overrides[name], name, low, high) != 'saved':
            reasons.append(prefix + '_manual')
            return overrides[name]
        stored = _int_or_saved(saved.get(name), name, low, high)
        if stored != 'saved':
            reasons.append(prefix + '_saved')
            return stored
        reasons.append('runtime_default_used')
        return RUNTIME_DEFAULTS[name]

    refresh = resolve_int('shop_refreshes', *REFRESH_RANGE, 'refresh')

    # A reserve the player chose this launch is used exactly as written, in either
    # direction: lowering it is the player's own call.  What is never lowered is the
    # player's stored floor by the *learned* layer, which lives outside this module and
    # may only read these settings.  ``explicit_reserve`` is never clamped upwards.
    stored_reserve = _int_or_saved(saved.get('shop_reserve_coins'), 'shop_reserve_coins',
                                   *RESERVE_RANGE)
    explicit_reserve = _int_or_saved(overrides.get('shop_reserve_coins'), 'shop_reserve_coins',
                                     *RESERVE_RANGE)
    if explicit_reserve != 'saved':
        reasons.append('reserve_manual')
        if stored_reserve != 'saved' and explicit_reserve > stored_reserve:
            reasons.append('reserve_floor_raised')
        elif stored_reserve != 'saved' and explicit_reserve < stored_reserve:
            # The stored value is replaced, and the card records that it went down so a
            # reader can tell a deliberate downgrade from a default.
            reasons.append('reserve_floor_lowered_by_player')
        reserve = explicit_reserve
    elif stored_reserve != 'saved':
        reasons.append('reserve_saved')
        reserve = stored_reserve
    else:
        reasons.append('runtime_default_used')
        reserve = RUNTIME_DEFAULTS['shop_reserve_coins']

    source = lambda name: ('manual' if name in overrides and overrides[name] not in (None, 'saved')
                           else ('saved' if name in saved and saved[name] not in (None, 'saved')
                                 else 'default'))
    return dict(
        version=SETTINGS_VERSION,
        shop_policy=policy,
        shop_refreshes=refresh,
        shop_reserve_coins=reserve,
        fields=list(FIELDS),
        policy_source=source('shop_policy'),
        refresh_source=source('shop_refreshes'),
        reserve_source=source('shop_reserve_coins'),
        caps=dict(shop_refreshes=REFRESH_CAP, shop_reserve_coins=RESERVE_CAP),
        ranges=dict(shop_refreshes=list(REFRESH_RANGE), shop_reserve_coins=list(RESERVE_RANGE)),
        runtime_defaults=dict(RUNTIME_DEFAULTS),
        learned_obeys=list(LEARNED_OBEYS),
        learned_applied=False,
        reasons=reasons,
        model_trained=False,
        game_controller=False,
        input_sent=False,
        state_written=False,
        limitation=('Settings only. This resolver takes no learning decision: learned mode '
                    'obeys the two hard settings and the existing gift allow/block list, '
                    'falls back to the rule when there are no recorded samples, and never '
                    'claims a trained purchase model.'),
    )


def shop_settings_protocol():
    """The declared contract, so a UI can state it before any setting is stored."""
    return dict(
        version=SETTINGS_VERSION,
        fields={name: list(choices) for name, choices in (
            ('shop_policy', POLICIES), ('shop_refreshes', REFRESH_CHOICES),
            ('shop_reserve_coins', RESERVE_CHOICES))},
        accepts=dict(shop_refreshes='an integer 0..5, or "saved"',
                     shop_reserve_coins='an integer 0..500, or "saved"'),
        runtime_defaults=dict(RUNTIME_DEFAULTS),
        caps=dict(shop_refreshes=REFRESH_CAP, shop_reserve_coins=RESERVE_CAP),
        learned=dict(
            obeys=list(LEARNED_OBEYS),
            never=['raise, lower or rewrite the two hard settings',
                   'lower a coin reserve floor the player set',
                   'edit the gift allow/block list',
                   'claim a trained model', 'spend without limit'],
            player_may=['lower or raise the coin reserve explicitly; that is reported as a '
                        'deliberate downgrade and is the only way the floor goes down'],
            without_samples='the rule fallback: the settings above, no observed adjustment',
            decides_here=False,
            owner='the run owner keeps hash-bound receipts and successor evidence'),
        refuses=['a string of digits, a boolean or a float where an integer is expected',
                 'an integer outside 0..5 (refresh) or 0..500 (reserve)',
                 'an unknown shop_policy mode', 'an unknown field',
                 'a non-mapping saved or overrides argument'],
        not_claimed=['a trained model', 'an optimal purchase rule', 'a game formula',
                     'any state write', 'any learning decision'],
    )


def collect(get_node, saved=None):
    """Read the three inert option nodes and resolve them.  Pure; the nodes are read only.

    The three nodes are independent attach-only carriers, so a case can never replace the
    MirrorLoop or MainTask action parameters it was never meant to touch.
    """
    overrides = {}
    for name, node in (('shop_policy', 'MirrorShopPolicy'),
                       ('shop_refreshes', 'MirrorShopRefreshLimit'),
                       ('shop_reserve_coins', 'MirrorShopCoinReserve')):
        value = get_node(node)['attach'][name]
        if value != 'saved':
            overrides[name] = value
    return resolve_shop_settings(saved, overrides)
