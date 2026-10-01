"""Prepare documented public models/licenses and locale resources, no account data."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ocr', type=Path, required=True)
    args = parser.parse_args()
    target_ocr = ROOT/'assets/resource/base/model/ocr'
    if args.ocr.resolve() != target_ocr.resolve():
        shutil.copytree(args.ocr,target_ocr,dirs_exist_ok=True)
    locales = {
        # The retained Drive screenshot's outlined menu label is read as Mirro
        # at Maa's 720px replay scale. Require the independent Inferno heading.
        'en': {'mirror_menu': r'^Mirro(?:r)?$|Mirror\s*Dungeons?', 'inferno': '^Inferno$', 'enter': '^Enter$',
               'exploring': 'Exploring|Before Entry', 'details': '^Details$', 'teams': r'TEAMS|Preset',
               'forbidden_dialog': r'Purchase\s*Lunacy|Refill\s*Enkephalin|Extract\s*10|Exchange\s*Lunacy',
               'expired': 'previous session has expired', 'defeat': '^DEFEAT$', 'sin_cost': r'^SIN\s*\|?\s*COST$',
               'acquire_gift':r'^Acquire\s*E\.?G\.?O\.?\s*Gift$', 'owned_gift':r'^Owned$', 'gift_confirm':r'^Confirm$'},
        'jp': {'mirror_menu': '鏡ダンジョン|鏡のダンジョン', 'inferno': 'Inferno|地獄', 'enter': '入場|入る|Enter',
               'exploring': '探索状況|入場前|探索中|Exploring', 'details': '詳細|Details', 'teams': 'チーム|プリセット|TEAMS',
               'forbidden_dialog': '狂気を購入|狂気で.*回復|抽出10回|エンケファリン.*回復',
               'expired': '前回.*期限|前回.*終了', 'defeat': '敗北|DEFEAT', 'sin_cost': r'SIN\s*\|?\s*COST|罪悪.*コスト',
               'acquire_gift':r'E\.?G\.?O\.?\s*ギフト.*獲得|^Acquire\s*E\.?G\.?O\.?\s*Gift$',
               'owned_gift':r'^所持済み$|^所持$|^Owned$', 'gift_confirm':r'^確定$|^確認$|^Confirm$'},
    }
    for locale, words in locales.items():
        write(ROOT / f'assets/resource/{locale}/locale.json', words)
        write(ROOT / f'assets/resource/{locale}/pipeline/locale.json', {})
    nodes = {
        'MirrorHard': {'recognition': 'DirectHit', 'action': 'Custom', 'custom_action':'limbus_preflight', 'next': ['LimbusSafety', 'MirrorDrive', 'MirrorEnter', 'MirrorTeamEvidence'], 'timeout': 20000, 'on_error': ['LimbusUnknown']},
        'LimbusSafety': {'recognition': 'Custom', 'custom_recognition': 'limbus_scene', 'custom_recognition_param': {'scene': 'RESOURCE_DIALOG'}, 'action': 'Custom', 'custom_action': 'limbus_terminal', 'custom_action_param': {'reason': 'unconfigured_resource_dialog'}, 'next': [], 'on_error': []},
        'MirrorDrive': {'recognition': 'Custom', 'custom_recognition': 'limbus_scene', 'custom_recognition_param': {'scene': 'DRIVE', 'token': 'mirror_menu', 'roi': [.23, .25, .46, .55]}, 'action': 'Click', 'target': True, 'post_delay': 1000, 'max_hit': 3, 'next': ['LimbusSafety', 'MirrorEnter', 'MirrorDrive'], 'timeout': 20000, 'on_error': ['LimbusUnknown']},
        'MirrorEnter': {'recognition': 'Custom', 'custom_recognition': 'limbus_scene', 'custom_recognition_param': {'scene': 'MIRROR_ENTRY', 'token': 'enter', 'roi': [.76, .55, .97, .85]}, 'action': 'Click', 'target': True, 'post_delay': 1000, 'max_hit': 2, 'next': ['LimbusSafety', 'MirrorTeamEvidence'], 'timeout': 20000, 'on_error': ['LimbusUnknown']},
        'MirrorTeamEvidence': {'recognition': 'Custom', 'custom_recognition': 'limbus_scene', 'custom_recognition_param': {'scene': 'TEAM_LIBRARY'}, 'action': 'Custom', 'custom_action': 'limbus_terminal', 'custom_action_param': {'reason': 'unexpected_team_library_not_dungeon_deployment'}, 'next': [], 'on_error': []},
        'LimbusUnknown': {'recognition': 'DirectHit', 'action': 'Custom', 'custom_action': 'limbus_terminal', 'custom_action_param': {'reason': 'unknown_or_bounded_transition_exhausted'}, 'next': [], 'on_error': []},
    }
    for name,scene in [('LimbusExpired','EXPIRED_SESSION'),('LimbusDefeat','DEFEAT')]:
        nodes[name] = {'recognition':'Custom','custom_recognition':'limbus_scene',
            'custom_recognition_param':{'scene':scene},'action':'Custom','custom_action':'limbus_terminal',
            'custom_action_param':{'reason':scene.lower()},'next':[],'on_error':[]}
    safety = ['LimbusSafety','LimbusExpired','LimbusDefeat']
    for node in nodes.values():
        if node.get('next',[])[:1] == ['LimbusSafety']:
            node['next'] = safety + node['next'][1:]
    nodes['TeamLibraryStart'] = {'recognition':'DirectHit','action':'Custom','custom_action':'limbus_preflight',
        'next':['TeamLibraryConfigure'],'on_error':['LimbusUnknown']}
    nodes['TeamLibraryConfigure'] = {'recognition':'DirectHit','action':'Custom','custom_action':'limbus_team',
        'custom_action_param':{'mode':'configure','slot':1},'next':['TeamLibraryName'],
        'timeout':20000,'on_error':['LimbusUnknown']}
    nodes['TeamLibraryName']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_team',
        'custom_action_param':{'mode':'name','name':''},'next':safety+['TeamLibraryVerified','TeamLibraryRow','TeamLibraryScroll'],
        'timeout':20000,'on_error':['LimbusUnknown']}
    for name,mode,action in [('TeamLibraryVerified','verified','Custom'),('TeamLibraryRow','row','Click'),('TeamLibraryScroll','scroll','Swipe')]:
        node = {'recognition':'Custom','custom_recognition':'limbus_scene',
                'custom_recognition_param':{'scene':'TEAM_LIBRARY','team_mode':mode},
                'action':action,'post_delay':1000,'timeout':20000,'on_error':['LimbusUnknown']}
        if mode=='verified':
            node.update(custom_action='limbus_team',custom_action_param={'mode':'verified'},next=[])
        else:
            node.update(next=safety+['TeamLibraryVerified','TeamLibraryRow','TeamLibraryScroll'], max_hit=3 if mode=='row' else 8)
            if mode=='row': node['target']=True
        nodes[name]=node
    nodes['ThemePackStart']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_preflight',
        'next':['ThemePackConfigure'],'on_error':['LimbusUnknown']}
    nodes['ThemePackConfigure']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_team',
        'custom_action_param':{'mode':'configure','slot':1},'next':['ThemePackPreference'],
        'timeout':3000,'on_error':['LimbusUnknown']}
    nodes['ThemePackPreference']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_team',
        'custom_action_param':{'mode':'pack','name':''},'next':['ThemePackWeight'],'on_error':['LimbusUnknown']}
    nodes['ThemePackWeight']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_team',
        'custom_action_param':{'mode':'weight','weight':20},'next':safety+['ThemePackNormal','ThemePackDrag'],
        'timeout':3000,'on_error':['LimbusUnknown']}
    nodes['ThemePackNormal']={'recognition':'Custom','custom_recognition':'limbus_scene',
        'custom_recognition_param':{'scene':'THEME_PACKS','theme_mode':'normal'},
        'action':'Custom','custom_action':'limbus_terminal',
        'custom_action_param':{'reason':'theme_pack_difficulty_is_normal_not_hard'},'next':[],'on_error':[]}
    nodes['ThemePackDrag']={'recognition':'Custom','custom_recognition':'limbus_scene',
        'custom_recognition_param':{'scene':'THEME_PACKS','theme_mode':'recommend'},
        'action':'Swipe','max_hit':1,'post_delay':1000,'next':['ThemePackObserve'],
        'timeout':3000,'on_error':['LimbusUnknown']}
    nodes['ThemePackObserve']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_theme_observe',
        'next':['ThemePackBoundary'],'on_error':['LimbusUnknown']}
    nodes['ThemePackBoundary']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_terminal',
        'custom_action_param':{'reason':'theme_drag_recorded_map_verification_pending'},'next':[],'on_error':[]}
    nodes['DeploymentStart']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_preflight',
        'next':['DeploymentConfigure'],'on_error':['LimbusUnknown']}
    nodes['DeploymentConfigure']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_team',
        'custom_action_param':{'mode':'configure','slot':1},'next':['DeploymentPreset'],'on_error':['LimbusUnknown']}
    nodes['DeploymentPreset']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_team',
        'custom_action_param':{'mode':'deployment','preset':'saved'},'next':safety+['DeploymentComplete','DeploymentNext'],
        'timeout':3000,'on_error':['LimbusUnknown']}
    nodes['DeploymentNext']={'recognition':'Custom','custom_recognition':'limbus_scene',
        'custom_recognition_param':{'scene':'DEPLOYMENT','deployment_mode':'next'},
        'action':'Click','target':True,'post_delay':700,'max_hit':12,
        'next':safety+['DeploymentComplete','DeploymentNext'],'timeout':3000,'on_error':['LimbusUnknown']}
    nodes['DeploymentComplete']={'recognition':'Custom','custom_recognition':'limbus_scene',
        'custom_recognition_param':{'scene':'DEPLOYMENT','deployment_mode':'complete'},
        'action':'Custom','custom_action':'limbus_deployment_proof','next':['DeploymentBoundary'],
        'on_error':['LimbusUnknown']}
    nodes['DeploymentBoundary']={'recognition':'DirectHit','action':'Custom','custom_action':'limbus_terminal',
        'custom_action_param':{'reason':'deployment_order_observed_battle_not_started'},'next':[],'on_error':[]}
    write(ROOT / 'assets/resource/base/pipeline/mirror.json', nodes)
    write(ROOT / 'assets/interface.json', {
        'interface_version': 2, 'name': 'MaaLimbus', 'label': 'MaaLimbus', 'version': 'v0.1.0',
        'github': 'https://github.com/sairaisaika/MaaLimbus', 'license': '../LICENSE',
        'description': '$description', 'languages': {'en_us': 'i18n/en_us.json', 'ja_jp': 'i18n/ja_jp.json'},
        'controller': [{'name': 'windows', 'label': '$windows', 'type': 'Win32', 'display_long_side': 1920, 'permission_required': True,
                        'win32': {'class_regex': '^UnityWndClass$', 'window_regex': '^LimbusCompany$', 'screencap': 'FramePool', 'mouse': 'Seize', 'keyboard': 'Seize'}}],
        'resource': [{'name': 'en', 'label': 'English', 'path': ['./resource/base', './resource/en']},
                     {'name': 'jp', 'label': '日本語', 'path': ['./resource/base', './resource/jp']}],
        'agent': {'child_exec': 'python', 'child_args': ['../agent/main.py']},
        'group': [{'name': 'mirror', 'label': '$mirror_group'}, {'name': 'daily', 'label': '$daily_group'}],
        'task': [{'name': 'mirror_hard', 'label': '$mirror_hard', 'entry': 'MirrorHard', 'group': ['mirror'], 'description': '$mirror_status', 'default_check': False},
                 {'name':'select_saved_team','label':'$select_saved_team','entry':'TeamLibraryStart','group':['mirror'],
                  'description':'$team_library_scope','option':['team_slot','team_name'],'default_check':False},
                 {'name':'select_theme_pack','label':'$select_theme_pack','entry':'ThemePackStart','group':['mirror'],
                  'description':'$theme_pack_scope','option':['team_slot','pack_name','pack_weight'],'default_check':False},
                 {'name':'prepare_deployment','label':'$prepare_deployment','entry':'DeploymentStart','group':['mirror'],
                  'description':'$deployment_scope','option':['team_slot','deployment_preset'],'default_check':False}],
        'option': {
            'team_slot': {'type':'select','label':'$team_slot','default_case':'1','cases':[
                {'name':str(slot),'label':str(slot),'pipeline_override':{
                    'TeamLibraryConfigure':{'custom_action_param':{'mode':'configure','slot':slot}},
                    'ThemePackConfigure':{'custom_action_param':{'mode':'configure','slot':slot}},
                    'DeploymentConfigure':{'custom_action_param':{'mode':'configure','slot':slot}}}}
                for slot in range(1,21)]},
            'team_name': {'type':'input','label':'$team_name','inputs':[{'name':'name','label':'$team_name',
                           'default':'','verify':r'^.{0,80}$','pipeline_type':'string'}],
                          'pipeline_override':{'TeamLibraryName':{'custom_action_param':{'mode':'name','name':'{name}'}}}},
            'pack_name':{'type':'select','label':'$pack_name','default_case':'unchanged','cases':[
                {'name':'unchanged','label':'$keep_pack_preferences','pipeline_override':{'ThemePackPreference':{'custom_action_param':{'mode':'pack','name':''}}}}]+[
                {'name':str(index),'label':entry['name'],'pipeline_override':{'ThemePackPreference':{'custom_action_param':{'mode':'pack','name':entry['name']}}}}
                for index,entry in enumerate(json.loads((ROOT/'assets/resource/base/theme-catalog.json').read_text(encoding='utf-8'))['names'])]},
            'pack_weight':{'type':'select','label':'$pack_weight','default_case':'20','cases':[
                {'name':str(weight),'label':'$pack_block' if weight==0 else str(weight),
                 'pipeline_override':{'ThemePackWeight':{'custom_action_param':{'mode':'weight','weight':weight}}}}
                for weight in (0,1,5,10,20,100)]},
            'deployment_preset':{'type':'select','label':'$deployment_preset','default_case':'saved','cases':[
                {'name':preset,'label':'$deployment_'+preset,
                 'pipeline_override':{'DeploymentPreset':{'custom_action_param':{'mode':'deployment','preset':preset}}}}
                for preset in ('saved','natural')]},
        },
    })
    for code, texts in {
        'en_us': {'description': 'Native Windows Limbus automation with MaaFramework', 'windows': 'Windows · Limbus Company', 'mirror_group': 'Mirror Dungeon', 'daily_group': 'Daily tasks', 'mirror_hard': 'Hard Mirror Dungeon', 'mirror_status': 'Development: entry navigation only; five floors and team rotation are not verified.',
                  'select_saved_team':'Select saved team','team_slot':'Saved team slot','team_name':'Renamed team label (optional)',
                  'team_library_scope':'Select and verify a team on the Sinners team-management page. Does not enter a dungeon.',
                  'select_theme_pack':'Select theme pack (development)','theme_pack_scope':'Current Hard pack page only. Save one preference for this team and drag the best identified pack. Stops with a fresh frame; map transition not yet verified.',
                  'pack_name':'Save a theme preference','keep_pack_preferences':'Keep saved preferences','pack_weight':'Preference weight (higher first)','pack_block':'Do not select',
                  'prepare_deployment':'Prepare deployment (development)','deployment_scope':'Current battle preparation only. Uses saved order, verifies count and order after each choice, then stops before starting battle. Experimental; live geometry unverified.',
                  'deployment_preset':'Deployment order','deployment_saved':'Keep saved order','deployment_natural':'Save natural sinner order'},
        'ja_jp': {'description': 'MaaFramework による Windows 版 Limbus 自動操作', 'windows': 'Windows · Limbus Company', 'mirror_group': '鏡ダンジョン', 'daily_group': 'デイリー', 'mirror_hard': '鏡ダンジョン · ハード', 'mirror_status': '開発中：入口の操作のみ。5階クリアとチーム切替は未検証です。',
                  'select_saved_team':'保存チームを選択','team_slot':'保存チーム番号','team_name':'変更したチーム名（任意）',
                  'team_library_scope':'囚人のチーム管理画面で選択と確認を行います。ダンジョンには入場しません。',
                  'select_theme_pack':'テーマパック選択（開発中）','theme_pack_scope':'ハードの選択画面でチームの優先度を保存し、識別できたパックをドラッグします。新しい画像を保存して停止します。マップ移行は未検証です。',
                  'pack_name':'パックの優先設定を保存','keep_pack_preferences':'保存した設定を維持','pack_weight':'優先度（大きい順）','pack_block':'選択しない',
                  'prepare_deployment':'出撃順の準備（開発中）','deployment_scope':'戦闘準備画面のみ。選択ごとに人数と順番を確認し、戦闘開始前に停止します。実機の位置確認は未完了です。',
                  'deployment_preset':'出撃順','deployment_saved':'保存した順番を維持','deployment_natural':'囚人の標準順を保存'},
    }.items():
        write(ROOT / f'assets/i18n/{code}.json', texts)


if __name__ == '__main__':
    main()
