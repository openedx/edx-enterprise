# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel.
"""
from __future__ import absolute_import, unicode_literals

import logging

from django.db import models

from model_utils.models import TimeStampedModel

from enterprise.models import EnterpriseCustomer

LOGGER = logging.getLogger(__name__)


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
