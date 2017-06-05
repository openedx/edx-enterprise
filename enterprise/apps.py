# -*- coding: utf-8 -*-
"""
Enterprise Django application initialization.
"""

from __future__ import absolute_import, unicode_literals

from django.apps import AppConfig, apps
from django.conf import settings

from enterprise.constants import USER_POST_SAVE_DISPATCH_UID


class EnterpriseConfig(AppConfig):
    """
    Configuration for the enterprise Django application.
    """

    name = "enterprise"
    valid_image_extensions = [".png", ]
    valid_max_image_size = getattr(settings, 'ENTERPRISE_CUSTOMER_LOGO_IMAGE_SIZE', 512)  # Value in KB's

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
        from enterprise.signals import handle_user_post_save
        from django.db.models.signals import pre_migrate, post_save

        post_save.connect(handle_user_post_save, sender=self.auth_user_model, dispatch_uid=USER_POST_SAVE_DISPATCH_UID)
        pre_migrate.connect(self._disconnect_user_post_save_for_migrations)

    def _disconnect_user_post_save_for_migrations(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle pre_migrate signal - disconnect User post_save handler.
        """
        from django.db.models.signals import post_save
        post_save.disconnect(sender=self.auth_user_model, dispatch_uid=USER_POST_SAVE_DISPATCH_UID)
