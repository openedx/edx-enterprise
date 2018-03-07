# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel CSOD Web Services.
"""

from __future__ import absolute_import, unicode_literals

import json
from logging import getLogger

from config_models.models import ConfigurationModel
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration
from integrated_channels.sap_success_factors.exporters.content_metadata import SapSuccessFactorsContentMetadataExporter
from integrated_channels.sap_success_factors.exporters.learner_data import SapSuccessFactorsLearnerExporter
from integrated_channels.sap_success_factors.transmitters.content_metadata import SapSuccessFactorsContentMetadataTransmitter
from integrated_channels.sap_success_factors.transmitters.learner_data import SapSuccessFactorsLearnerTransmitter
from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

LOGGER = getLogger(__name__)


@python_2_unicode_compatible
class CSODWebServicesGlobalConfiguration(ConfigurationModel):
    """
    The global configuration for integrating with Cornerstone.
    """

    class Meta:
        app_label = 'csod_web_services'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return "<CSODWebServicesGlobalConfiguration with id {id}>".format(id=self.id)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class CSODWebServicesEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Cornerstone.
    """

    history = HistoricalRecords()

    class Meta:
        app_label = 'csod_web_services'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<CSODWebServicesEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
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
        return 'CSODWS'


    def get_learner_data_transmitter(self):
        """
        Return a ``CornerstoneLearnerTransmitter`` instance.
        """
        return SapSuccessFactorsLearnerTransmitter(self)

    def get_learner_data_exporter(self, user):
        """
        Return a ``CornerstoneLearnerDataExporter`` instance.
        """
        return SapSuccessFactorsLearnerExporter(user, self)

    def get_content_metadata_transmitter(self):
        """
        Return a ``CornerstoneContentMetadataTransmitter`` instance.
        """
        return SapSuccessFactorsContentMetadataTransmitter(self)

    def get_content_metadata_exporter(self, user):
        """
        Return a ``CornerstoneContentMetadataExporter`` instance.
        """
        return SapSuccessFactorsContentMetadataExporter(user, self)


@python_2_unicode_compatible
class CSODWebServicesLearnerDataTransmissionAudit(models.Model):
    """
    The payload we sent to Cornerstone at a given point in time for an enterprise course enrollment.
    """

    # Request-related information.
    status = models.CharField(max_length=100, blank=False, null=False)
    error_message = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'csod_web_services'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<CSODWebServicesLearnerDataTransmissionAudit {transmission_id} for enterprise enrollment '
            '{enterprise_course_enrollment_id}, Cornerstone user {sapsf_user_id}, and course {course_id}>'.format(
                transmission_id=self.id,
                enterprise_course_enrollment_id=self.enterprise_course_enrollment_id,
                sapsf_user_id=self.sapsf_user_id,
                course_id=self.course_id
            )
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    def serialize(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Return a JSON-serialized representation.

        Sort the keys so the result is consistent and testable.

        # TODO: When we refactor to use a serialization flow consistent with how course metadata
        # is serialized, remove the serialization here and make the learner data exporter handle the work.
        """
        return json.dumps(self._payload_data(), sort_keys=True)

    def _payload_data(self):
        """
        Convert the audit record's fields into Cornerstone key/value pairs.
        """
        return dict()
