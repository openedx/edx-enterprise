"""
Celery tasks for integrated channel management commands.
"""

import time

from celery import shared_task
from celery.utils.log import get_task_logger
from edx_django_utils.monitoring import set_code_owner_attribute

from django.contrib import auth
from django.utils import timezone

from enterprise.utils import get_enterprise_uuids_for_user_and_course
from integrated_channels.integrated_channel.management.commands import (
    INTEGRATED_CHANNEL_CHOICES,
    IntegratedChannelCommandUtils,
)
from integrated_channels.utils import generate_formatted_log

LOGGER = get_task_logger(__name__)
User = auth.get_user_model()  # pylint: disable=invalid-name


@shared_task
@set_code_owner_attribute
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
@set_code_owner_attribute
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
    generate_formatted_log(
        'Batch processing learners for integrated channel. Configuration: {configuration}'.format(
            configuration=integrated_channel,
        ),
        channel_name=channel_code,
        enterprise_customer_identifier=api_user.username
    )

    # Note: learner data transmission code paths don't raise any uncaught exception, so we don't need a broad
    # try-except block here.
    integrated_channel.transmit_learner_data(api_user)

    duration = time.time() - start
    generate_formatted_log(
        'Batch learner data transmission task finished. Configuration: {configuration},'
        ' Duration: {duration}'.format(
            configuration=integrated_channel,
            duration=duration
        ),
        channel_name=channel_code,
        enterprise_customer_identifier=api_user.username
    )


@shared_task
@set_code_owner_attribute
def transmit_single_learner_data(username, course_run_id):
    """
    Task to send single learner data to each linked integrated channel.

    Arguments:
        username (str): The username of the learner whose data it should send.
        course_run_id (str): The course run id of the course it should send data for.
    """
    user = User.objects.get(username=username)
    enterprise_customer_uuids = get_enterprise_uuids_for_user_and_course(user, course_run_id, active=True)

    # Transmit the learner data to each integrated channel for each related customer.
    # Starting Export. N customer is usually 1 but multiple are supported in codebase.
    for enterprise_customer_uuid in enterprise_customer_uuids:
        LOGGER.info('[Integrated Channel] Single learner data transmission started.'
                    ' Course: {course_run}, Username: {username}, Customer:{enterprise_uuid}'.format(
                        course_run=course_run_id,
                        username=username,
                        enterprise_uuid=enterprise_customer_uuid
                    ))

        channel_utils = IntegratedChannelCommandUtils()
        # Transmit the learner data to each integrated channelStarting Export
        for channel in channel_utils.get_integrated_channels(
                {'channel': None, 'enterprise_customer': enterprise_customer_uuid}
        ):
            integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel.channel_code()].objects.get(pk=channel.pk)
            LOGGER.info(
                '[Integrated Channel] Processing learner for transmission. Configuration: {configuration},'
                ' User: {user_id}, Customer: {enterprise_uuid}'.format(
                    configuration=integrated_channel,
                    user_id=user.id,
                    enterprise_uuid=enterprise_customer_uuid))
            integrated_channel.transmit_single_learner_data(
                learner_to_transmit=user,
                course_run_id=course_run_id,
                completed_date=timezone.now(),
                grade='Pass',
                is_passing=True
            )


@shared_task
@set_code_owner_attribute
def transmit_single_subsection_learner_data(username, course_run_id, subsection_id, grade):
    """
    Task to send a single assessment level learner data record to each linked integrated channel. This task is fired off
    when an enterprise learner completes a subsection of their course, and as such only sends the data for that sub-
    section.

    Arguments:
        username (str): The username of the learner whose data it should send.
        course_run_id  (str): The course run id of the course it should send data for.
        subsection_id (str): The subsection id that the learner completed and whose grades are being reported.
        grade (str): The grade received, used to ensure we are not sending duplicate transmissions.
    """
    start = time.time()
    user = User.objects.get(username=username)
    enterprise_customer_uuids = get_enterprise_uuids_for_user_and_course(user, course_run_id, active=True)
    channel_utils = IntegratedChannelCommandUtils()

    # Transmit the learner data to each integrated channel for each related customer.
    # Starting Export. N customer is usually 1 but multiple are supported in codebase.
    for enterprise_customer_uuid in enterprise_customer_uuids:
        for channel in channel_utils.get_integrated_channels(
                {'channel': None, 'enterprise_customer': enterprise_customer_uuid}
        ):
            integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel.channel_code()].objects.get(pk=channel.pk)
            integrated_channel.transmit_single_subsection_learner_data(
                learner_to_transmit=user,
                course_run_id=course_run_id,
                grade=grade,
                subsection_id=subsection_id
            )

        duration = time.time() - start
        LOGGER.info(
            '[Integrated Channel] Single learner data transmission task finished.'
            'Customer: {enterprise_uuid}, Course: {course_run}, Duration: {duration}, Username: {username}'.format(
                username=username,
                course_run=course_run_id,
                duration=duration,
                enterprise_uuid=enterprise_customer_uuid
            ))


@shared_task
@set_code_owner_attribute
def transmit_subsection_learner_data(username, channel_code, channel_pk):
    """
    Task to send assessment level learner data to each linked integrated channel.

    Arguments:
        username (str): The username of the User to be used for making API requests for learner data.
        channel_code (str): Capitalized identifier for the integrated channel
        channel_pk (str): Primary key for identifying integrated channel
    """
    start = time.time()
    api_user = User.objects.get(username=username)
    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)
    generate_formatted_log(
        'Batch processing assessment level reporting for integrated channel. Configuration: {configuration}'.format(
            configuration=integrated_channel,
        ),
        channel_name=channel_code,
        enterprise_customer_identifier=api_user.username
    )

    # Exceptions during transmission are caught and saved within the audit so no need to try/catch here
    integrated_channel.transmit_subsection_learner_data(api_user)
    duration = time.time() - start
    LOGGER.info(
        '[Integrated Channel] Bulk learner data transmission task finished.'
        'Duration: {duration}, Username: {username}'.format(
            username=username,
            duration=duration)
    )


@shared_task
@set_code_owner_attribute
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
