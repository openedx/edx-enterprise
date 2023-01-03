"""
Models for xAPI.
"""

import base64

from django.contrib import auth
from django.db import models
from django.utils.translation import gettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise.models import EnterpriseCustomer
from integrated_channels.integrated_channel.models import LearnerDataTransmissionAudit

User = auth.get_user_model()


class XAPILRSConfiguration(TimeStampedModel):
    """
    xAPI LRS configurations.

    .. no_pii:
    """

    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer,
        blank=False,
        null=False,
        help_text=_('Enterprise Customer associated with the configuration.'),
        on_delete=models.deletion.CASCADE
    )
    version = models.CharField(max_length=16, default='1.0.1', help_text=_('Version of xAPI.'))
    endpoint = models.URLField(help_text=_('URL of the LRS.'))
    key = models.CharField(max_length=255, verbose_name="Client ID", help_text=_('Key of xAPI LRS.'))
    secret = models.CharField(max_length=255, verbose_name="Client Secret", help_text=_('secret of xAPI LRS.'))
    active = models.BooleanField(
        blank=False,
        null=False,
        help_text=_('Is this configuration active?'),
    )

    class Meta:
        app_label = 'xapi'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return '<XAPILRSConfiguration for Enterprise {enterprise_name}>'.format(
            enterprise_name=self.enterprise_customer.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    @property
    def authorization_header(self):
        """
        Authorization header for authenticating requests to LRS.
        """
        return 'Basic {}'.format(
            base64.b64encode('{key}:{secret}'.format(key=self.key, secret=self.secret).encode()).decode()
        )


class XAPILearnerDataTransmissionAudit(LearnerDataTransmissionAudit):
    """
    The payload we sent to XAPI at a given point in time for an enterprise course enrollment.

    .. no_pii:
    """

    user = models.ForeignKey(
        User,
        blank=False,
        null=False,
        related_name='xapi_transmission_audit',
        on_delete=models.CASCADE,
    )

    class Meta:
        app_label = 'xapi'
        unique_together = ("user", "course_id")
        index_together = ['enterprise_customer_uuid', 'plugin_configuration_id']

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<XAPILearnerDataTransmissionAudit {transmission_id} for enterprise enrollment '
            '{enterprise_course_enrollment_id}, XAPI user {user_id}, and course {course_id}>'.format(
                transmission_id=self.id,
                enterprise_course_enrollment_id=self.enterprise_course_enrollment_id,
                user_id=self.user.id,
                course_id=self.course_id
            )
        )
