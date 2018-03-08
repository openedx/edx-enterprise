# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel Cornerstone.
"""


from __future__ import absolute_import, unicode_literals

from datetime import datetime
from logging import getLogger

from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter

from django.apps import apps

LOGGER = getLogger(__name__)


class CSODWebServicesLearnerExporter(LearnerExporter):
    """
    Class to provide a Cornerstone learner data transmission audit prepared for serialization.
    """
