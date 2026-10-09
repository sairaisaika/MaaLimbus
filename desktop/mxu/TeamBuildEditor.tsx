import { useState } from 'react';
import { useAppStore, flushConfig } from '@/stores/appStore';
import { saveConfig } from '@/services/configService';
import { SINNERS, toggleSinner, moveSinner, completeOrder } from '@/utils/teamOrder';

export function TeamBuildEditor({ optionKey }: { optionKey: string }) {
  const store = useAppStore();
  const zh = store.language.startsWith('zh'), jp = store.language.startsWith('ja');
  const text = (cn:string,en:string,ja:string) => zh ? cn : jp ? ja : en;
  const read = () => SINNERS.map((fallback,index) => {
    const value = store.globalOptionValues[`${optionKey}_order_${index+1}`];
    return value?.type === 'select' ? value.caseName : fallback;
  });
  const nameKey=`${optionKey}_name`, systemKey=`${optionKey}_systems`;
  const readName=()=> {const v=store.globalOptionValues[nameKey];return v?.type==='input' ? v.values.name || '' : '';};
  const systemDef=store.projectInterface?.option?.[systemKey];
  const cases=systemDef && 'cases' in systemDef ? systemDef.cases : [];
  const readSystem=()=> {const v=store.globalOptionValues[systemKey];return v?.type==='select' ? v.caseName : cases[0]?.name || '';};
  const [draftName,setDraftName]=useState(readName), [draftSystem,setDraftSystem]=useState(readSystem);
  const [draft,setDraft] = useState<string[]>(read);
  const [editing,setEditing] = useState(false), [busy,setBusy] = useState(false);
  const [message,setMessage] = useState('');
  const disabled = busy || store.instances.some(i => i.isRunning);
  async function apply() {
    if (disabled || !completeOrder(draft)) return;
    setBusy(true); setMessage('');
    const previous = {...useAppStore.getState().globalOptionValues};
    try {
      store.setGlobalOptionValue(optionKey, {type:'select',caseName:'edit'});
      const values = {...useAppStore.getState().globalOptionValues};
      values[nameKey]={type:'input',values:{name:draftName}};
      values[systemKey]={type:'select',caseName:draftSystem};
      draft.forEach((name,index) => { values[`${optionKey}_order_${index+1}`] = {type:'select',caseName:name}; });
      useAppStore.setState({globalOptionValues:values});
      const snapshot=flushConfig(), state=useAppStore.getState();
      if (!snapshot || !state.projectInterface || !await saveConfig(state.dataPath,snapshot,state.projectInterface.name))
        throw new Error(text('保存失败，请重试','Save failed. Try again.','保存できませんでした。再試行してください。'));
      setEditing(false); setMessage(text('顺序已保存，下次镜牢任务应用。','Order saved for the next Mirror task.','順序を保存しました。次の鏡ダンジョンタスクで適用します。'));
    } catch(error) { useAppStore.setState({globalOptionValues:previous}); setMessage(String(error)); }
    finally { setBusy(false); }
  }
  const shown=editing ? draft : read();
  return <div className="space-y-3">
    <div className="flex items-center justify-between gap-2">
      <span className="text-sm text-text-secondary">{text('点选罪人排列出战顺序；再点取消。','Click sinners in deployment order; click again to remove.','出撃順に罪人を選択。再クリックで解除。')}</span>
      <button disabled={disabled} onClick={()=>{setDraft(read());setDraftName(readName());setDraftSystem(readSystem());setEditing(true);setMessage('');}} className="px-3 py-2 rounded border border-border text-sm">{text('编辑编队','Edit build','編成を編集')}</button>
    </div>
    <div className="grid grid-cols-3 sm:grid-cols-6 gap-2" aria-label={text('罪人编队','Sinner formation','罪人編成')}>
      {SINNERS.map((name,index) => {const position=shown.indexOf(name);return <button key={name} disabled={disabled || !editing}
        aria-pressed={position>=0} onClick={()=>setDraft(toggleSinner(draft,name))}
        className={`relative min-h-20 rounded-lg border-2 p-2 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${position>=0?'border-accent bg-bg-secondary':'border-border bg-bg-primary opacity-70'}`}>
        <span className="text-xs text-text-secondary">{index+1}</span><span className="block text-sm font-semibold">{name}</span>
        {position>=0 && <span className="absolute top-1 right-1 rounded bg-accent px-1 text-xs text-white">{position+1}</span>}
      </button>;})}
    </div>
    {editing && <><div className="flex flex-wrap gap-1" aria-label={text('当前出战顺序','Deployment order','現在の出撃順')}>
      {draft.map((name,index)=><span key={name} className="rounded border border-border px-2 py-1 text-xs">{index+1}. {name}
        <button disabled={disabled || index===0} aria-label={`Move ${name} earlier`} onClick={()=>setDraft(moveSinner(draft,index,-1))}> ← </button>
        <button disabled={disabled || index===draft.length-1} aria-label={`Move ${name} later`} onClick={()=>setDraft(moveSinner(draft,index,1))}> → </button></span>)}
    </div><div className="flex gap-2 items-center"><span>{draft.length}/12</span>
      <button disabled={disabled} onClick={()=>setDraft([])} className="px-3 py-2 border border-border rounded">{text('清空顺序','Clear order','順序をクリア')}</button>
      <button disabled={disabled || !completeOrder(draft)} onClick={apply} className="px-3 py-2 bg-accent text-white rounded disabled:opacity-40">{text('保存顺序','Save order','順序を保存')}</button>
      <button disabled={busy} onClick={()=>setEditing(false)}>{text('取消','Cancel','キャンセル')}</button>
    </div></>}
    {message && <p role="status" className="text-sm">{message}</p>}
    {editing && <div className="grid grid-cols-2 gap-3">
      <label className="text-sm">{text('编队名称','Build name','編成名')}<input disabled={disabled} maxLength={80} value={draftName} onChange={e=>setDraftName(e.target.value)} className="block w-full bg-bg-primary border border-border rounded p-2" /></label>
      <label className="text-sm">{text('体系','Systems','体系')}<select disabled={disabled} value={draftSystem} onChange={e=>setDraftSystem(e.target.value)} className="block w-full bg-bg-primary border border-border rounded p-2">{cases.map(c=><option key={c.name} value={c.name}>{c.name}</option>)}</select></label>
    </div>}
  </div>;
}
