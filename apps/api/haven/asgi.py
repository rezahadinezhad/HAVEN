import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "haven.settings")
from django.core.asgi import get_asgi_application

django_app = get_asgi_application()
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402 -- Django must initialize before importing model-backed consumers
from django.urls import path  # noqa: E402 -- Django must initialize before importing model-backed consumers
from core.consumers import SyncConsumer  # noqa: E402 -- Django must initialize before importing model-backed consumers

application = ProtocolTypeRouter(
    {"http": django_app, "websocket": URLRouter([path("ws/v1", SyncConsumer.as_asgi())])}
)
