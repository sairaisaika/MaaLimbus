from maalimbus.releases import ReleaseClient
from maalimbus.github_cache import GitHubState


def test_http_etag_rate_limit_restart_and_deadline_resume(tmp_path):
    calls=[]
    responses=iter([(200,{'ETag':'"v1"'},{'tag_name':'v0.1.0','assets':[]}),
                    (304,{},None),(403,{'X-RateLimit-Remaining':'0','X-RateLimit-Reset':'9000'},None),
                    (200,{}, {'tag_name':'v0.2.0','assets':[]})])
    def request(url,headers,proxy):
        calls.append((url,headers));return next(responses)
    path=tmp_path/'state.json'
    client=ReleaseClient(path,transport=request)
    assert client.check(0)['status']=='available'
    assert not ReleaseClient(path,transport=request).check(3599)['requested']
    assert client.check(3600)['status']=='cached'
    assert calls[1][1]['If-None-Match']=='"v1"'
    assert client.check(7200)['status']=='rate_limited'
    assert not ReleaseClient(path,transport=request).check(9004)['requested']
    assert ReleaseClient(path,transport=request).check(9005)['release']['tag_name']=='v0.2.0'
    assert len(calls)==4


def test_forbidden_is_not_a_rate_limit_and_no_release_invalidates_old_cache(tmp_path):
    state=GitHubState(payload={'tag_name':'old'},etag='old')
    state.response(403,{'X-RateLimit-Remaining':'8'},{'message':'Forbidden'},0)
    assert state.status=='access_denied'
    state.response(404,{},None,3600)
    assert state.payload is None and state.etag=='' and state.status=='no_release'


def test_transport_failure_cannot_discard_valid_cache_or_leak_proxy(tmp_path):
    path=tmp_path/'state.json'
    GitHubState(payload={'tag_name':'v1','assets':[]}).save(path)
    def fail(*args): raise OSError('secret proxy password')
    result=ReleaseClient(path,transport=fail).check(0)
    assert result['status']=='network_error' and result['release']['tag_name']=='v1'
    assert 'secret' not in path.read_text()


def test_invalid_release_does_not_replace_known_cache(tmp_path):
    path=tmp_path/'state.json'
    GitHubState(payload={'tag_name':'v1','assets':[]}).save(path)
    result=ReleaseClient(path,transport=lambda *args:(200,{}, {'html':'login'})).check(0)
    assert result['status']=='network_error' and result['release']['tag_name']=='v1'


def test_non_object_error_body_cannot_crash_rate_limit_handler():
    state=GitHubState()
    state.response(403,{},['malformed error'],0)
    assert state.status=='access_denied'
