"""
Database models for Enterprise Integrated Channel.
"""
from __future__ import absolute_import, unicode_literals
import logging

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from model_utils.models import TimeStampedModel

from enterprise.models import EnterpriseCustomer


LOGGER = logging.getLogger(__name__)


@python_2_unicode_compatible
class EnterpriseIntegratedChannel(TimeStampedModel):
    """
    Store information related to integrating with external enterprise systems.

    EnterpriseIntegratedChannel is an external system that the Enterprise Customer uses to manage enterprise
    related data. Each of these requires an edx plugin in order to send data to these systems, this model stores
    information related to what and where to send data from the enterprise app.
    """

    name = models.CharField(max_length=255, blank=False, null=False, help_text=_("Third Party name."))
    data_type = models.CharField(max_length=100, blank=False, null=False, help_text=_("Data Type"))

    class Meta:
        app_label = 'integrated_channel'
        verbose_name = _("Enterprise Integrated Channel")
        verbose_name_plural = _("Enterprise Integrated Channels")
        unique_together = (("name", "data_type"),)

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseIntegratedChannel {name} for {data_type} data with id {id}>".format(
            name=self.name,
            data_type=self.data_type,
            id=self.id
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class EnterpriseCustomerPluginConfiguration(TimeStampedModel):
    """
    Abstract base class for information related to integrating with external systems for an enterprise customer.

    EnterpriseCustomerPluginConfiguration will be extended by the configuration models in other integrated channel's
    apps to provide uniformity across different integrated channels.
    """

    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer, blank=False, null=False
    )
    active = models.BooleanField(blank=False, null=False)

    class Meta:
        abstract = True

    @staticmethod
    def channel_code():
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        raise NotImplementedError('Implemented in concrete subclass.')

    def get_learner_data_record(self, enterprise_enrollment, completed_date=None, grade=None, is_passing=False):
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        raise NotImplementedError('Implemented in concrete subclass.')

    def get_learner_data_exporter(self, user):
        """
        Returns the class that can serialize the learner course completion data to the integrated channel.
        """
        raise NotImplementedError('Implemented in concrete subclass.')

    def get_learner_data_transmitter(self):
        """
        Returns the class that can transmit the learner course completion data to the integrated channel.
        """
        raise NotImplementedError("Implemented in concrete subclass.")

    def transmit_learner_data(self, user):
        """
        Iterate over each learner data record and transmit it to the integrated channel.
        """
        exporter = self.get_learner_data_exporter(user)
        transmitter = self.get_learner_data_transmitter()
        for learner_data in exporter.collect_learner_data():
            transmitter.transmit(learner_data)

    def get_course_data_exporter(self, user):
        """
        Returns a class that can retrieve, transform, and serialize the courseware data to the integrated channel.
        """
        raise NotImplementedError("Implemented in concrete subclass.")

    def get_course_data_transmitter(self):
        """
        Returns a class that can transmit the courseware data to the integrated channel.
        """
        raise NotImplementedError("Implemented in concrete subclass.")

    def transmit_course_data(self, user):
        """
        Compose the details from the concrete subclass to transmit the relevant data.
        """
        course_data_exporter = self.get_course_data_exporter(user)
        transmitter = self.get_course_data_transmitter()
        transmitter.transmit(course_data_exporter)
