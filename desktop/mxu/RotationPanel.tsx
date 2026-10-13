import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useAppStore } from '@/stores/appStore';

type Rotation = {rotation:number;team:number;mode:string;active:boolean;payout_pending:boolean};
export function RotationPanel() {
 const store=useAppStore(),[status,setStatus]=useState<Rotation|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const [request,setRequest]=useState<{id:string;rotation:number}|null>(null);
 const zh=store.language.startsWith('zh'),jp=store.language.startsWith('ja');
 const text=(cn:string,en:string,ja:string)=>zh?cn:jp?ja:en;
 const running=store.instances.some(i=>i.isRunning);
 async function refresh(){setBusy(true);try{setStatus(await invoke<Rotation>('limbus_rotation_manage'));setMessage('');}catch(e){setMessage(String(e));}finally{setBusy(false);}}
 async function skip(){
  if (!status || busy || running || status.active || status.payout_pending || status.mode!=='rotation') return;
  const pending=request || {id:crypto.randomUUID().replaceAll('-',''),rotation:status.rotation};setRequest(pending);setBusy(true);
  try {
   const result=await invoke<{next_team:number}>('limbus_rotation_manage',{requestId:pending.id,expectedRotation:pending.rotation});
   // Acknowledged action is complete even if the subsequent status refresh fails.
   setRequest(null);setStatus(null);
   const current=await invoke<Rotation>('limbus_rotation_manage');setStatus(current);
   setMessage(text(`已跳过；下次使用 Team${result.next_team}，不记通关或领奖。`,`Skipped; next Team${result.next_team}. No clear or reward recorded.`,`スキップ済み。次は Team${result.next_team}。クリア・報酬として記録しません。`));
  }catch(e){setMessage(String(e));}finally{setBusy(false);}
 }
 return <section className="rounded-xl border border-border p-4 space-y-3">
  <h2 className="text-lg font-semibold">{text('镜牢队伍轮换','Mirror team rotation','鏡ダンジョンの編成ローテーション')}</h2>
  <p>{text('成功领奖并返回后自动换队；弃局保持原队。手动跳过只在无活动局、无未结领奖时可用。','Rotate after verified payout and return; abandonment keeps the team. Manual skip requires no active run or pending payout.','報酬と帰還の確認後に交代。中止では維持。手動スキップは進行中・未精算の報酬がない場合のみ。')}</p>
  {status && <p>{text('下次队伍','Next team','次の編成')}: Team{status.team}</p>}
  <div className="flex gap-2">
   <button disabled={busy || running} onClick={refresh} className="px-3 py-2 border border-border rounded">{text('读取当前轮换','Read rotation','現在の順番を確認')}</button>
   <button disabled={busy || running || !status || status.active || status.payout_pending || status.mode!=='rotation'} onClick={skip} className="px-3 py-2 border border-border rounded">{text('跳过当前队伍','Skip current team','現在の編成をスキップ')}</button>
  </div>
  {request && <button disabled={busy || running} onClick={()=>{setRequest(null);setStatus(null);setMessage(text('已结束本次重试；此操作不回退队伍。请重新读取后再决定。','Retry ended; no rotation is reversed. Read the current team before deciding again.','再試行を終了しました。順番は戻しません。現在の編成を確認してください。'));}}>{text('结束重试（不回退）','End retry without undo','再試行を終了（取り消しなし）')}</button>}
  {message && <p role="status">{message}</p>}
 </section>;
}
