import { useState } from 'react';
import { useAppStore, flushConfig } from '@/stores/appStore';
import { saveConfig } from '@/services/configService';
import { STAR_IMAGES } from '@/utils/teamArtwork';
import type { OptionValue } from '@/types/interface';

const NAMES=['Star of the Beginning','Cumulating Starcloud','Interstellar Travel','Star-shower','Binary Star-shop','Moon Star-shop','Favor of the Nebulae','Starlight Guidance','Chance Comet','Perfected Possibility'];
export function StarCardsEditor({prefix,instanceId='',taskId='',globalScope=false,disabled=false}: {prefix:'mirror_star_task'|'mirror_star_team';instanceId?:string;taskId?:string;globalScope?:boolean;disabled?:boolean}) {
 const store=useAppStore(),zh=store.language.startsWith('zh'),jp=store.language.startsWith('ja');
 const text=(cn:string,en:string,ja:string)=>zh?cn:jp?ja:en;
 const values=globalScope?store.globalOptionValues:store.instances.find(i=>i.id===instanceId)?.selectedTasks.find(t=>t.id===taskId)?.optionValues || {};
 const read=()=>Array.from({length:10},(_,n)=>{const v=values[`${prefix}_${n}`];return v?.type==='select'&&v.caseName==='on';});
 const readBudget=()=>{const v=values[`${prefix}_budget`];return v?.type==='input'?v.values.budget || '0':'0';};
 const [selected,setSelected]=useState(read),[budget,setBudget]=useState(readBudget),[editing,setEditing]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const locked=disabled || busy || store.instances.some(i=>i.isRunning);
 async function save(){
  if(locked || !/^[0-9]{1,7}$/.test(budget) || Number(budget)>1000000)return;
  setBusy(true);setMessage('');
  const previous=useAppStore.getState(),oldInstances=previous.instances,oldGlobals=previous.globalOptionValues;
  const patch:Record<string,OptionValue>={[`${prefix}_budget`]:{type:'input',values:{budget}}};
  selected.forEach((on,n)=>{patch[`${prefix}_${n}`]={type:'select',caseName:on?'on':'off'};});
  try {
   if(globalScope)useAppStore.setState({globalOptionValues:{...oldGlobals,...patch}});
   else useAppStore.setState({instances:oldInstances.map(i=>i.id!==instanceId?i:{...i,selectedTasks:i.selectedTasks.map(t=>t.id!==taskId?t:{...t,optionValues:{...t.optionValues,...patch}})})});
   const snapshot=flushConfig(),state=useAppStore.getState();
   if(!snapshot || !state.projectInterface || !await saveConfig(state.dataPath,snapshot,state.projectInterface.name))throw new Error(text('保存失败','Save failed','保存できませんでした'));
   setEditing(false);setMessage(text('星光卡片与预算已保存；下次任务核对队伍与实际价格后应用。','Star cards and budget saved; the next task checks team and current prices.','星光カードと予算を保存しました。次のタスクで編成と現在価格を確認します。'));
  }catch(e){useAppStore.setState({instances:oldInstances,globalOptionValues:oldGlobals});setMessage(String(e));}finally{setBusy(false);}
 }
 const shown=editing?selected:read();
 return <section className="space-y-3 w-full min-w-0" aria-label={text('配置初始星光','Starting star cards','開始時の星光カード')}>
  <div className="flex items-center justify-between"><strong>{text('配置初始星光','Starting star cards','開始時の星光カード')}</strong><button disabled={locked} onClick={()=>{setSelected(read());setBudget(readBudget());setEditing(true);setMessage('');}} className="rounded border border-border px-3 py-2">{text('编辑卡片','Edit cards','カードを編集')}</button></div>
  <p className="text-xs text-text-secondary">{text('选择基础卡片；费用以本轮游戏画面为准。强化与剩余星光兑换暂不支持。','Base cards only; costs come from the current game page. Enhancements and balance conversion are unsupported.','基本カードのみ。費用は現在のゲーム画面で確認します。強化と残高交換には未対応です。')}</p>
  <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">{NAMES.map((name,n)=><button key={name} type="button" disabled={locked || !editing} aria-label={name} aria-pressed={shown[n]} onClick={()=>setSelected(selected.map((v,i)=>i===n?!v:v))} className={`p-2 rounded-lg border-2 flex flex-col items-center gap-2 min-w-0 ${shown[n]?'border-accent bg-bg-secondary':'border-border bg-bg-primary'}`}><img src={STAR_IMAGES[n]} alt="" className="w-full max-w-48 object-contain rounded"/><span className="text-xs text-center">{n+1}. {name}</span><span className="text-xs">{shown[n]?'☑':'□'} {text('选择','Selected','選択')}</span></button>)}</div>
  <label className="flex gap-2 items-center text-sm">{text('本轮星光消费上限','Starlight spending cap','星光消費上限')}<input aria-label={text('星光预算','Star budget','星光予算')} disabled={locked || !editing} inputMode="numeric" value={editing?budget:readBudget()} onChange={e=>setBudget(e.target.value)} className="w-32 bg-bg-primary border border-border rounded p-2"/></label>
  {editing&&<div className="flex gap-3"><button disabled={locked || !/^[0-9]{1,7}$/.test(budget) || Number(budget)>1000000} onClick={save} className="bg-accent text-white rounded px-3 py-2">{text('保存星光配置','Save star cards','星光設定を保存')}</button><button disabled={busy} onClick={()=>setEditing(false)}>{text('取消','Cancel','キャンセル')}</button></div>}
  {message&&<p role="status" className="text-sm">{message}</p>}
 </section>;
}
