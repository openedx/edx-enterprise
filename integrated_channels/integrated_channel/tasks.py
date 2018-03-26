"""
Celery tasks for integrated channel management commands.
"""

from __future__ import absolute_import, unicode_literals

import time

from celery import shared_task
from celery.utils.log import get_task_logger

from django.contrib.auth.models import User

from integrated_channels.integrated_channel.management.commands import INTEGRATED_CHANNEL_CHOICES

LOGGER = get_task_logger(__name__)


@shared_task
def transmit_content_metadata(username, channel_code, channel_pk):
    """
    Task to send content metadata to each linked integrated channel.

    Arguments:
        username (str): The username of the User to be used for making API requests to retrieve content metadata.
        channel_code (str): Capitalized identifier for the integrated channel.
        channel_pk (str): Primary key for identifying integrated channel.

    """
    start = time.time()
    api_user = User.objects.get(username=username)
    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)
    LOGGER.info('Transmitting content metadata to integrated channel using configuration: [%s]', integrated_channel)
    try:
        integrated_channel.transmit_content_metadata(api_user)
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception(
            'Transmission of content metadata failed for user [%s] and for integrated '
            'channel with code [%s] and id [%s].', username, channel_code, channel_pk
        )
    duration = time.time() - start
    LOGGER.info(
        'Content metadata transmission task for integrated channel configuration [%s] took [%s] seconds',
        integrated_channel,
        duration
    )


@shared_task
def transmit_learner_data(username, channel_code, channel_pk):
    """
    Task to send learner data to each linked integrated channel.

    Arguments:
        username (str): The username of the User to be used for making API requests for learner data.
        channel_code (str): Capitalized identifier for the integrated channel
        channel_pk (str): Primary key for identifying integrated channel

    """
    start = time.time()
    api_user = User.objects.get(username=username)
    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)
    LOGGER.info('Processing learners for integrated channel using configuration: [%s]', integrated_channel)

    # Note: learner data transmission code paths don't raise any uncaught exception, so we don't need a broad
    # try-except block here.
    integrated_channel.transmit_learner_data(api_user)

    duration = time.time() - start
    LOGGER.info(
        'Learner data transmission task for integrated channel configuration [%s] took [%s] seconds',
        integrated_channel,
        duration
    )
