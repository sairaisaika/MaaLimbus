"""Bounded Mirror payout execution under an explicit current-run budget."""
import time
from pathlib import Path

from . import runner
from .paid_reward_action import prepare
from .reward_receipt_audit import verify
from .storage import read_json, write_json, RunStore, ProfileStore

ACTIONS={'RUN_REWARD_DIALOG':'claim','RUN_REWARD_CONFIRM':'confirm',
         'RUN_REWARD_BONUS':'confirm','RUN_REWARD_RECEIPT':'receipt',
         'RUN_REWARD_PASS':'pass'}


def action_for(record):
    # Receipt recognizers differ from page registry names; independent captions
    # are still required by prepare(), never inferred from this dispatch alone.
    from .vision import Text, find
    texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
    size=record.get('size')
    if size==[1920,1080]:
        if len(find(texts,r'^Rewards Acquired$',(.39,.30,.61,.39),size,.9))==1:return 'receipt'
        if len(find(texts,r'^Pass Level Up$',(.40,.30,.61,.39),size,.9))==1:return 'pass'
    return ACTIONS.get(record.get('scene'))


def finish(config,scope,home):
    """Only audited inputs, actual receipts and HOME may advance rotation."""
    path=config/'user-reward-claim-transaction.json'
    tx=read_json(path)
    if tx.get('scope')!=scope or tx.get('completed'):
        raise ValueError('Current reward transaction missing or already complete')
    reports={action:read_json(Path(report)) for action,report in tx.get('task_input_reports',{}).items()}
    proof=verify(tx,home,reports)
    ledger=config/'user-run-ledger.json'
    data=read_json(ledger)
    active=data.get('active') or {}
    if active:
        if active.get('id')!=scope or active.get('floors')!=[1,2,3,4,5] or not active.get('victory'):
            raise ValueError('Completed run scope differs before payout bookkeeping')
        store=RunStore(ledger,ProfileStore(config/'user-team-profiles.json').load())
        # Save the verified HOME before bookkeeping. If the transaction write
        # after rotation fails, recovery checks the exact archived events and
        # finishes this transaction without rotating or clicking again.
        tx['bookkeeping_home']=str(home)
        write_json(path,tx)
        store.record(scope,'native-reward-task-receipt','reward_received',tx['receipt_proof'])
        store.record(scope,'native-reward-task-home','entry_returned',home)
    else:
        import hashlib
        matches=[r for r in data.get('receipts',[]) if r.get('id')==scope]
        if len(matches)!=1 or tx.get('bookkeeping_home')!=str(home):
            raise ValueError('Exact completed bookkeeping scope missing')
        archived=matches[0]
        if archived.get('floors')!=[1,2,3,4,5] or not archived.get('victory') or not archived.get('reward'):
            raise ValueError('Archived payout completion missing')
        for event_id,kind,evidence in (
                ('native-reward-task-receipt','reward_received',tx['receipt_proof']),
                ('native-reward-task-home','entry_returned',home)):
            event=archived.get('events',{}).get(event_id,{})
            if event!=dict(kind=kind,floor=None,evidence=str(Path(evidence).resolve()),
                           sha256=hashlib.sha256(Path(evidence).read_bytes()).hexdigest()):
                raise ValueError('Archived bookkeeping evidence differs')
    tx.update(completed=True,pending=None,reward_received=True,
              receipt_chain=proof['proofs'],home_return_proof=str(home),
              module_balance_delta_verified=False)
    write_json(path,tx)
    return dict(passed=True,reason='mirror_payout_and_home_verified',task='rewards',
                reward_received=True,mail_daily_verified=False,verified_clear=False,proof=proof)


def execute(config,directory,observer,device,journal,*,deadline=None):
    config,directory=Path(config),Path(directory)
    deadline=deadline or time.monotonic()+90
    try:
        ledger=read_json(config/'user-run-ledger.json')
    except (ValueError,OSError) as error:
        return dict(passed=False,reason=str(error),task='rewards',input_sent=False,
                    reward_received=False,mail_daily_verified=False)
    active=ledger.get('active') or {}
    scope=active.get('id')
    if not active:
        txpath=config/'user-reward-claim-transaction.json'
        try:
            tx=read_json(txpath) if txpath.exists() else {}
        except (ValueError,OSError) as error:
            return dict(passed=False,reason=str(error),task='rewards',input_sent=False,
                        reward_received=False,mail_daily_verified=False)
        if tx.get('bookkeeping_home') and not tx.get('completed'):
            try:
                result=finish(config,tx.get('scope'),Path(tx['bookkeeping_home']))
                result['input_sent']=False
                return result
            except (ValueError,KeyError,OSError,RuntimeError) as error:
                return dict(passed=False,reason=str(error),task='rewards',input_sent=False,
                            reward_received=False,mail_daily_verified=False)
    if not scope or not active.get('victory') or active.get('floors')!=[1,2,3,4,5]:
        return dict(passed=False,reason='completed_mirror_run_required',task='rewards',input_sent=False,
                    mail_daily_verified=False,reward_received=False)
    sent=0
    class TrackedDevice:
        def click(self,x,y):
            nonlocal sent
            sent+=1  # Count attempts even if the device or successor read fails.
            return device.click(x,y)
    tracked=TrackedDevice()
    try:
        for _ in range(5):
            record=runner.observe(observer,deadline)
            if record.get('scene')=='HOME':
                result=finish(config,scope,runner.frame_file(directory))
                result['input_sent']=sent>0
                return result
            action=action_for(record)
            if action is None:raise ValueError('Reward page or successor not proven')
            def preflight(current):
                if action_for(current)!=action:raise ValueError('Fresh reward page changed')
                frame=runner.frame_file(directory)
                return prepare(action,read_json(frame),config,scope,str(frame))
            entry=runner.one_shot_click(tracked,observer,[0,0,1,1],label='paid_reward_'+action,
                deadline=deadline,journal=journal,rounds=3,interval=1,preflight=preflight)
            report=directory/('reward-'+action+'-input.json')
            write_json(report,dict(run_ledger=dict(run=scope),clicks_sent=1,steps=[entry]))
            txpath=config/'user-reward-claim-transaction.json'
            tx=read_json(txpath)
            tx.setdefault('task_input_reports',{})[action]=str(report)
            write_json(txpath,tx)
            if not entry['passed']:raise ValueError('Reward successor did not settle')
        raise ValueError('Reward task input bound reached')
    except (ValueError,KeyError,OSError,RuntimeError) as error:
        journal.record('reward_task_stopped',scope=scope,error=str(error),inputs_sent=sent)
        return dict(passed=False,reason=str(error),task='rewards',input_sent=sent>0,
                    reward_received=False,mail_daily_verified=False,verified_clear=False)
