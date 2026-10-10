"""Audit retained native locale snapshots without device or application input."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    directory=ROOT/'build/native-en-ja-20261010'
    evidence={}
    labels={
        'en-main':['Open game','Mirror Dungeon','Experience Luxcavation','Thread Luxcavation','Collect rewards','Convert Enkephalin','Battle auto-assignment'],
        'ja-main':['ゲームを開く','鏡ダンジョン','経験値採光','紐採光','報酬を受け取る','エンケファリン変換','戦闘の自動配置'],
        'ja-update-device':['ソフトウェア更新','現在のバージョン：v0.1.2','デバイス接続','GitHub の更新を確認'],
    }
    for name,expected in labels.items():
        path=directory/(name+'.json')
        value=json.loads(path.read_text(encoding='utf-8'))
        assert value['window']['title']=='MaaLimbus v0.1.2'
        assert value['window']['app'].lower()=='process:d:\\fgoa\\maalimbus\\dist\\maalimbus\\maalimbus.exe'
        text=value['accessibility']['document_text']
        assert all(label in text for label in expected),(name,expected)
        screenshot=directory/(name+'-0.jpg')
        assert screenshot.read_bytes().startswith(b'\xff\xd8\xff')
        evidence[name]=dict(window=value['window'],json_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            screenshot_path=str(screenshot),screenshot_format='JPEG',
            screenshot_sha256=hashlib.sha256(screenshot.read_bytes()).hexdigest(),labels=expected)
    config=json.loads((ROOT/'dist/MaaLimbus/config/mxu-MaaLimbus.json').read_text(encoding='utf-8'))
    assert config['settings']['language']=='zh-CN' and config['settings']['autoRunOnLaunch'] is False
    assert all(t['enabled'] is False for i in config['instances'] for t in i['tasks'])
    baseline=json.loads((ROOT/'build/reward-task-budget-native-verification.json').read_text(encoding='utf-8'))['private_hashes']
    assert all(hashlib.sha256((ROOT/'config'/Path(name).name).read_bytes()).hexdigest()==digest for name,digest in baseline.items())
    report=dict(passed=True,scope='Actual native English/Japanese UI rendering, not game recognition or execution',
        evidence=evidence,restored_language='zh-CN',autorun=False,tasks_enabled=False,
        private_game_state_hashes_unchanged=True,game_input=False,task_dispatch_verified=False,
        japanese_game_e2e_verified=False,installed_source='2a684f6')
    (ROOT/'build/native-locale-real-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Native English/Japanese snapshots and unchanged game state verified; game E2E not claimed.')


if __name__=='__main__':main()
