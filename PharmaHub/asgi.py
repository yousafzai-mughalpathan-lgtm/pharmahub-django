"""
ASGI config for PharmaHub project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PharmaHub.settings')

# Import consumers here to avoid circular imports
from admin_panel.consumers import NotifyConsumer

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter([
            # single endpoint used by all roles
            path('ws/notifications/', NotifyConsumer.as_asgi()),
        ])
    ),
})
