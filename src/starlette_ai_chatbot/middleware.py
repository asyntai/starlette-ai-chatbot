"""Puts the chat widget on every HTML page, with no template edit.

This is a plain ASGI middleware, so it works with Starlette, FastAPI and any
other ASGI framework. It only touches complete, uncompressed HTML pages with
status 200. Everything else (JSON, files, streams, websockets) passes through
untouched.
"""
from starlette.datastructures import MutableHeaders

from .snippet import MARKER, resolve_widget_id, widget_snippet
from .utils import clean_script_url

BODY_CLOSE = b'</body>'

#: Paths the widget never touches by default: admin areas and the FastAPI
#: API docs. A path that ends in * matches everything below it.
DEFAULT_SKIP_PATHS = ('/admin*', '/docs', '/docs/oauth2-redirect', '/redoc')


def path_is_skipped(path, skip_paths):
    """Answer whether the widget must stay off on this path."""
    for rule in skip_paths:
        if rule.endswith('*'):
            base = rule[:-1].rstrip('/')
            if path == base or path.startswith(base + '/'):
                return True
        elif path == rule:
            return True
    return False


def _charset(content_type):
    for part in content_type.split(';')[1:]:
        key, _, value = part.partition('=')
        if key.strip().lower() == 'charset' and value.strip():
            return value.strip().strip('"')
    return 'utf-8'


def insert_snippet(body, snippet, charset='utf-8'):
    """Return the page with the snippet before the last </body>, or None.

    None means "leave the page as it is": the page has no closing body tag,
    it already carries the widget, or it is not readable text.
    """
    if MARKER.encode() in body or b'data-asyntai-id' in body:
        return None

    if BODY_CLOSE not in body.lower():
        return None

    try:
        html = body.decode(charset)
        encoded_snippet = snippet.encode(charset)
    except (UnicodeError, LookupError):
        return None

    # Split on the last closing tag, so a page that prints the tag inside an
    # example or a code block is left alone.
    index = html.lower().rfind('</body>')
    if index < 0:
        return None
    return html[:index].encode(charset) + encoded_snippet + html[index:].encode(charset)


class AsyntaiWidgetMiddleware:
    """Inserts the widget just before the closing body tag.

    widget_id                 the ID from the Asyntai dashboard; without it,
                              the ASYNTAI_WIDGET_ID environment variable
    skip_paths                paths the widget never touches
    show_to_anonymous_only    hide the chat from signed-in users (needs
                              Starlette's AuthenticationMiddleware)
    script_url                change only if Asyntai support asks
    """

    def __init__(self, app, widget_id=None, skip_paths=DEFAULT_SKIP_PATHS,
                 show_to_anonymous_only=False, script_url=None):
        self.app = app
        self.widget_id = widget_id
        self.skip_paths = tuple(skip_paths or ())
        self.show_to_anonymous_only = show_to_anonymous_only
        self.script_url = script_url

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') == 'HEAD':
            await self.app(scope, receive, send)
            return

        if path_is_skipped(scope.get('path') or '/', self.skip_paths):
            await self.app(scope, receive, send)
            return

        if self.show_to_anonymous_only and _is_signed_in(scope):
            await self.app(scope, receive, send)
            return

        # The environment variable is read on every request, so a project can
        # change the ID without a code change.
        if not resolve_widget_id(self.widget_id) or not clean_script_url(self.script_url):
            await self.app(scope, receive, send)
            return

        await _Responder(self, send).run(scope, receive)


class _Responder:
    """Holds one HTML response until it is complete, then adds the widget."""

    def __init__(self, middleware, send):
        self.middleware = middleware
        self.send = send
        self.start_message = None
        self.chunks = []

    async def run(self, scope, receive):
        await self.middleware.app(scope, receive, self.wrapped_send)

    async def wrapped_send(self, message):
        kind = message['type']

        if kind == 'http.response.start':
            if self._can_carry_widget(message):
                self.start_message = message
                return
            await self.send(message)
            return

        if self.start_message is None:
            await self.send(message)
            return

        if kind != 'http.response.body':
            # Something we cannot change, such as a file sent by path:
            # release the held headers and pass it on.
            await self._flush_untouched()
            await self.send(message)
            return

        self.chunks.append(message.get('body', b''))
        if message.get('more_body', False):
            return

        await self._finish()

    def _can_carry_widget(self, message):
        if message.get('status') != 200:
            return False

        headers = MutableHeaders(raw=list(message.get('headers', [])))
        if headers.get('content-encoding'):
            return False

        content_type = headers.get('content-type', '')
        return content_type.split(';')[0].strip().lower() == 'text/html'

    async def _flush_untouched(self):
        start = self.start_message
        self.start_message = None
        await self.send(start)
        if self.chunks:
            await self.send({'type': 'http.response.body', 'body': b''.join(self.chunks), 'more_body': True})
            self.chunks = []

    async def _finish(self):
        start = self.start_message
        body = b''.join(self.chunks)
        self.start_message = None
        self.chunks = []

        headers = MutableHeaders(raw=list(start.get('headers', [])))
        snippet = widget_snippet(self.middleware.widget_id, self.middleware.script_url)
        new_body = insert_snippet(body, snippet, _charset(headers.get('content-type', ''))) if snippet else None

        if new_body is not None:
            body = new_body
            if 'content-length' in headers:
                headers['content-length'] = str(len(body))
            start = dict(start)
            start['headers'] = headers.raw

        await self.send(start)
        await self.send({'type': 'http.response.body', 'body': body, 'more_body': False})


def _is_signed_in(scope):
    user = scope.get('user')
    return bool(user is not None and getattr(user, 'is_authenticated', False))
