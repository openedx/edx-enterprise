"""
Celery tasks for integrated channel management commands.
"""

import time
from functools import wraps

from celery import shared_task
from celery.utils.log import get_task_logger
from edx_django_utils.monitoring import set_code_owner_attribute

from django.contrib import auth
from django.core.cache import cache
from django.utils import timezone

from enterprise.utils import get_enterprise_uuids_for_user_and_course
from integrated_channels.integrated_channel.constants import TASK_LOCK_EXPIRY_SECONDS
from integrated_channels.integrated_channel.management.commands import (
    INTEGRATED_CHANNEL_CHOICES,
    IntegratedChannelCommandUtils,
)
from integrated_channels.utils import generate_formatted_log

LOGGER = get_task_logger(__name__)
User = auth.get_user_model()


def locked(expiry_seconds, lock_name_kwargs):
    """
    A decorator to wrap a method in a cache-based lock with a cache-key derrived from function name and selected kwargs
    """
    def task_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):  # lint-amnesty, pylint: disable=inconsistent-return-statements
            cache_key = f'{func.__name__}'
            for key in lock_name_kwargs:
                cache_key += f'-{key}:{kwargs.get(key)}'
            if cache.add(cache_key, "true", expiry_seconds):
                exception = None
                try:
                    LOGGER.info('Locking task in cache with key: %s for %s seconds', cache_key, expiry_seconds)
                    return func(*args, **kwargs)
                except Exception as error:  # lint-amnesty, pylint: disable=broad-except
                    LOGGER.exception(error)
                    exception = error
                finally:
                    LOGGER.info('Unlocking task in cache with key: %s', cache_key)
                    cache.delete(cache_key)
                    if exception:
                        LOGGER.error(f'Re-raising exception from inside locked task: {type(exception).__name__}')
                        raise exception
            else:
                LOGGER.info('Task with key %s already exists in cache', cache_key)
                return None
        return wrapper
    return task_decorator


def _log_batch_task_start(task_name, channel_code, job_user_id, integrated_channel_full_config, extra_message=''):
    """
    Logs a consistent message on the start of a batch integrated channel task.
    """
    LOGGER.info(
        '[Integrated Channel: {channel_name}] Batch {task_name} started '
        '(api user: {job_user_id}). Configuration: {configuration}. {details}'.format(
            channel_name=channel_code,
            task_name=task_name,
            job_user_id=job_user_id,
            configuration=integrated_channel_full_config,
            details=extra_message
        ))


def _log_batch_task_finish(task_name, channel_code, job_user_id,
                           integrated_channel_full_config, duration_seconds, extra_message=''):
    """
    Logs a consistent message on the end of a batch integrated channel task.
    """

    LOGGER.info(
        '[Integrated Channel: {channel_name}] Batch {task_name} finished in {duration_seconds} '
        '(api user: {job_user_id}). Configuration: {configuration}. {details}'.format(
            channel_name=channel_code,
            task_name=task_name,
            job_user_id=job_user_id,
            configuration=integrated_channel_full_config,
            duration_seconds=duration_seconds,
            details=extra_message
        ))


@shared_task
@set_code_owner_attribute
@locked(expiry_seconds=TASK_LOCK_EXPIRY_SECONDS, lock_name_kwargs=['channel_code', 'channel_pk'])
def transmit_content_metadata(username, channel_code, channel_pk):
    """
    Task to send content metadata to each linked integrated channel.

    Arguments:
        username (str): The username of the User for making API requests to retrieve content metadata.
        channel_code (str): Capitalized identifier for the integrated channel.
        channel_pk (str): Primary key for identifying integrated channel.

    """
    start = time.time()
    api_user = User.objects.get(username=username)
    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)

    _log_batch_task_start('transmit_content_metadata', channel_code, api_user.id, integrated_channel)

    try:
        integrated_channel.transmit_content_metadata(api_user)
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception(
            '[Integrated Channel: {channel_name}] Batch transmit_content_metadata failed with exception. '
            '(api user: {job_user_id}). Configuration: {configuration}'.format(
                channel_name=channel_code,
                job_user_id=api_user.id,
                configuration=integrated_channel
            ), exc_info=True)

    duration = time.time() - start
    _log_batch_task_finish('transmit_content_metadata', channel_code, api_user.id, integrated_channel, duration)


@shared_task
@set_code_owner_attribute
@locked(expiry_seconds=TASK_LOCK_EXPIRY_SECONDS, lock_name_kwargs=['channel_code', 'channel_pk'])
def transmit_learner_data(username, channel_code, channel_pk):
    """
    Task to send learner data to a linked integrated channel.

    Arguments:
        username (str): The username of the User to be used for making API requests for learner data.
        channel_code (str): Capitalized identifier for the integrated channel
        channel_pk (str): Primary key for identifying integrated channel
    """
    start = time.time()
    api_user = User.objects.get(username=username)
    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)
    _log_batch_task_start('transmit_learner_data', channel_code, api_user.id, integrated_channel)

    # Note: learner data transmission code paths don't raise any uncaught exception,
    # so we don't need a broad try-except block here.
    integrated_channel.transmit_learner_data(api_user)

    duration = time.time() - start
    _log_batch_task_finish('transmit_learner_data', channel_code, api_user.id, integrated_channel, duration)


@shared_task
@set_code_owner_attribute
def cleanup_duplicate_assignment_records(username, channel_code, channel_pk):
    """
    Task to remove transmitted duplicate assignment records of provided integrated channel.

    Arguments:
        username (str): The username of the User to be used for making API requests for learner data.
        channel_code (str): Capitalized identifier for the integrated channel
        channel_pk (str): Primary key for identifying integrated channel
    """
    start = time.time()
    api_user = User.objects.get(username=username)
    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)
    _log_batch_task_start('cleanup_duplicate_assignment_records', channel_code, api_user.id, integrated_channel)

    integrated_channel.cleanup_duplicate_assignment_records(api_user)
    duration = time.time() - start
    _log_batch_task_finish(
        'cleanup_duplicate_assignment_records',
        channel_code,
        api_user.id,
        integrated_channel,
        duration
    )


@shared_task
@set_code_owner_attribute
def update_content_transmission_catalog(username, channel_code, channel_pk):
    """
    Task to retrieve all transmitted content items under a specific channel and update audits to contain the content's
    associated catalog.

    Arguments:
        username (str): The username of the User to be used for making API requests for learner data.
        channel_code (str): Capitalized identifier for the integrated channel
        channel_pk (str): Primary key for identifying integrated channel
    """
    start = time.time()
    api_user = User.objects.get(username=username)

    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)

    _log_batch_task_start('update_content_transmission_catalog', channel_code, api_user.id, integrated_channel)

    integrated_channel.update_content_transmission_catalog(api_user)
    duration = time.time() - start
    _log_batch_task_finish(
        'update_content_transmission_catalog',
        channel_code,
        api_user.id,
        integrated_channel,
        duration
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
    enterprise_customer_uuids = get_enterprise_uuids_for_user_and_course(user, course_run_id, is_customer_active=True)

    # Transmit the learner data to each integrated channel for each related customer.
    # Starting Export. N customer is usually 1 but multiple are supported in codebase.
    for enterprise_customer_uuid in enterprise_customer_uuids:
        channel_utils = IntegratedChannelCommandUtils()
        enterprise_integrated_channels = channel_utils.get_integrated_channels(
            {'channel': None, 'enterprise_customer': enterprise_customer_uuid}
        )
        for channel in enterprise_integrated_channels:
            integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel.channel_code()].objects.get(pk=channel.pk)

            LOGGER.info(generate_formatted_log(
                integrated_channel.channel_code(),
                enterprise_customer_uuid,
                user.id,
                course_run_id,
                'transmit_single_learner_data started.'
            ))

            integrated_channel.transmit_single_learner_data(
                learner_to_transmit=user,
                course_run_id=course_run_id,
                completed_date=timezone.now(),
                grade='Pass',
                is_passing=True
            )
            LOGGER.info(generate_formatted_log(
                integrated_channel.channel_code(),
                enterprise_customer_uuid,
                user.id,
                course_run_id,
                "transmit_single_learner_data finished."
            ))


@shared_task
@set_code_owner_attribute
def transmit_single_subsection_learner_data(username, course_run_id, subsection_id, grade):
    """
    Task to send an assessment level learner data record to each linked
    integrated channel. This task is fired off
    when an enterprise learner completes a subsection of their course, and
    only sends the data for that sub-section.

    Arguments:
        username (str): The username of the learner whose data it should send.
        course_run_id  (str): The course run id of the course it should send data for.
        subsection_id (str): The completed subsection id whose grades are being reported.
        grade (str): The grade received, used to ensure we are not sending duplicate transmissions.
    """

    user = User.objects.get(username=username)
    enterprise_customer_uuids = get_enterprise_uuids_for_user_and_course(user, course_run_id, is_customer_active=True)
    channel_utils = IntegratedChannelCommandUtils()

    # Transmit the learner data to each integrated channel for each related customer.
    # Starting Export. N customer is usually 1 but multiple are supported in codebase.
    for enterprise_customer_uuid in enterprise_customer_uuids:
        enterprise_integrated_channels = channel_utils.get_integrated_channels(
            {'channel': None, 'enterprise_customer': enterprise_customer_uuid, 'assessment_level_support': True}
        )

        for channel in enterprise_integrated_channels:
            start = time.time()
            integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel.channel_code()].objects.get(pk=channel.pk)

            LOGGER.info(generate_formatted_log(
                channel.channel_code(),
                enterprise_customer_uuid,
                user.id,
                course_run_id,
                'transmit_single_subsection_learner_data for Subsection_id: {} started.'.format(subsection_id)
            ))

            integrated_channel.transmit_single_subsection_learner_data(
                learner_to_transmit=user,
                course_run_id=course_run_id,
                grade=grade,
                subsection_id=subsection_id
            )

            duration = time.time() - start
            LOGGER.info(generate_formatted_log(
                None,
                enterprise_customer_uuid,
                user.id,
                course_run_id,
                'transmit_single_subsection_learner_data for channels {channels} and for Subsection_id: '
                '{subsection_id} finished in {duration}s.'.format(
                        channels=[c.channel_code() for c in enterprise_integrated_channels],
                        subsection_id=subsection_id,
                        duration=duration)
            ))


@shared_task
@set_code_owner_attribute
@locked(expiry_seconds=TASK_LOCK_EXPIRY_SECONDS, lock_name_kwargs=['channel_code', 'channel_pk'])
def transmit_subsection_learner_data(job_username, channel_code, channel_pk):
    """
    Task to send assessment level learner data to a linked integrated channel.

    Arguments:
        job_username (str): The username of the User making API requests for learner data.
        channel_code (str): Capitalized identifier for the integrated channel
        channel_pk (str): Primary key for identifying integrated channel
    """
    start = time.time()
    api_user = User.objects.get(username=job_username)
    integrated_channel = INTEGRATED_CHANNEL_CHOICES[channel_code].objects.get(pk=channel_pk)
    _log_batch_task_start('transmit_subsection_learner_data', channel_code, api_user.id, integrated_channel)

    # Exceptions during transmission are caught and saved within the audit so no need to try/catch here
    integrated_channel.transmit_subsection_learner_data(api_user)
    duration = time.time() - start
    _log_batch_task_finish('transmit_subsection_learner_data', channel_code, api_user.id, integrated_channel, duration)


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

    _log_batch_task_start('unlink_inactive_learners', channel_code, None, integrated_channel)

    # Note: learner data transmission code paths don't raise any uncaught exception, so we don't need a broad
    # try-except block here.
    integrated_channel.unlink_inactive_learners()

    duration = time.time() - start
    _log_batch_task_finish('unlink_inactive_learners', channel_code, None, integrated_channel, duration)
