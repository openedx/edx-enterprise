"""
Enterprise Django application initialization.
"""

from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models.signals import post_save, pre_migrate

from enterprise.constants import (
    COURSE_ASSESSMENT_GRADE_CHANGED_DISPATCH_UID,
    COURSE_GRADE_NOW_PASSED_DISPATCH_UID,
    SAML_ACCOUNT_DISCONNECTED_DISPATCH_UID,
    UNENROLL_DONE_DISPATCH_UID,
    USER_POST_SAVE_DISPATCH_UID,
)


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
        # Importing this module also connects its @receiver-decorated handlers.
        from enterprise.signals import (  # pylint: disable=import-outside-toplevel
            create_enterprise_enrollment_receiver,
            handle_enterprise_learner_passing_grade,
            handle_enterprise_learner_subsection,
            handle_social_auth_disconnect,
            handle_user_post_save,
            refund_order_voucher,
            retire_user_from_pending_enterprise_customer_user,
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

        try:
            # pylint: disable=import-outside-toplevel
            from common.djangoapps.student.models import CourseEnrollment
            from openedx.core.djangoapps.user_api.accounts.signals import USER_RETIRE_LMS_CRITICAL
        except ImportError:
            pass
        else:
            post_save.connect(create_enterprise_enrollment_receiver, sender=CourseEnrollment)
            USER_RETIRE_LMS_CRITICAL.connect(retire_user_from_pending_enterprise_customer_user)

        # Learner grade and unenrollment events are only handled in the LMS, never in Studio.
        if getattr(settings, 'SERVICE_VARIANT', None) == 'lms':
            try:
                # pylint: disable=import-outside-toplevel
                from common.djangoapps.student.signals import UNENROLL_DONE
                from openedx.core.djangoapps.signals.signals import (
                    COURSE_ASSESSMENT_GRADE_CHANGED,
                    COURSE_GRADE_NOW_PASSED,
                )
            except ImportError:
                pass
            else:
                COURSE_GRADE_NOW_PASSED.connect(
                    handle_enterprise_learner_passing_grade,
                    dispatch_uid=COURSE_GRADE_NOW_PASSED_DISPATCH_UID,
                )
                COURSE_ASSESSMENT_GRADE_CHANGED.connect(
                    handle_enterprise_learner_subsection,
                    dispatch_uid=COURSE_ASSESSMENT_GRADE_CHANGED_DISPATCH_UID,
                )
                UNENROLL_DONE.connect(
                    refund_order_voucher,
                    dispatch_uid=UNENROLL_DONE_DISPATCH_UID,
                )

    def _disconnect_user_post_save_for_migrations(self, sender, **kwargs):  # pylint: disable=unused-argument
        """
        Handle pre_migrate signal - disconnect User post_save handler.
        """
        post_save.disconnect(sender=self.auth_user_model, dispatch_uid=USER_POST_SAVE_DISPATCH_UID)
