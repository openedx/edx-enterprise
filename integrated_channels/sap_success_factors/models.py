"""
Database models for Enterprise Integrated Channel SAP SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

import json
from datetime import datetime
from config_models.models import ConfigurationModel
from simple_history.models import HistoricalRecords

from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible

from model_utils.models import TimeFramedModel

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration
from integrated_channels.sap_success_factors.utils import SapCourseExporter
from .transmitters.courses import SuccessFactorsCourseTransmitter
from .transmitters.learner_data import SuccessFactorsLearnerDataTransmitter


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

    key = models.CharField(max_length=255, blank=True, verbose_name="Client ID")
    sapsf_base_url = models.CharField(max_length=255, verbose_name="SAP Base URL")
    sapsf_company_id = models.CharField(max_length=255, blank=True, verbose_name="SAP Company ID")
    sapsf_user_id = models.CharField(max_length=255, blank=True, verbose_name="SAP User ID")
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

    @staticmethod
    def channel_code():
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        return 'SAP'

    def get_learner_data(self, enterprise_enrollment, certificate):
        """
        Returns a LearnerDataTransmissionAudit initialized from the given enrollment and certificate data.
        """
        return LearnerDataTransmissionAudit(
            enterprise_enrollment=enterprise_enrollment,
            certificate=certificate,
            # Used only if certificate is None
            course_completed=False,
        )

    def get_learner_data_transmitter(self):
        """
        Returns a SuccessFactorsLearnerDataTransmitter instance.
        """
        return SuccessFactorsLearnerDataTransmitter(self)

    def get_course_data_exporter(self, user):
        """
        Returns a SapCourseExporter instance.
        """
        return SapCourseExporter(user, self)

    def get_course_data_transmitter(self):
        """
        Returns a SuccessFactorsCourseTransmitter instance.
        """
        return SuccessFactorsCourseTransmitter(self)


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

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    class Meta:
        app_label = 'sap_success_factors'

    def __init__(self, *args, **kwargs):
        """
        Return a new ``LearnerDataTransmissionAudit`` object.

        Optional arguments:
        * ``enterprise_enrollment``: If provided, then ``enterprise_course_enrollment_id``, ``user_id``, * ``course_id``
          are pulled from this EnterpriseCourseEnrollment object.
        * ``certificate``: If provided, then ``course_completed=True``; ``completed_timestamp`, ``grade``
          are pulled from this GeneratedCertificate object.

        Otherwise, the field values are pulled directly from the kwargs, as usual.
        """
        enterprise_enrollment = kwargs.pop('enterprise_enrollment', None)
        if enterprise_enrollment is not None:
            kwargs['enterprise_course_enrollment_id'] = enterprise_enrollment.id
            kwargs['sapsf_user_id'] = enterprise_enrollment.enterprise_customer_user.get_remote_id()
            kwargs['course_id'] = enterprise_enrollment.course_id

        certificate = kwargs.pop('certificate', None)
        if certificate is not None:
            kwargs['course_completed'] = True
            kwargs['completed_timestamp'] = int((certificate.created_date - self.epoch).total_seconds())
            kwargs['grade'] = certificate.grade

        super(LearnerDataTransmissionAudit, self).__init__(*args, **kwargs)

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

    @property
    def provider_id(self):
        '''
        Fetch ``provider_id`` from global configuration settings
        '''
        return SAPSuccessFactorsGlobalConfiguration.current().provider_id

    def _payload_data(self, empty_value):
        """
        Convert the audit record's fields into SAP SuccessFactors key/value pairs.
        """
        return dict(
            userID=self.sapsf_user_id,
            courseID=self.course_id,
            providerID=self.provider_id,
            # SAP SuccessFactors requires strings, not boolean values.
            courseCompleted="true" if self.course_completed else "false",
            completedTimestamp=self.completed_timestamp,
            grade=self.grade,
            # TODO: determine these values from the enrollment seat?
            price=empty_value,
            currency=empty_value,
            creditHours=empty_value,
            # These fields currently have no edX source, so remain empty.
            totalHours=empty_value,
            contactHours=empty_value,
            cpeHours=empty_value,
            instructorName=empty_value,
            comments=empty_value,
        )

    def serialize(self, empty_value=''):
        """
        Return a JSON-serialized representation.

        Sort the keys so the result is consistent and testable.
        """
        return json.dumps(self._payload_data(empty_value=empty_value), sort_keys=True)


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
