#asgi.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashion_app.settings')
django.setup()
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import catalog.routing


application = get_asgi_application()
application = ProtocolTypeRouter({
  "http": get_asgi_application(),
  "websocket": AuthMiddlewareStack(
    URLRouter(
      catalog.routing.websocket_urlpatterns
    )
  )
})