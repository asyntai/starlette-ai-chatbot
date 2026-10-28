"""Adds the Asyntai AI chat assistant to Starlette and FastAPI sites."""
from .middleware import DEFAULT_SKIP_PATHS, AsyntaiWidgetMiddleware
from .snippet import asyntai_widget, widget_snippet

__all__ = ['AsyntaiWidgetMiddleware', 'DEFAULT_SKIP_PATHS', 'asyntai_widget', 'widget_snippet']
__version__ = '1.0.0'
