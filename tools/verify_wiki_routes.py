"""Exercise portable routing behavior in an isolated project, never live state."""
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wiki_routes',ROOT/'skills/multi-agent-wiki/scripts/wiki_route.py')
router=importlib.util.module_from_spec(spec);spec.loader.exec_module(router)

def main():
    cases=[]
    with tempfile.TemporaryDirectory(prefix='wiki-route-') as temporary:
        root=Path(temporary)
        for name in ('src','docs/wiki','tests'):(root/name).mkdir(parents=True,exist_ok=True)
        file=root/'src/jobs.py';body='class Runner:\n    def start(self):\n        pass\n'
        file.write_text(body,encoding='utf8')
        (root/'docs/wiki/runtime.md').write_text('# Runtime\n\n<a id="startup"></a>\n',encoding='utf8')
        (root/'tests/test_jobs.py').write_text('',encoding='utf8')
        route=dict(id='start',title='Startup',aliases=['开始失败','start failed'],
            sources=[dict(path='src/jobs.py',symbol='Runner.start')],
            docs=['docs/wiki/runtime.md#startup'],tests=['tests/test_jobs.py'],
            boundary='Dispatch is not completion')
        manifest=dict(schema_version=1,project='Fixture',routes=[route])
        assert router.resolve(root,manifest)[0]['locations'][0]['line']==2
        file.write_text('\n\n\n'+body,encoding='utf8')
        assert router.resolve(root,manifest)[0]['locations'][0]['line']==5
        cases.append('moved_symbol_resolves_current_line')
        for fault in ('missing_symbol','missing_anchor','path_escape','ambiguous_needle'):
            changed=json.loads(json.dumps(manifest));row=changed['routes'][0]
            if fault=='missing_symbol':row['sources'][0]['symbol']='Runner.absent'
            if fault=='missing_anchor':row['docs']=['docs/wiki/runtime.md#absent']
            if fault=='path_escape':row['sources'][0]['path']='../outside.py'
            if fault=='ambiguous_needle':
                row['sources']=[dict(path='src/jobs.py',needle='same')]
                file.write_text('# same\n# same\n'+body,encoding='utf8')
            try:router.resolve(root,changed)
            except ValueError:cases.append(fault+'_reported')
            else:raise AssertionError('Invalid route accepted: '+fault)
        assert router.rank('开始失败了怎么办',[route])[0]['id']=='start'
        assert router.rank('start failed',[route])[0]['id']=='start'
        assert router.rank('unrelated banana',[route])==[]
        cases+=['chinese_symptom_routed','english_symptom_routed','unknown_query_no_invented_location']
    actual=json.loads((ROOT/'docs/wiki/routes.json').read_text(encoding='utf8'))
    expected={'星光余额读不出来':'stars','GPU占用':'gpu','shop purchase delta':'shop','神经学习是否apply':'neural'}
    for query,identifier in expected.items():
        selected=router.rank(query,actual['routes'])[0]
        assert selected['id']==identifier,(query,selected['id'])
        assert router.resolve(ROOT,dict(actual,routes=[selected]))
        cases.append('actual_project_'+identifier)
    result=dict(passed=True,cases=cases,game_input=False,fixture_isolated=True)
    path=ROOT/'build/wiki-route-real-verification.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))

if __name__=='__main__':main()
