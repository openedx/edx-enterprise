"""
Enterprise Django application initialization.
"""

from django.apps import AppConfig, apps

from enterprise.constants import USER_POST_SAVE_DISPATCH_UID


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
        from enterprise.signals import handle_user_post_save  # pylint: disable=import-outside-toplevel

        from django.db.models.signals import post_save, pre_migrate  # pylint: disable=C0415, # isort:skip

        post_save.connect(handle_user_post_save, sender=self.auth_user_model, dispatch_uid=USER_POST_SAVE_DISPATCH_UID)
        pre_migrate.connect(self._disconnect_user_post_save_for_migrations)

    def _disconnect_user_post_save_for_migrations(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle pre_migrate signal - disconnect User post_save handler.
        """
        from django.db.models.signals import post_save  # pylint: disable=import-outside-toplevel
        post_save.disconnect(sender=self.auth_user_model, dispatch_uid=USER_POST_SAVE_DISPATCH_UID)
