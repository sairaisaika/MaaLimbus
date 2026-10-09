import { useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useAppStore } from '@/stores/appStore';
import { OptionEditor } from './OptionEditor';
type Status = {current_version:string;available_version:string|null;status:string;retry_at:number|null;newer_available:boolean};
export function SoftwareUpdatePanel() {
 const store=useAppStore(),[result,setResult]=useState<Status|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const zh=store.language.startsWith('zh'),jp=store.language.startsWith('ja');
 const text=(cn:string,en:string,ja:string)=>zh?cn:jp?ja:en;
 const statusLabel=(status:string)=>({
  current:text('已是最新版本','Up to date','最新です'),
  update_available:text('发现新版本','New version available','新しいバージョンがあります'),
  unsupported_release_tag:text('发布版本号不符合更新要求','Release version cannot be used for updates','リリースのバージョン形式に対応していません'),
  rate_limited:text('GitHub 请求受限，请稍后再试','GitHub request limit reached. Try later.','GitHub の制限により、後で再試行してください'),
  offline:text('无法连接 GitHub','Cannot connect to GitHub','GitHub に接続できません'),
  unavailable:text('更新信息暂不可用','Update information unavailable','更新情報を取得できません'),
  deferred:text('检查已延后','Check deferred','確認を延期しました'),
 }[status] || text('检查未完成，请稍后再试','Check incomplete. Try later.','確認できませんでした。後で再試行してください'));
 async function check(){setBusy(true);setError('');try{setResult(await invoke<Status>('limbus_project_update_check'));}catch(e){setError(String(e));}finally{setBusy(false);}}
 return <section id="section-software-update" className="space-y-3 scroll-mt-6">
  <h2 className="text-lg font-semibold">{text('软件更新','Software updates','ソフトウェア更新')}</h2>
  <div className="rounded-xl border border-border p-4 space-y-3">
   <p>{text('当前版本','Current version','現在のバージョン')}：{result?.current_version || store.projectInterface?.version || '—'}</p>
   <OptionEditor optionKey="software_auto_update" globalScope />
   <button disabled={busy || store.instances.some(i=>i.isRunning)} onClick={check} className="px-3 py-2 rounded border border-border disabled:opacity-40">{busy?text('正在检查…','Checking…','確認中…'):text('检查 GitHub 更新','Check GitHub updates','GitHub の更新を確認')}</button>
   {result && <p role="status">{statusLabel(result.status)}{result.available_version?` · ${result.available_version}`:''}{result.retry_at?` · ${text('下次检查','Next check','次回の確認')} ${new Date(result.retry_at*1000).toLocaleString()}`:''}</p>}
   {result?.newer_available && <p>{text('启用自动更新后，下次正常退出并重新打开时安装；检查不会立即替换软件。','With automatic updates enabled, install on the next normal close and reopen. Checking does not replace the running app.','自動更新を有効にすると、通常終了して再起動した際にインストールします。確認時には置き換えません。')}</p>}
   {error && <p role="alert">{error}</p>}
  </div>
 </section>;
}
