/**
 * Opt-in local resource diagnostics: host CPU, sampled-process memory, GPU and
 * VRAM, fed by the read-only sampler through the launcher bridge.
 *
 * The panel is off by default and issues no command until the user switches it
 * on. It never touches the game, the emulator or the controller lease: the
 * bridge runs the sampler only, which takes no lock, sends no input and writes
 * no state. Readings stay in this window — nothing is written to a file or
 * uploaded — and the panel renders the sampler's own `null` plus reason instead
 * of substituting a zero.
 */
import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useAppStore } from '@/stores/appStore';
import {
  DEFAULT_POLL_MS, UNKNOWN, diagnosticsRows, gpuStatus, gpuUnsupported, parseSnapshot,
  pollIntervalMs, processMemoryBytes, processRows, shouldSample, formatBytes, formatPercent,
  type Snapshot,
} from '@/utils/resourceDiagnostics';

export function ResourceDiagnosticsPanel() {
 const store=useAppStore();
 const [enabled,setEnabled]=useState(false);
 const [windowMs,setWindowMs]=useState(DEFAULT_POLL_MS);
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const inFlight=useRef(false);
 const zh=store.language.startsWith('zh'),jp=store.language.startsWith('ja');
 const text=(cn:string,en:string,ja:string)=>zh?cn:jp?ja:en;
 const label=(key:string)=>({
  cpu:text('整机 CPU','Machine CPU','マシン CPU'),
  cores:text('逻辑核心','Logical cores','論理コア'),
  process_memory:text('MaaLimbus 进程内存 (RSS)','MaaLimbus process memory (RSS)','MaaLimbus プロセスのメモリ (RSS)'),
  gpu_device:text('GPU','GPU','GPU'),
  gpu_util:text('GPU 利用率','GPU utilization','GPU 使用率'),
  vram_used:text('显存已用','VRAM used','VRAM 使用'),
  vram_total:text('显存总量','VRAM total','VRAM 合計'),
 } as Record<string,string>)[key] || key;

 useEffect(()=>{
  if(!enabled){setSnapshot(null);setError('');setBusy(false);return;}
  let stopped=false;
  async function read(){
   if(stopped || !shouldSample(enabled,inFlight.current))return;
   inFlight.current=true;setBusy(true);
   try {
    const reply=await invoke<Snapshot>('limbus_resource_diagnostics',{intervalMs:windowMs});
    if(stopped)return;
    const parsed=parseSnapshot(reply);
    if(!parsed){setError(text('采样结果不符合诊断约定，已忽略。','The reply did not match the diagnostics contract; it was ignored.','診断の規約と一致しないため無視しました。'));return;}
    setSnapshot(parsed);setError('');
   } catch(e){
    if(!stopped)setError(String(e));
   } finally {
    inFlight.current=false;if(!stopped)setBusy(false);
   }
  }
  read();
  const timer=setInterval(read,pollIntervalMs(windowMs));
  return ()=>{stopped=true;clearInterval(timer);};
 },[enabled,windowMs]);

 const rows=diagnosticsRows(snapshot);
 const processes=processRows(snapshot);
 const memory=processMemoryBytes(processes);
 return <section id="section-diagnostics" className="space-y-3 scroll-mt-6">
  <h2 className="text-lg font-semibold">{text('本机资源诊断','Local resource diagnostics','ローカル診断')}</h2>
  <div className="rounded-xl border border-border p-4 space-y-3">
   <p>{text('默认关闭：只有你打开开关后才会采样，采样只读取计数器，不发游戏输入、不占用控制器。结果只在本窗口显示，不写入文件、不上传。','Off by default: nothing is sampled until you switch it on. Sampling only reads counters — it sends no gameplay input and never takes the controller. Readings stay in this window and are neither written to a file nor uploaded.','既定ではオフです。スイッチを入れるまで何も取得しません。入力は送らず、コントローラも占有しません。結果はこの画面のみで、ファイル保存も送信も行いません。')}</p>
   <label className="flex items-center gap-2">
    <input type="checkbox" checked={enabled} onChange={event=>setEnabled(event.target.checked)} />
    <span>{text('开启本机资源诊断','Enable local resource diagnostics','ローカル診断を有効にする')}</span>
   </label>
   <label className="flex items-center gap-2">
    <span>{text('采样窗口','Sampling window','サンプリング間隔')}</span>
    <select value={windowMs} disabled={!enabled} onChange={event=>setWindowMs(pollIntervalMs(event.target.value))}
      className="px-2 py-1 border border-border rounded bg-transparent disabled:opacity-40">
     {[1000,2000,5000].map(ms=><option key={ms} value={ms}>{ms/1000}s</option>)}
    </select>
   </label>
   {enabled && <p role="status">{busy?text('正在采样…','Sampling…','取得中…'):text('已开启；改变窗口后按新频率采样。','Enabled; the next reads use the selected window.','有効です。次の取得から選択した間隔を使います。')}</p>}
   {snapshot && <dl className="space-y-1">
    {rows.map(row=><div key={row.key} className="flex justify-between gap-4">
     <dt>{label(row.key)}</dt>
     <dd>{row.value}</dd>
    </div>)}
   </dl>}
   {snapshot && <p className="text-sm opacity-70">{snapshot.cpu_percent_semantics}</p>}
   {snapshot && memory.unknown>0 && <p role="status">{text(`有 ${memory.unknown} 个进程的内存读数不可用，上面的进程内存只统计可读的行。`,`${memory.unknown} process memory reading(s) unavailable; the figure above sums only the rows that could be read.`,`${memory.unknown} 件のメモリ値を取得できませんでした。上の値は読めた行のみの合計です。`)}</p>}
   {snapshot && gpuUnsupported(snapshot) && <p role="status">{text(`GPU 提供方状态：${gpuStatus(snapshot)}（不是 0，也不是把整卡占用当作本项目占用）`,`GPU provider status: ${gpuStatus(snapshot)} (not zero, and the whole-device figure is never reported as this project's load)`,`GPU 提供元の状態: ${gpuStatus(snapshot)}（0 ではなく、カード全体の値も本プロジェクトの負荷として扱いません）`)}</p>}
   {snapshot && processes.length>0 && <details>
    <summary>{text('进程明细','Process detail','プロセス詳細')}</summary>
    <ul className="space-y-1 text-sm">
     {processes.map((row,index)=><li key={index}>
      {row.role || UNKNOWN} · PID {row.pid ?? UNKNOWN} · CPU {formatPercent(row.cpu_percent,row.reasons?.cpu_percent)} · RSS {formatBytes(row.rss_bytes,row.reasons?.rss_bytes)} · {row.status || UNKNOWN}
     </li>)}
    </ul>
   </details>}
   {snapshot && <p className="text-sm opacity-70">{text('采样时间','Sampled at','取得時刻')}：{snapshot.sampled_at || UNKNOWN} · {text('窗口','Window','間隔')} {snapshot.interval_ms ?? UNKNOWN} ms · v{snapshot.version ?? UNKNOWN}</p>}
   {error && <p role="alert">{error}</p>}
  </div>
 </section>;
}
