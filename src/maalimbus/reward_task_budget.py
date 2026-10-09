"""Explicit native rewards-task budget, bound only to a verified active run."""
from pathlib import Path
from .storage import read_json,write_json


def apply(config,selection):
    if selection=='saved':return False
    if type(selection) is not int or selection not in (0,5,6):
        raise ValueError('Unknown rewards-task module budget')
    config=Path(config)
    active=read_json(config/'user-run-ledger.json').get('active') or {}
    scope=active.get('id')
    if (not isinstance(scope,str) or not scope or active.get('floors')!=[1,2,3,4,5]
            or active.get('victory') is not True or active.get('reward') is not False):
        raise ValueError('Budget requires the current verified, unpaid five-floor run')
    path=config/'user-mirror-settings.json'
    policy=read_json(path)
    if not isinstance(policy,dict):raise ValueError('Invalid saved resource policy')
    txpath=config/'user-reward-claim-transaction.json'
    if txpath.exists():
        tx=read_json(txpath)
        if (tx.get('pending') is not None or
                tx.get('scope')==scope and tx.get('claim_sent')):
            raise ValueError('Do not change a budget after a claim intent or unresolved transaction')
        if tx.get('scope')!=scope and tx.get('completed') is not True:
            raise ValueError('Previous reward transaction is incomplete')
    proposed=dict(policy,reward_budget_scope=scope,max_reward_modules=selection,
                  module_budget_pending=selection==0)
    if proposed==policy:return False
    write_json(path,proposed)
    return True
