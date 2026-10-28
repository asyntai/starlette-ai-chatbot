import pytest

fastapi = pytest.importorskip('fastapi')

from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from starlette_ai_chatbot import AsyntaiWidgetMiddleware  # noqa: E402


def make_app():
    app = fastapi.FastAPI()
    app.add_middleware(AsyntaiWidgetMiddleware, widget_id='asyntai_ab12cd34')

    @app.get('/', response_class=HTMLResponse)
    def home():
        return '<html><body><h1>FastAPI</h1></body></html>'

    @app.get('/api/items')
    def items():
        return [{'id': 1}]

    return app


def test_fastapi_html_page_gets_the_widget():
    text = TestClient(make_app()).get('/').text
    assert 'data-asyntai-widget="asyntai_ab12cd34"' in text


def test_fastapi_json_is_left_alone():
    assert TestClient(make_app()).get('/api/items').json() == [{'id': 1}]


def test_fastapi_with_gzip_added_last():
    from starlette.middleware.gzip import GZipMiddleware

    app = make_app()
    app.add_middleware(GZipMiddleware, minimum_size=10)
    response = TestClient(app).get('/', headers={'accept-encoding': 'gzip'})
    assert response.headers.get('content-encoding') == 'gzip'
    assert 'data-asyntai-widget="asyntai_ab12cd34"' in response.text


def test_fastapi_api_docs_are_left_alone():
    client = TestClient(make_app())
    assert 'asyntai' not in client.get('/docs').text
    assert 'asyntai' not in client.get('/redoc').text
