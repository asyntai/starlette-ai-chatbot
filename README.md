# starlette-ai-chatbot

Adds the [Asyntai](https://asyntai.com) AI chat assistant to a Starlette or
FastAPI site. The assistant answers visitor questions from your own content,
day and night, in more than 80 languages.

Free and open source. Works on every Asyntai plan, including the free plan.

- Requires Python 3.10 or newer and Starlette 0.27 or newer (any FastAPI
  version that uses it)
- Documentation: https://asyntai.com/documentation/integrations/starlette/

## Install

```
pip install starlette-ai-chatbot
```

### Starlette

```python
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette_ai_chatbot import AsyntaiWidgetMiddleware

app = Starlette(
    routes=routes,
    middleware=[
        Middleware(AsyntaiWidgetMiddleware, widget_id="asyntai_ab12cd34"),
    ],
)
```

### FastAPI

```python
from fastapi import FastAPI
from starlette_ai_chatbot import AsyntaiWidgetMiddleware

app = FastAPI()
app.add_middleware(AsyntaiWidgetMiddleware, widget_id="asyntai_ab12cd34")
```

You get the widget ID from the Install page of your
[Asyntai dashboard](https://asyntai.com/dashboard). You can paste the whole
snippet; the package keeps only the ID.

That is all. The chat button appears on every HTML page of the site. JSON,
files, streams and websockets pass through untouched.

## Options

```python
app.add_middleware(
    AsyntaiWidgetMiddleware,
    widget_id="asyntai_ab12cd34",       # without it: the ASYNTAI_WIDGET_ID environment variable
    skip_paths=["/admin*", "/docs", "/docs/oauth2-redirect", "/redoc"],  # the default
    show_to_anonymous_only=False,         # hide the chat from signed-in users
)
```

- Leave out `widget_id` to read the `ASYNTAI_WIDGET_ID` environment variable.
  It is read on every request, so you can change it without a code change.
  An empty value switches the chat off.
- `skip_paths` lists paths that never get the widget. A path that ends in `*`
  also matches everything below it. The default skips admin pages and the
  FastAPI API docs.
- `show_to_anonymous_only` needs Starlette's `AuthenticationMiddleware`.

The middleware only changes complete HTML pages with status 200 that are not
compressed. `GZipMiddleware` must run outside it, so it compresses the page
after the widget is added: in a `middleware=[...]` list, put `GZipMiddleware`
first; with `app.add_middleware(...)`, add `GZipMiddleware` last.

## Placing the widget by hand

With Jinja2 templates, register the helper once:

```python
from starlette.templating import Jinja2Templates
from starlette_ai_chatbot import asyntai_widget

templates = Jinja2Templates(directory="templates")
templates.env.globals["asyntai_widget"] = asyntai_widget
```

Then put it before the closing body tag:

```html
{{ asyntai_widget() }}
</body>
```

`widget_snippet()` returns the same HTML as a plain string. The middleware
never adds a second copy to a page that already has one.

## How it loads

The widget script loads after the page has finished loading, so your page
draws first and page speed does not change.

## License

MIT
