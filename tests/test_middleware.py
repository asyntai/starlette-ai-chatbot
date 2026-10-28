import gzip

import pytest
from starlette.applications import Starlette
from starlette.authentication import AuthCredentials, AuthenticationBackend, SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient

from starlette_ai_chatbot import AsyntaiWidgetMiddleware
from starlette_ai_chatbot.middleware import insert_snippet, path_is_skipped

WIDGET_ID = 'asyntai_ab12cd34'
PAGE = '<html><head><title>T</title></head><body><h1>Hello</h1></body></html>'


async def home(request):
    return HTMLResponse(PAGE)


async def json_view(request):
    return JSONResponse({'ok': True})


async def text_view(request):
    return PlainTextResponse('</body>')


async def not_found(request):
    return HTMLResponse(PAGE, status_code=404)


async def no_body_tag(request):
    return HTMLResponse('<p>fragment</p>')


async def already_there(request):
    return HTMLResponse('<html><body><script data-asyntai-id="asyntai_zz99yy88" src="https://x"></script></body></html>')


async def streamed(request):
    async def parts():
        yield b'<html><body><h1>Str'
        yield b'eamed</h1>'
        yield b'</body></html>'
    return StreamingResponse(parts(), media_type='text/html')


async def latin1(request):
    return Response('<html><body>Caf\xe9</body></html>'.encode('latin-1'), media_type='text/html; charset=iso-8859-1')


async def admin(request):
    return HTMLResponse(PAGE)


async def code_sample(request):
    return HTMLResponse('<html><body><pre>&lt;/body&gt; </body> in text</pre></body></html>')


async def upper_tag(request):
    return HTMLResponse('<HTML><BODY>Big</BODY></HTML>')


async def ws(websocket):
    await websocket.accept()
    await websocket.send_text('hi')
    await websocket.close()


ROUTES = [
    Route('/', home),
    Route('/json', json_view),
    Route('/text', text_view),
    Route('/missing', not_found),
    Route('/fragment', no_body_tag),
    Route('/already', already_there),
    Route('/stream', streamed),
    Route('/latin1', latin1),
    Route('/admin', admin),
    Route('/admin/users', admin),
    Route('/administrator', admin),
    Route('/sample', code_sample),
    Route('/upper', upper_tag),
    WebSocketRoute('/ws', ws),
]


def make_client(**options):
    options.setdefault('widget_id', WIDGET_ID)
    app = Starlette(routes=ROUTES, middleware=[Middleware(AsyntaiWidgetMiddleware, **options)])
    return TestClient(app)


def test_widget_is_added_to_an_html_page():
    response = make_client().get('/')
    assert response.status_code == 200
    assert 'data-asyntai-widget="asyntai_ab12cd34"' in response.text
    assert response.text.index('asyntai-widget-config') < response.text.index('</body>')
    assert '<h1>Hello</h1>' in response.text


def test_content_length_matches_the_new_body():
    response = make_client().get('/')
    assert int(response.headers['content-length']) == len(response.content)


def test_json_and_text_are_left_alone():
    client = make_client()
    assert client.get('/json').json() == {'ok': True}
    assert client.get('/text').text == '</body>'


def test_error_pages_are_left_alone():
    assert 'asyntai' not in make_client().get('/missing').text


def test_fragment_without_body_tag_is_left_alone():
    assert make_client().get('/fragment').text == '<p>fragment</p>'


def test_hand_placed_snippet_is_not_doubled():
    text = make_client().get('/already').text
    assert 'asyntai-widget-config' not in text
    assert text.count('data-asyntai-id') == 1


def test_streamed_html_is_completed_then_changed():
    response = make_client().get('/stream')
    assert '<h1>Streamed</h1>' in response.text
    assert response.text.count('asyntai-widget-config') == 2  # the div and the selector in the script


def test_page_charset_is_kept():
    response = make_client().get('/latin1')
    assert 'Caf\xe9' in response.text
    assert 'asyntai-widget-config' in response.text


def test_only_the_last_body_tag_is_used():
    text = make_client().get('/sample').text
    assert text.index('asyntai-widget-config') > text.index('in text')


def test_upper_case_body_tag_works():
    text = make_client().get('/upper').text
    assert text.index('asyntai-widget-config') < text.index('</BODY>')


def test_admin_paths_are_skipped_by_default():
    client = make_client()
    assert 'asyntai' not in client.get('/admin').text
    assert 'asyntai' not in client.get('/admin/users').text
    assert 'asyntai-widget-config' in client.get('/administrator').text


def test_own_skip_paths_replace_the_defaults():
    client = make_client(skip_paths=['/'])
    assert 'asyntai' not in client.get('/').text
    assert 'asyntai-widget-config' in client.get('/admin').text


def test_skip_rules():
    rules = ['/admin*', '/docs']
    assert path_is_skipped('/admin', rules)
    assert path_is_skipped('/admin/x/y', rules)
    assert not path_is_skipped('/administrator', rules)
    assert path_is_skipped('/docs', rules)
    assert not path_is_skipped('/docs/getting-started', rules)


def test_bad_or_missing_id_switches_the_chat_off(monkeypatch):
    monkeypatch.delenv('ASYNTAI_WIDGET_ID', raising=False)
    assert 'asyntai' not in make_client(widget_id='nonsense').get('/').text
    assert 'asyntai' not in make_client(widget_id=None).get('/').text


def test_environment_variable_is_used_and_read_per_request(monkeypatch):
    client = make_client(widget_id=None)
    monkeypatch.setenv('ASYNTAI_WIDGET_ID', 'asyntai_env12345')
    assert 'data-asyntai-widget="asyntai_env12345"' in client.get('/').text
    monkeypatch.setenv('ASYNTAI_WIDGET_ID', '')
    assert 'asyntai' not in client.get('/').text


def test_pasted_snippet_works_as_id():
    pasted = '<script async src="https://widget.asyntai.com/static/js/chat-widget.js" data-asyntai-id="asyntai_ab12cd34"></script>'
    assert 'data-asyntai-widget="asyntai_ab12cd34"' in make_client(widget_id=pasted).get('/').text


def test_non_https_script_url_switches_the_chat_off():
    assert 'asyntai' not in make_client(script_url='http://evil.example/x.js').get('/').text


def test_custom_https_script_url_is_used():
    text = make_client(script_url='https://cdn.example.com/w.js').get('/').text
    assert 'data-asyntai-src="https://cdn.example.com/w.js"' in text


def test_head_request_is_left_alone():
    response = make_client().head('/')
    assert response.status_code == 200


def test_websocket_passes_through():
    with make_client().websocket_connect('/ws') as socket:
        assert socket.receive_text() == 'hi'


def test_works_under_gzip():
    app = Starlette(routes=ROUTES, middleware=[
        Middleware(GZipMiddleware, minimum_size=10),
        Middleware(AsyntaiWidgetMiddleware, widget_id=WIDGET_ID),
    ])
    response = TestClient(app).get('/', headers={'accept-encoding': 'gzip'})
    assert response.headers.get('content-encoding') == 'gzip'
    assert 'asyntai-widget-config' in response.text


def test_compressed_page_is_left_alone():
    async def compressed(request):
        return Response(gzip.compress(PAGE.encode()), media_type='text/html', headers={'content-encoding': 'gzip'})

    app = Starlette(routes=[Route('/', compressed)], middleware=[Middleware(AsyntaiWidgetMiddleware, widget_id=WIDGET_ID)])
    response = TestClient(app).get('/')
    assert response.text == PAGE


class _Backend(AuthenticationBackend):
    async def authenticate(self, conn):
        if conn.headers.get('x-user'):
            return AuthCredentials(['authenticated']), SimpleUser('ann')
        return None


def test_anonymous_only_hides_the_chat_from_signed_in_users():
    app = Starlette(routes=ROUTES, middleware=[
        Middleware(AuthenticationMiddleware, backend=_Backend()),
        Middleware(AsyntaiWidgetMiddleware, widget_id=WIDGET_ID, show_to_anonymous_only=True),
    ])
    client = TestClient(app)
    assert 'asyntai-widget-config' in client.get('/').text
    assert 'asyntai' not in client.get('/', headers={'x-user': '1'}).text


def test_insert_snippet_refuses_unreadable_pages():
    assert insert_snippet(b'<body>\xff</body>', 'x', 'utf-8') is None
    assert insert_snippet(b'<body></body>', 'x', 'no-such-charset') is None


@pytest.mark.parametrize('path', ['/', '/stream', '/upper'])
def test_widget_is_added_once(path):
    text = make_client().get(path).text
    assert text.count('class="asyntai-widget-config"') == 1
