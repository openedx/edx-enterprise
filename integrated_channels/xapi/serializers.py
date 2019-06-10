# -*- coding: utf-8 -*-

"""
Serializers for xAPI data.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from edx_django_utils.cache import TieredCache
from rest_framework import serializers

from django.core.exceptions import ImproperlyConfigured

from enterprise.api.v1.serializers import ImmutableStateSerializer
from enterprise.api_client.discovery import CourseCatalogApiServiceClient
from enterprise.models import EnterpriseCustomerUser
from enterprise.utils import get_cache_key

LOGGER = getLogger(__name__)
CACHE_TIMEOUT = 3600


class LearnerInfoSerializer(ImmutableStateSerializer):
    """
    Serializer for Learner info.

    Model: User
    """
    lms_user_id = serializers.IntegerField(source='id')
    user_username = serializers.CharField(source='username')
    user_email = serializers.EmailField(source='email')
    user_country_code = serializers.CharField(source='profile.country.code')
    user_account_creation_date = serializers.DateTimeField(source='date_joined')

    enterprise_user_id = serializers.SerializerMethodField()
    enterprise_sso_uid = serializers.SerializerMethodField()

    def get_enterprise_user_id(self, obj):
        """
        Get enterprise user id from user object.

        Arguments:
            obj (User): Django User object

        Returns:
            (int): Primary Key identifier for enterprise user object.
        """
        # An enterprise learner can not belong to multiple enterprise customer at the same time
        # but if such scenario occurs we will pick the first.
        enterprise_learner = EnterpriseCustomerUser.objects.filter(user_id=obj.id).first()

        return enterprise_learner and enterprise_learner.id

    def get_enterprise_sso_uid(self, obj):
        """
        Get enterprise SSO UID.

        Arguments:
            obj (User): Django User object

        Returns:
            (str): string containing UUID for enterprise customer's Identity Provider.
        """
        # An enterprise learner can not belong to multiple enterprise customer at the same time
        # but if such scenario occurs we will pick the first.
        enterprise_learner = EnterpriseCustomerUser.objects.filter(user_id=obj.id).first()

        return enterprise_learner and enterprise_learner.get_remote_id()


class CourseInfoSerializer(ImmutableStateSerializer):
    """
    Serializer for course info.

    Model: CourseOverview
    """
    course_id = serializers.CharField(source='id')
    course_title = serializers.CharField(source='display_name')
    course_description = serializers.CharField(source='short_description')
    course_details_url = serializers.CharField(source='marketing_url')
    course_effort = serializers.CharField(source='effort')
    course_duration = serializers.SerializerMethodField()

    def get_course_duration(self, obj):
        """
        Get course's duration as a timedelta.

        Arguments:
            obj (CourseOverview): CourseOverview object

        Returns:
            (timedelta): Duration of a course.
        """
        course_run = None
        duration = None
        site = self.context.get('site')
        if site:
            cache_key = get_cache_key(course_id=obj.id, site=site)
            cached_response = TieredCache.get_cached_response(cache_key)
            if cached_response.is_found:
                course_run = cached_response.value
            else:
                try:
                    _, course_run = CourseCatalogApiServiceClient(site).get_course_and_course_run(str(obj.id))
                    TieredCache.set_all_tiers(cache_key, course_run, CACHE_TIMEOUT)
                except ImproperlyConfigured:
                    LOGGER.warning('CourseCatalogApiServiceClient is improperly configured.')
        if course_run and course_run.get('max_effort') and course_run.get('weeks_to_complete'):
            duration = '{effort} hours per week for {weeks} weeks.'.format(
                effort=course_run['max_effort'],
                weeks=course_run['weeks_to_complete']
            )
        return duration or ''
