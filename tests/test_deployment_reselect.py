"""An adopted team may re-point the card before anything was clicked.

Live `packaged-mirror-20261024-121001`: the pre-battle page was adopted from the board
(D119), the window planned the adopted team's order, and the transaction stopped the run
with `Deployment order changed during selection` -- although no card had been clicked and
nothing had been reserved.  The order may change while the card is still empty; once a
card is in flight it may not.
"""
import pytest

from maalimbus.deployment_transaction import DeploymentTransaction

TWELVE = list(range(1, 13))
REVERSED = list(reversed(TWELVE))


def _prepared(tmp_path):
    transaction = DeploymentTransaction(tmp_path / 'deployment.json')
    transaction.prepare('scope', TWELVE, (0, len(TWELVE)))
    return transaction


def test_an_empty_card_takes_the_adopted_order(tmp_path):
    transaction = _prepared(tmp_path)
    assert transaction.prepare('scope', REVERSED, (0, len(TWELVE)))['order'] == REVERSED


def test_a_card_already_in_flight_does_not(tmp_path):
    transaction = _prepared(tmp_path)
    transaction.intent('card', (0, len(TWELVE)), 1)
    with pytest.raises(ValueError):
        transaction.prepare('scope', REVERSED, (0, len(TWELVE)))
