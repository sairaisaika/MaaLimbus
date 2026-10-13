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

def test_local_learning_policy_and_logs_are_not_public_files(tmp_path):
    for name in ('neural-learning.local.json','events.jsonl','run.log'):
        p=tmp_path/name;p.touch();assert not public_file(p)
