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
        'custom_action_param':{'mode':'configure','slot':1,'name':''},'next':safety+['TeamLibraryVerified','TeamLibraryRow','TeamLibraryScroll'],
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
                  'description':'$team_library_scope','option':['team_slot','team_name'],'default_check':False}],
        'option': {
            'team_slot': {'type':'select','label':'$team_slot','default_case':'1','cases':[
                {'name':str(slot),'label':str(slot),'pipeline_override':{'TeamLibraryConfigure':{'custom_action_param':{'slot':slot}}}}
                for slot in range(1,21)]},
            'team_name': {'type':'input','label':'$team_name','inputs':[{'name':'name','label':'$team_name',
                           'default':'','verify':r'^.{0,80}$','pipeline_type':'string'}],
                          'pipeline_override':{'TeamLibraryConfigure':{'custom_action_param':{'name':'{name}'}}}},
        },
    })
    for code, texts in {
        'en_us': {'description': 'Native Windows Limbus automation with MaaFramework', 'windows': 'Windows · Limbus Company', 'mirror_group': 'Mirror Dungeon', 'daily_group': 'Daily tasks', 'mirror_hard': 'Hard Mirror Dungeon', 'mirror_status': 'Development: entry navigation only; five floors and team rotation are not verified.',
                  'select_saved_team':'Select saved team','team_slot':'Saved team slot','team_name':'Renamed team label (optional)',
                  'team_library_scope':'Select and verify a team on the Sinners team-management page. Does not enter a dungeon.'},
        'ja_jp': {'description': 'MaaFramework による Windows 版 Limbus 自動操作', 'windows': 'Windows · Limbus Company', 'mirror_group': '鏡ダンジョン', 'daily_group': 'デイリー', 'mirror_hard': '鏡ダンジョン · ハード', 'mirror_status': '開発中：入口の操作のみ。5階クリアとチーム切替は未検証です。',
                  'select_saved_team':'保存チームを選択','team_slot':'保存チーム番号','team_name':'変更したチーム名（任意）',
                  'team_library_scope':'囚人のチーム管理画面で選択と確認を行います。ダンジョンには入場しません。'},
    }.items():
        write(ROOT / f'assets/i18n/{code}.json', texts)


if __name__ == '__main__':
    main()
