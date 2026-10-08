from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field='django.db.models.BigAutoField'
    name='portal'

    def ready(self):
        # Import only after Django's app registry is ready so new list records receive
        # their inexpensive bounded Focus classification without coupling ingestion code.
        from . import focus_signals  # noqa: F401
        # Company identity may be repaired/enriched after initial discovery. Enforce the
        # active blacklist after every saved identity boundary, not only at first ingest.
        from . import blacklist_signals  # noqa: F401
