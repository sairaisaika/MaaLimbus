"""Durable base-grace purchases; unverified input is never retried."""
from .storage import read_json, write_json


class GraceTransaction:
    def __init__(self,path):
        self.path=path
        self.data=read_json(path) if path.exists() else None

    def begin(self,scope,requested,budget,proof):
        if self.data and self.data.get('pending'):
            raise ValueError('Unverified grace purchase remains pending')
        self.data=dict(scope=scope,requested=list(requested),budget=budget,selected=[],
                       spent=0,available=None,pending=None,proofs=[str(proof)])
        write_json(self.path,self.data)

    def reset_baseline(self,reason):
        """Forget the balance number an earlier session recorded; keep what was bought.

        A resumed run kept refusing every frame as "balance changed outside verified
        purchases" because the only number it had was the dead session's.  Nothing is
        pending, so the next STAR frame's balance is the truth; what was selected and
        spent stays on the record.
        """
        d=self.data
        if not d or d.get('pending') is not None:
            return False
        if d.get('available') is None:
            return False
        d.setdefault('baseline_resets',[]).append(dict(was=d['available'],reason=str(reason)))
        d['available']=None
        write_json(self.path,d)
        return True

    def validate(self,scope,requested,budget,available):
        d=self.data
        if d and d.get('scope')!=scope:
            # A ledger left by another run is not a contradiction: its selections belong
            # to that run.  Measured on evidence/runtime/packaged-mirror-20261025-053423,
            # where a fresh run inherited scope `37fc4d01...` (budget 100, spent 100) and
            # ended on `Grace transaction scope or configuration mismatch` before reading
            # a single frame -- the same family as D98/D134.  Anything actually pending
            # still refuses: a purchase nobody observed is not a configuration problem.
            if d.get('pending'):raise ValueError('Unverified grace purchase remains pending')
            # Only a plan that spent its whole budget is safe to forget: it has nothing
            # left to carry, and the next run's Graces page starts a new plan.  A ledger
            # part-way through (spent < budget, selections still live) still contradicts
            # a new scope -- that is a purchase this run cannot finish.
            spent=d.get('spent') or 0
            budget=d.get('budget') or 0
            if budget<=0 or spent<budget:
                raise ValueError('Grace transaction scope or configuration mismatch')
            d.setdefault('scope_rebinds',[]).append(dict(was=d.get('scope'),
                requested=list(d.get('requested') or ()),budget=d.get('budget'),
                spent=d.get('spent'),reason='a_previous_run_owned_this_ledger'))
            d.update(scope=scope,requested=list(requested),budget=budget,selected=[],
                     spent=0,available=None)
            write_json(self.path,d)
        elif not d:
            raise ValueError('Grace transaction scope or configuration mismatch')
        elif d['requested']!=list(requested) or d['budget']!=budget:
            # Same scope, different plan: the run's wish list (or its budget) changed
            # between sessions.  A *finished* plan is stale configuration and the new
            # plan owns the ledger; anything pending or part-way still refuses, because
            # those are purchases this configuration cannot finish.
            if d.get('pending'):raise ValueError('Unverified grace purchase remains pending')
            spent=d.get('spent') or 0
            budget_old=d.get('budget') or 0
            if budget_old>0 and spent<budget_old:
                raise ValueError('Grace transaction scope or configuration mismatch')
            d.setdefault('scope_rebinds',[]).append(dict(was=d.get('scope'),
                requested=list(d.get('requested') or ()),budget=d.get('budget'),
                spent=spent,reason='the_plan_changed_after_it_was_finished'))
            d.update(requested=list(requested),budget=budget,selected=[],spent=0,available=None)
            write_json(self.path,d)
        if d['pending']:raise ValueError('Unverified grace purchase remains pending')
        if d['available'] is not None and available!=d['available']:
            raise ValueError('Grace balance changed outside verified purchases')
        return d

    def adopt_unspent_entry_settings(self,scope,requested,budget,available,proof):
        """Explicitly repair a zero-budget entry stub before any purchase.

        The caller must bind a current STAR frame and an explicit saved setting.
        This cannot reconfigure a purchase, sealed auto plan or unknown pending.
        """
        d=self.data
        if (not d or d['scope']!=scope or d['budget']!=0 or d['selected'] or
                d['spent']!=0 or d['pending'] is not None or d['available'] is not None or
                'auto_priority' in d or 'entry_settings_adopted' in d):
            raise ValueError('Only an untouched zero-budget entry stub can be adopted')
        if (type(budget) is not int or not 0<=budget<=1000000 or
                type(available) is not int or available<0 or
                not isinstance(requested,list) or len(set(requested))!=len(requested) or
                any(type(n) is not int or not 1<=n<=10 for n in requested)):
            raise ValueError('Explicit entry star choices/budget/current balance required')
        if (not isinstance(proof,dict) or proof.get('page')!='STAR_GRACES' or
                proof.get('scope')!=scope or any(not isinstance(proof.get(k),str) or
                len(proof[k])!=64 for k in ('frame_sha256','configuration_sha256'))):
            raise ValueError('Bound current frame and saved configuration required')
        d['entry_settings_adopted']=dict(previous_requested=list(d['requested']),
            previous_budget=d['budget'],proof=proof)
        d.update(requested=list(requested),budget=budget,available=available)
        write_json(self.path,d)
        return d

    def seal_auto(self,scope,priorities,budget,available,costs,proof):
        """Freeze one affordable plan before input; resumes never re-budget it."""
        d=self.data
        if not d or d['scope']!=scope or d['budget']!=budget or d['pending']:
            raise ValueError('Automatic star scope/budget/pending mismatch')
        if 'auto_priority' in d:
            if d['auto_priority']!=list(priorities):raise ValueError('Automatic star priorities changed')
            if costs is not None and any(costs[n-1]!=d['auto_costs'][str(n)] for n in priorities):
                raise ValueError('Automatic star costs changed')
            return list(d['requested'])
        if costs is None or d['selected'] or d['requested']!=list(priorities):
            raise ValueError('Current auto costs required before selecting stars')
        from .mirror_starlight import affordable
        chosen=affordable(priorities,budget,available,costs)
        d.update(auto_priority=list(priorities),auto_costs={str(n):costs[n-1] for n in priorities},
                 requested=chosen,available=available,auto_plan_proof=str(proof))
        write_json(self.path,d)
        return chosen

    def seal_affordable(self,scope,priorities,budget,limit,costs,proof):
        """Freeze the affordable prefix of a player's own selection before input.

        The Graces page decides how much of that selection one run can pay for: live
        2026-10-12 01:56 the page offered 60 starlight against a configured set that
        costs 100, so the run bought 2,4,5 and then refused the page forever
        (config/user-grace-transaction.json, selected [2,4,5], spent 60). Narrowing to
        the affordable prefix keeps what a full set guaranteed -- Enter is only pressed
        for a plan this transaction froze and proved -- while letting the run leave the
        page. ``limit`` is what the run may still spend in total, so a selection that is
        already part bought narrows onto its own bought cards instead of failing.
        """
        d=self.data
        if not d or d['scope']!=scope or d['budget']!=budget or d['pending']:
            raise ValueError('Narrowed star scope/budget/pending mismatch')
        if 'affordable_plan' in d:
            return list(d['requested'])
        if not d['selected'] or d['requested']==list(priorities):
            from .mirror_starlight import affordable
            chosen=affordable(list(priorities),budget,limit,costs)
            if not chosen:
                raise ValueError('No configured grace fits the current balance')
            if not set(d['selected'])<=set(chosen):
                raise ValueError('An already bought grace is not in the affordable prefix')
        else:
            chosen=list(d['requested'])
        d['affordable_plan']=dict(previous_requested=list(d['requested']),limit=limit,
                                  proof=str(proof))
        d['requested']=list(chosen)
        write_json(self.path,d)
        return list(chosen)

    def intent(self,card,cost,available,proof):
        d=self.data
        if (d['pending'] or card not in d['requested'] or card in d['selected'] or cost<=0
                or cost>available or d['spent']+cost>d['budget']
                or ('auto_costs' in d and d['auto_costs'].get(str(card))!=cost)):
            raise ValueError('Grace purchase is not authorized by this transaction')
        d['pending']=dict(card=card,cost=cost,before=available,proof=str(proof))
        write_json(self.path,d)

    def observe(self,available,proof):
        d=self.data;p=d['pending']
        if not p or available!=p['before']-p['cost']:
            raise ValueError('Grace purchase successor balance not proven')
        d['selected'].append(p['card']);d['spent']+=p['cost'];d['available']=available
        d['proofs'].append(str(proof));d['pending']=None
        write_json(self.path,d)

    def recover(self,scope,requested,budget,available,proof):
        """Book a sent purchase from retained intent + fresh exact balance, no input."""
        from pathlib import Path
        import hashlib
        from .grace_vision import available_starlight, observed_board
        from .vision import Text
        import cv2
        d=self.data
        if (not d or d['scope']!=scope or d['requested']!=list(requested)
                or d['budget']!=budget or not d.get('pending')):
            raise ValueError('Grace recovery scope/configuration/pending mismatch')
        pending=d['pending']
        def frame(path):
            path=Path(path);record=read_json(path);png=path.with_suffix('.png')
            if (record.get('scene')!='STAR_GRACES' or
                    hashlib.sha256(png.read_bytes()).hexdigest()!=record.get('image_sha256')):
                raise ValueError('Grace recovery frame hash/page differs')
            image=cv2.imread(str(png))
            if image is None or [image.shape[1],image.shape[0]]!=record.get('size'):
                raise ValueError('Grace recovery frame dimensions differ')
            texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record['ocr']]
            return record,image,texts
        before,image,texts=frame(pending['proof'])
        board=observed_board(image,texts,[pending['card']])
        if (available_starlight(texts,before['size'])!=pending['before'] or not board
                or board['costs'][pending['card']-1]!=pending['cost']
                or pending['card'] in d['selected'] or d['spent']+pending['cost']>budget):
            raise ValueError('Grace retained purchase intent not independently proven')
        after,_,texts=frame(proof)
        if available_starlight(texts,after['size'])!=available:
            raise ValueError('Grace recovery current balance differs')
        self.observe(available,proof)
        return pending
