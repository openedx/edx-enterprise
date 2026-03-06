"""
Enterprise Integrated Channel Django application initialization.
"""

from django.apps import AppConfig


class IntegratedChannelConfig(AppConfig):
    """
    Configuration for the Enterprise Integrated Channel Django application.
    """
    name = 'channel_integrations.integrated_channel'
    verbose_name = "Enterprise Integrated Channels"

    # TODO: We should move these integrated-channel-specific retirement handlers to the edx-integrated-channels repository
    def ready(self):
        """
        Perform one-time initialization: connect signal handlers.
        """
        import integrated_channels.integrated_channel.signals  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
