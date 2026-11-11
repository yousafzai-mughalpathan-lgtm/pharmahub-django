from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'

    # 🔽 Bas yeh ready function niche add kar dein
    def ready(self):
        import orders.signals  # Yeh app start hote hi signals ko active kar dega