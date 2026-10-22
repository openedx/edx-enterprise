"""edX Enterprise's Consent application.

This application provides a generic Consent API that lets the
user get, provide, and revoke consent to an enterprise customer
at some gate.
"""

from django.apps import AppConfig


class ConsentConfig(AppConfig):
    """Configuration for edX Enterprise's Consent application."""

    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "common": {
                    "relative_path": "settings.common",
                },
                "production": {
                    "relative_path": "settings.production",
                },
            },
        },
    }

    name = 'consent'
    verbose_name = "Enterprise Consent"

    def ready(self):
        """
        Perform one-time initialization: connect signal handlers.
        """
        import consent.signals  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
