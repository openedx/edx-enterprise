"""
Celery tasks for integrated channel management commands.
"""

from __future__ import absolute_import, unicode_literals

import time

from celery import shared_task
from celery.utils.log import get_task_logger

from django.contrib.auth.models import User
from django.utils import timezone

from integrated_channels.integrated_channel.management.commands import (
    INTEGRATED_CHANNEL_CHOICES,
    IntegratedChannelCommandUtils,
)

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


@shared_task
def transmit_single_learner_data(username, course_run_id):
    """
    Task to send single learner data to each linked integrated channel.

    Arguments:
        username (str): The username of the learner whose data it should send.
        course_run_id (str): The course run id of the course it should send data for.
    """
    start = time.time()
    user = User.objects.get(username=username)
    LOGGER.info('Started transmitting single learner data for user: [%s] and course [%s]', username, course_run_id)
    channel_utils = IntegratedChannelCommandUtils()
    # Transmit the learner data to each integrated channel
    for channel in channel_utils.get_integrated_channels({'channel': None}):
        integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel.channel_code()].objects.get(pk=channel.pk)
        LOGGER.info(
            'Processing learner [%s] for integrated channel using configuration: [%s]', user.id, integrated_channel
        )
        integrated_channel.transmit_single_learner_data(
            learner_to_transmit=user,
            course_run_id=course_run_id,
            completed_date=timezone.now(),
            grade='Pass',
            is_passing=True
        )

    duration = time.time() - start
    LOGGER.info(
        'Learner data transmission task for user: [%s] and course [%s] took [%s] seconds',
        username,
        course_run_id,
        duration
    )


@shared_task
def unlink_inactive_learners(channel_code, channel_pk):
    """
    Task to unlink inactive learners of provided integrated channel.

    Arguments:
        channel_code (str): Capitalized identifier for the integrated channel
        channel_pk (str): Primary key for identifying integrated channel

    """
    start = time.time()
    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)
    LOGGER.info('Processing learners to unlink inactive users using configuration: [%s]', integrated_channel)

    # Note: learner data transmission code paths don't raise any uncaught exception, so we don't need a broad
    # try-except block here.
    integrated_channel.unlink_inactive_learners()

    duration = time.time() - start
    LOGGER.info(
        'Unlink inactive learners task for integrated channel configuration [%s] took [%s] seconds',
        integrated_channel,
        duration
    )
