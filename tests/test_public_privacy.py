import pytest
from maalimbus.public_privacy import findings,require_public,public_file

def test_export_refuses_user_path_without_echoing_identifier(tmp_path):
    p=tmp_path/'sample.md';p.write_text('path '+'C:/Users/'+'private-example/session',encoding='utf-8')
    result=findings([p]);assert result[0]['category']=='local_user_path'
    assert 'private-example' not in str(result)
    with pytest.raises(ValueError) as error:require_public([p])
    assert 'private-example' not in str(error.value)

def test_redacted_path_and_schema_field_are_not_real_identifiers(tmp_path):
    p=tmp_path/'safe.md';p.write_text('C:/Users/<user>/session\nuser_id: string',encoding='utf-8')
    assert findings([p])==[]
    p.write_text('UID: '+'A'+'123456789',encoding='utf-8')
    assert findings([p])[0]['category']=='player_id_literal'
    p.write_text('{"uid": "'+'A'+'123456789'+'"}',encoding='utf-8')
    assert findings([p])[0]['category']=='player_id_literal'

def test_local_learning_policy_and_logs_are_not_public_files(tmp_path):
    for name in ('neural-learning.local.json','events.jsonl','run.log'):
        p=tmp_path/name;p.touch();assert not public_file(p)

def test_source_export_refuses_before_zip_and_excludes_local_policy(tmp_path,monkeypatch):
    import sys,zipfile
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
    import build_windows_package as package
    monkeypatch.setattr(package,'ROOT',tmp_path)
    for name in ('src','agent','tools','tests','docs','assets','desktop','THIRD_PARTY_NOTICES'):
        (tmp_path/name).mkdir()
    for name in ('README.md','README_en.md','LICENSE','pyproject.toml','PROJECT.md','.gitignore'):
        (tmp_path/name).write_text('public',encoding='utf-8')
    private=tmp_path/'assets'/'neural-learning.local.json';private.write_text('private account policy')
    document=tmp_path/'docs'/'example.md';document.write_text('C:/Users/'+'private-example/proof')
    output=tmp_path/'source.zip'
    with pytest.raises(ValueError):package.copy_public_sources(output)
    assert not output.exists()
    document.write_text('C:/Users/<user>/proof');package.copy_public_sources(output)
    with zipfile.ZipFile(output) as archive:
        assert 'assets/neural-learning.local.json' not in archive.namelist()
        assert 'docs/example.md' in archive.namelist()
