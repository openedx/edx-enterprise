"""
Database models for Enterprise Integrated Channel SAP SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

from config_models.models import ConfigurationModel
from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from model_utils.models import TimeFramedModel

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration


@python_2_unicode_compatible
class SAPSuccessFactorsGlobalConfiguration(ConfigurationModel):
    """
    The Global configuration for integrating with SuccessFactors.
    """

    completion_status_api_path = models.CharField(max_length=255)
    course_api_path = models.CharField(max_length=255)
    oauth_api_path = models.CharField(max_length=255)
    provider_id = models.CharField(max_length=100, default='EDX')

    class Meta:
        app_label = 'sap_success_factors'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<SAPSuccessFactorsGlobalConfiguration with id {id}>".format(
            id=self.id
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class SAPSuccessFactorsEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise specific configuration we need for integrating with SuccessFactors.
    """

    sapsf_base_url = models.CharField(max_length=255)
    key = models.CharField(max_length=255, blank=True, verbose_name="Client ID")
    secret = models.CharField(max_length=255, blank=True, verbose_name="Client Secret")

    history = HistoricalRecords()

    class Meta:
        app_label = 'sap_success_factors'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
            enterprise_name=self.enterprise_customer.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class LearnerDataTransmissionAudit(models.Model):
    """
    The payload we sent to SuccessFactors at a given point in time for an enterprise course enrollment.
    """

    enterprise_course_enrollment_id = models.PositiveIntegerField(blank=False, null=False)
    sapsf_user_id = models.CharField(max_length=255, blank=False, null=False)
    course_id = models.CharField(max_length=255, blank=False, null=False)
    course_completed = models.BooleanField(default=True)
    completed_timestamp = models.BigIntegerField()  # we send a UNIX timestamp to SuccessFactors
    instructor_name = models.CharField(max_length=255, blank=True)
    grade = models.CharField(max_length=100, blank=False, null=False)
    status = models.CharField(max_length=100, blank=False, null=False)
    error_message = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'sap_success_factors'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return '<LearnerDataTransmissionAudit {} for enterprise enrollment {}, SAP user {}, and course {}>'.format(
            self.id,
            self.enterprise_course_enrollment_id,
            self.sapsf_user_id,
            self.course_id
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class CatalogTransmissionAudit(TimeFramedModel):
    """
    The summary of instances when the course catalog was sent to SuccessFactors for an enterprise.
    """

    enterprise_customer_uuid = models.UUIDField(blank=False, null=False)
    total_courses = models.PositiveIntegerField(blank=False, null=False)
    status = models.CharField(max_length=100, blank=False, null=False)
    error_message = models.TextField(blank=True)

    class Meta:
        app_label = 'sap_success_factors'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<CatalogTransmissionAudit {} for Enterprise {}> for {} courses>".format(
            self.id,
            self.enterprise_customer_uuid,
            self.total_courses
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()
