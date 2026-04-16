"""
Enterprise Django application initialization.
"""

from django.apps import AppConfig, apps
from django.db.models.signals import post_save, pre_migrate

from enterprise.constants import SAML_ACCOUNT_DISCONNECTED_DISPATCH_UID, USER_POST_SAVE_DISPATCH_UID


class EnterpriseConfig(AppConfig):
    """
    Configuration for the enterprise Django application.
    """

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

    name = "enterprise"
    valid_image_extensions = [".png", ]

    @property
    def auth_user_model(self):
        """
        Return User model for django.contrib.auth.
        """
        return apps.get_app_config("auth").get_model("User")

    def ready(self):
        """
        Perform other one-time initialization steps.
        """
        from enterprise.signals import (  # pylint: disable=import-outside-toplevel
            handle_social_auth_disconnect,
            handle_user_post_save,
        )

        post_save.connect(handle_user_post_save, sender=self.auth_user_model, dispatch_uid=USER_POST_SAVE_DISPATCH_UID)
        pre_migrate.connect(self._disconnect_user_post_save_for_migrations)

        try:
            # pylint: disable=import-outside-toplevel
            from common.djangoapps.third_party_auth.signals import SAMLAccountDisconnected
        except ImportError:
            pass
        else:
            SAMLAccountDisconnected.connect(
                handle_social_auth_disconnect,
                dispatch_uid=SAML_ACCOUNT_DISCONNECTED_DISPATCH_UID,
            )

    def _disconnect_user_post_save_for_migrations(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle pre_migrate signal - disconnect User post_save handler.
        """
        post_save.disconnect(sender=self.auth_user_model, dispatch_uid=USER_POST_SAVE_DISPATCH_UID)
