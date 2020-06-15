"""
Celery tasks for integrated channel management commands.
"""

import time

from celery import shared_task
from celery.utils.log import get_task_logger

from django.contrib.auth.models import User
from django.utils import timezone

from enterprise.utils import get_enterprise_customer_for_user
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
    LOGGER.info('[Integrated Channel] Content metadata transmission started.'
                ' Configuration: {configuration}'.format(configuration=integrated_channel))
    try:
        integrated_channel.transmit_content_metadata(api_user)
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception(
            '[Integrated Channel] Transmission of content metadata failed.'
            ' ChannelCode: {channel_code}, ChannelId: {channel_id}, Username: {user}'.format(
                user=username,
                channel_code=channel_code,
                channel_id=channel_pk
            ))
    duration = time.time() - start
    LOGGER.info(
        '[Integrated Channel] Content metadata transmission task finished. Configuration: {configuration},'
        'Duration: {duration}'.format(
            configuration=integrated_channel,
            duration=duration
        ))


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
    LOGGER.info('[Integrated Channel] Batch processing learners for integrated channel.'
                ' Configuration: {configuration}'.format(configuration=integrated_channel))

    # Note: learner data transmission code paths don't raise any uncaught exception, so we don't need a broad
    # try-except block here.
    integrated_channel.transmit_learner_data(api_user)

    duration = time.time() - start
    LOGGER.info(
        '[Integrated Channel] Batch learner data transmission task finished. Configuration: {configuration},'
        ' Duration: {duration}'.format(
            configuration=integrated_channel,
            duration=duration
        ))


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
    LOGGER.info('[Integrated Channel] Single learner data transmission started.'
                ' Course: {course_run}, Username: {username}'.format(
                    course_run=course_run_id,
                    username=username))
    enterprise_customer = get_enterprise_customer_for_user(user)
    channel_utils = IntegratedChannelCommandUtils()
    # Transmit the learner data to each integrated channelStarting Export
    for channel in channel_utils.get_integrated_channels(
            {'channel': None, 'enterprise_customer': enterprise_customer.uuid}
    ):
        integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel.channel_code()].objects.get(pk=channel.pk)
        LOGGER.info(
            '[Integrated Channel] Processing learner for transmission. Configuration: {configuration},'
            ' User: {user_id}'.format(
                configuration=integrated_channel,
                user_id=user.id))
        integrated_channel.transmit_single_learner_data(
            learner_to_transmit=user,
            course_run_id=course_run_id,
            completed_date=timezone.now(),
            grade='Pass',
            is_passing=True
        )

    duration = time.time() - start
    LOGGER.info(
        '[Integrated Channel] Single learner data transmission task finished.'
        ' Course: {course_run}, Duration: {duration}, Username: {username}'.format(
            username=username,
            course_run=course_run_id,
            duration=duration))


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
