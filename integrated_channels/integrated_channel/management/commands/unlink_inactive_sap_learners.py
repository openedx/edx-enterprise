# -*- coding: utf-8 -*-
"""
Unlink inactive enterprise learners of SAP Success Factors from related EnterpriseCustomer(s).
"""

from __future__ import absolute_import, unicode_literals

from logging import getLogger

from django.core.management.base import BaseCommand

from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.integrated_channel.tasks import unlink_inactive_learners

LOGGER = getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Unlink inactive enterprise learners of SAP Success Factors from all related EnterpriseCustomer(s).
    """

    def handle(self, *args, **options):
        """
        Unlink inactive EnterpriseCustomer(s) SAP learners.
        """
        channels = self.get_integrated_channels(options)

        for channel in channels:
            channel_code = channel.channel_code()
            channel_pk = channel.pk
            if channel_code == 'SAP':
                # Transmit the learner data to each integrated channel
                unlink_inactive_learners.delay(channel_code, channel_pk)
