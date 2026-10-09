"""Project-owned interactive editors over pinned MXU; never patch an installed app."""
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]


def patch(source):
    source=Path(source).resolve()
    if source==(ROOT/'sources/upstream/MXU').resolve() or source==ROOT/'dist/MaaLimbus':
        raise ValueError('Patch a separate source work directory')
    p=source/'src/components/SettingsPage.tsx';s=p.read_text(encoding='utf8')
    s=s.replace("  if (/^global_team_\\d+$/.test(optionKey)) return <TeamBuildEditor optionKey={optionKey} />;", "  if (useAppStore.getState().projectInterface?.name==='MaaLimbus' && /^global_team_\\d+$/.test(optionKey)) return <TeamBuildEditor optionKey={optionKey} />;")
    if './TeamBuildEditor' not in s:
        s=s.replace("import { OptionEditor } from './OptionEditor';","import { OptionEditor } from './OptionEditor';\nimport { TeamBuildEditor } from './TeamBuildEditor';")
        needle='function TaskOptionCard({ optionKey }: { optionKey: string }) {\n'
        if needle not in s:raise ValueError('Pinned MXU setting hook changed')
        s=s.replace(needle,needle+"  if (useAppStore.getState().projectInterface?.name==='MaaLimbus' && /^global_team_\\d+$/.test(optionKey)) return <TeamBuildEditor optionKey={optionKey} />;\n")
    if './SoftwareUpdatePanel' not in s:
        s=s.replace("import { TeamBuildEditor } from './TeamBuildEditor';", "import { TeamBuildEditor } from './TeamBuildEditor';\nimport { SoftwareUpdatePanel } from './SoftwareUpdatePanel';\nimport { ConnectionPanel } from './ConnectionPanel';")
        s=s.replace("    items.push({ id: 'general',", "    if (projectInterface?.name==='MaaLimbus') items.push(\n      {id:'software-update',icon:Download,labelKey:language.startsWith('zh')?'软件更新':language.startsWith('ja')?'ソフトウェア更新':'Software updates'},\n      {id:'devices',icon:Settings2,labelKey:language.startsWith('zh')?'设备连接':language.startsWith('ja')?'デバイス接続':'Device connections'},\n    );\n    items.push({ id: 'general',",1)
        s=s.replace('settingsSections.length]);','settingsSections.length, language, projectInterface?.name]);',1)
        s=s.replace('{settingsSections.map((section)',"{settingsSections.filter(section=>projectInterface?.name!=='MaaLimbus' || section.name!=='software_update').map((section)",1)
        s=s.replace('            {/* 通用设置 */}', '''            {projectInterface?.name==='MaaLimbus' && <><SoftwareUpdatePanel />
              <section id="section-devices" className="space-y-3 scroll-mt-6"><h2 className="text-lg font-semibold">{language.startsWith('zh')?'设备连接':language.startsWith('ja')?'デバイス接続':'Device connections'}</h2><ConnectionPanel /></section>
            </>}
            {/* 通用设置 */}''',1)
    p.write_text(s,encoding='utf8')
    shutil.copyfile(ROOT/'desktop/mxu/TeamBuildEditor.tsx',source/'src/components/TeamBuildEditor.tsx')
    shutil.copyfile(ROOT/'desktop/mxu/teamOrder.ts',source/'src/utils/teamOrder.ts')
    shutil.copyfile(ROOT/'desktop/mxu/SoftwareUpdatePanel.tsx',source/'src/components/SoftwareUpdatePanel.tsx')
    rust=source/'src-tauri/src/lib.rs';s=rust.read_text(encoding='utf8')
    if 'mod limbus_update;' not in s:
        s=s.replace('pub mod commands;', 'pub mod commands;\nmod limbus_update;',1)
        s=s.replace('tauri::generate_handler![','tauri::generate_handler![\n            limbus_update::limbus_project_update_check,',1)
        rust.write_text(s,encoding='utf8')
    shutil.copyfile(ROOT/'desktop/mxu/limbus_update.rs',source/'src-tauri/src/limbus_update.rs')


if __name__=='__main__':patch(sys.argv[1])
