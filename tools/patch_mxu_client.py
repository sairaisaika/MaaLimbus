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
    if './RotationPanel' not in s:
        s=s.replace("import { TeamBuildEditor } from './TeamBuildEditor';", "import { TeamBuildEditor } from './TeamBuildEditor';\nimport { RotationPanel } from './RotationPanel';",1)
        needle="<><SoftwareUpdatePanel />"
        if needle not in s:raise ValueError('Pinned MXU rotation panel hook changed')
        s=s.replace(needle,"<><RotationPanel /><SoftwareUpdatePanel />",1)
    if './ResourceDiagnosticsPanel' not in s:
        s=s.replace("import { RotationPanel } from './RotationPanel';", "import { RotationPanel } from './RotationPanel';\nimport { ResourceDiagnosticsPanel } from './ResourceDiagnosticsPanel';",1)
        s=s.replace("  Globe,\n} from 'lucide-react';","  Globe,\n  Activity,\n} from 'lucide-react';",1)
        devices="      {id:'devices',icon:Settings2,labelKey:language.startsWith('zh')?'设备连接':language.startsWith('ja')?'デバイス接続':'Device connections'},\n"
        if devices not in s:raise ValueError('Pinned MXU diagnostics nav hook changed')
        s=s.replace(devices,devices+"      {id:'diagnostics',icon:Activity,labelKey:language.startsWith('zh')?'本机资源诊断':language.startsWith('ja')?'ローカル診断':'Local diagnostics'},\n",1)
        needle="<><RotationPanel /><SoftwareUpdatePanel />"
        if needle not in s:raise ValueError('Pinned MXU diagnostics panel hook changed')
        s=s.replace(needle,"<><RotationPanel /><SoftwareUpdatePanel /><ResourceDiagnosticsPanel />",1)
    p.write_text(s,encoding='utf8')
    shutil.copyfile(ROOT/'desktop/mxu/TeamBuildEditor.tsx',source/'src/components/TeamBuildEditor.tsx')
    shutil.copyfile(ROOT/'desktop/mxu/teamOrder.ts',source/'src/utils/teamOrder.ts')
    shutil.copyfile(ROOT/'desktop/mxu/teamArtwork.ts',source/'src/utils/teamArtwork.ts')
    shutil.copyfile(ROOT/'desktop/mxu/StarCardsEditor.tsx',source/'src/components/StarCardsEditor.tsx')
    for name in ('ARTWORK_NOTICE.md','artwork-provenance.json'):
        shutil.copyfile(ROOT/'desktop/mxu'/name,source/name)
    option=source/'src/components/OptionEditor.tsx';o=option.read_text(encoding='utf8')
    if 'function StandardOptionEditor(' not in o:
        o=o.replace("import { RichLabel } from './RichLabel';", "import { RichLabel } from './RichLabel';\nimport { StarCardsEditor } from './StarCardsEditor';",1)
        needle='export function OptionEditor({'
        if o.count(needle)!=1:raise ValueError('Pinned MXU option hook changed')
        o=o.replace(needle,'''export function OptionEditor(props: OptionEditorProps) {
  const project = useAppStore(state=>state.projectInterface?.name);
  if (project==='MaaLimbus') {
    if (/^mirror_star_(task|team)_\\d$/.test(props.optionKey)) return null;
    const matched = /^mirror_star_(task|team)_budget$/.exec(props.optionKey);
    if (matched) return <StarCardsEditor {...props} prefix={matched[1]==='task'?'mirror_star_task':'mirror_star_team'} />;
  }
  return <StandardOptionEditor {...props} />;
}

function StandardOptionEditor({''',1)
        option.write_text(o,encoding='utf8')
    shutil.copyfile(ROOT/'desktop/mxu/SoftwareUpdatePanel.tsx',source/'src/components/SoftwareUpdatePanel.tsx')
    shutil.copyfile(ROOT/'desktop/mxu/RotationPanel.tsx',source/'src/components/RotationPanel.tsx')
    shutil.copyfile(ROOT/'desktop/mxu/ResourceDiagnosticsPanel.tsx',source/'src/components/ResourceDiagnosticsPanel.tsx')
    shutil.copyfile(ROOT/'desktop/mxu/resourceDiagnostics.ts',source/'src/utils/resourceDiagnostics.ts')
    rust=source/'src-tauri/src/lib.rs';s=rust.read_text(encoding='utf8')
    if 'mod limbus_update;' not in s:
        s=s.replace('pub mod commands;', 'pub mod commands;\nmod limbus_update;',1)
        s=s.replace('tauri::generate_handler![','tauri::generate_handler![\n            limbus_update::limbus_project_update_check,',1)
        rust.write_text(s,encoding='utf8')
    if 'limbus_update::limbus_rotation_manage,' not in s:
        s=s.replace('tauri::generate_handler![','tauri::generate_handler![\n            limbus_update::limbus_rotation_manage,',1)
        rust.write_text(s,encoding='utf8')
    shutil.copyfile(ROOT/'desktop/mxu/limbus_update.rs',source/'src-tauri/src/limbus_update.rs')
    if 'mod limbus_diagnostics;' not in s:
        s=s.replace('pub mod commands;', 'pub mod commands;\nmod limbus_diagnostics;',1)
        rust.write_text(s,encoding='utf8')
    if 'limbus_diagnostics::limbus_resource_diagnostics,' not in s:
        s=s.replace('tauri::generate_handler![','tauri::generate_handler![\n            limbus_diagnostics::limbus_resource_diagnostics,',1)
        rust.write_text(s,encoding='utf8')
    shutil.copyfile(ROOT/'desktop/mxu/limbus_diagnostics.rs',source/'src-tauri/src/limbus_diagnostics.rs')
    # MaaLimbus settings and ADB do not need administrator privileges. The
    # existing explicit restart_as_admin command remains available for Win32.
    main=source/'src-tauri/src/main.rs';s=main.read_text(encoding='utf8')
    needle='if !cfg!(debug_assertions) && !mxu_lib::commands::system::is_elevated() {'
    replacement='''let maalimbus_ui = std::env::current_exe().ok()
            .and_then(|p| p.file_name().map(|n| n.to_string_lossy().to_string()))
            .map(|n| n.eq_ignore_ascii_case("MaaLimbus.exe")).unwrap_or(false);
        if !maalimbus_ui && !cfg!(debug_assertions) && !mxu_lib::commands::system::is_elevated() {'''
    if 'let maalimbus_ui =' not in s:
        if s.count(needle)!=1:raise ValueError('Pinned MXU elevation hook changed')
        main.write_text(s.replace(needle,replacement,1),encoding='utf8')


if __name__=='__main__':patch(sys.argv[1])
