from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_panel'

    def ready(self):
        # import signal handlers to ensure they're registered
        from . import signals  # noqa: F401
