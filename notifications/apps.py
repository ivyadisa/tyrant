from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Notifications'

    def ready(self):
        """Import and register notification signals."""
        # This ensures signals are registered when the app is ready
        try:
            from . import signals
            signals.register_notification_signals()
        except Exception as e:
            # Log the error but don't crash startup
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to register notification signals: {e}"
            )