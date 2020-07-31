# -*- coding: utf-8 -*-
"""
Serializers for enterprise api version 1.
"""

import copy
from logging import getLogger

from edx_rest_api_client.exceptions import HttpClientError
from rest_framework import serializers
from rest_framework.settings import api_settings

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

from enterprise import models, utils
from enterprise.api_client.lms import ThirdPartyAuthApiClient
from enterprise.constants import ENTERPRISE_PERMISSION_GROUPS
from enterprise.utils import (
    CourseEnrollmentDowngradeError,
    CourseEnrollmentPermissionError,
    has_course_run_available_for_enrollment,
    track_enrollment,
)

LOGGER = getLogger(__name__)


class ImmutableStateSerializer(serializers.Serializer):
    """
    Base serializer for any serializer that inhibits state changing requests.
    """

    def create(self, validated_data):
        """
        Do not perform any operations for state changing requests.
        """

    def update(self, instance, validated_data):
        """
        Do not perform any operations for state changing requests.
        """


class ResponsePaginationSerializer(ImmutableStateSerializer):
    """
    Serializer for responses that require pagination.
    """

    count = serializers.IntegerField(read_only=True, help_text=_('Total count of items.'))
    next = serializers.CharField(read_only=True, help_text=_('URL to fetch next page of items.'))
    previous = serializers.CharField(read_only=True, help_text=_('URL to fetch previous page of items.'))
    results = serializers.ListField(read_only=True, help_text=_('List of items.'))


class SiteSerializer(serializers.ModelSerializer):
    """
    Serializer for Site model.
    """

    class Meta:
        model = Site
        fields = (
            'domain', 'name',
        )


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    """

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'date_joined'
        )


class EnterpriseCustomerBrandingConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerBrandingConfiguration model.
    """

    class Meta:
        model = models.EnterpriseCustomerBrandingConfiguration
        fields = (
            'enterprise_customer',
            'enterprise_slug',
            'logo',
            'primary_color',
            'secondary_color',
            'tertiary_color',
        )

    enterprise_slug = serializers.SerializerMethodField()

    def get_enterprise_slug(self, obj):
        """
        Return the slug of the associated enterprise customer.
        """
        return obj.enterprise_customer.slug


class EnterpriseCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomer model.
    """

    class Meta:
        model = models.EnterpriseCustomer
        fields = (
            'uuid', 'name', 'slug', 'active', 'site', 'enable_data_sharing_consent',
            'enforce_data_sharing_consent', 'branding_configuration',
            'identity_provider', 'enable_audit_enrollment', 'replace_sensitive_sso_username',
            'enable_portal_code_management_screen', 'sync_learner_profile_data', 'enable_audit_data_reporting',
            'enable_learner_portal', 'enable_portal_reporting_config_screen',
            'enable_portal_saml_configuration_screen', 'contact_email',
            'enable_portal_subscription_management_screen', 'hide_course_original_price',
        )

    site = SiteSerializer()
    branding_configuration = EnterpriseCustomerBrandingConfigurationSerializer()


class EnterpriseCustomerBasicSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomer model only for name and id fields.
    """

    class Meta:
        model = models.EnterpriseCustomer
        fields = ('id', 'name')

    id = serializers.CharField(source='uuid')  # pylint: disable=invalid-name


class EnterpriseCourseEnrollmentReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCourseEnrollment model.
    """

    class Meta:
        model = models.EnterpriseCourseEnrollment
        fields = (
            'enterprise_customer_user', 'course_id'
        )


class EnterpriseCourseEnrollmentWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for writing to the EnterpriseCourseEnrollment model.
    """

    class Meta:
        model = models.EnterpriseCourseEnrollment
        fields = (
            'username', 'course_id',
        )

    username = serializers.CharField(max_length=30)
    enterprise_customer_user = None

    def validate_username(self, value):
        """
        Verify that the username has a matching user, and that the user has an associated EnterpriseCustomerUser.
        """
        try:
            user = User.objects.get(username=value)
        except User.DoesNotExist:
            error_message = ('[Enterprise API] The username for creating an EnterpriseCourseEnrollment'
                             ' record does not exist. User: {}').format(value)
            LOGGER.error(error_message)
            raise serializers.ValidationError("User does not exist")

        try:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.get(user_id=user.pk)
        except models.EnterpriseCustomerUser.DoesNotExist:
            error_message = '[Enterprise API] User has no EnterpriseCustomerUser. User: {}'.format(value)
            LOGGER.error(error_message)
            raise serializers.ValidationError("User has no EnterpriseCustomerUser")

        self.enterprise_customer_user = enterprise_customer_user
        return value

    def save(self):  # pylint: disable=arguments-differ
        """
        Save the model with the found EnterpriseCustomerUser.
        """
        course_id = self.validated_data['course_id']

        __, created = models.EnterpriseCourseEnrollment.objects.get_or_create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_id,
            defaults={
                'source': models.EnterpriseEnrollmentSource.get_source(
                    models.EnterpriseEnrollmentSource.OFFER_REDEMPTION
                )
            }
        )
        if created:
            track_enrollment('rest-api-enrollment', self.enterprise_customer_user.user_id, course_id)


class EnterpriseCustomerCatalogSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCustomerCatalog`` model.
    """

    class Meta:
        model = models.EnterpriseCustomerCatalog
        fields = (
            'uuid', 'title', 'enterprise_customer',
        )


class EnterpriseCustomerCatalogDetailSerializer(EnterpriseCustomerCatalogSerializer):
    """
    Serializer for the ``EnterpriseCustomerCatalog`` model which includes
    the catalog's discovery service search query results.
    """

    def to_representation(self, instance):
        """
        Serialize the EnterpriseCustomerCatalog object.

        Arguments:
            instance (EnterpriseCustomerCatalog): The EnterpriseCustomerCatalog to serialize.

        Returns:
            dict: The EnterpriseCustomerCatalog converted to a dict.
        """
        request = self.context['request']
        enterprise_customer = instance.enterprise_customer

        representation = super(EnterpriseCustomerCatalogDetailSerializer, self).to_representation(instance)

        # Retrieve the EnterpriseCustomerCatalog search results from the discovery service.
        paginated_content = instance.get_paginated_content(request.GET)
        count = paginated_content['count']
        search_results = paginated_content['results']

        for item in search_results:
            content_type = item['content_type']
            marketing_url = item.get('marketing_url')
            if marketing_url:
                item['marketing_url'] = utils.update_query_parameters(
                    marketing_url, utils.get_enterprise_utm_context(enterprise_customer)
                )
            # Add the Enterprise enrollment URL to each content item returned from the discovery service.
            if content_type == 'course':
                item['enrollment_url'] = instance.get_course_enrollment_url(item['key'])
                item['active'] = has_course_run_available_for_enrollment(item['course_runs'])
            if content_type == 'courserun':
                item['enrollment_url'] = instance.get_course_run_enrollment_url(item['key'])
            if content_type == 'program':
                item['enrollment_url'] = instance.get_program_enrollment_url(item['uuid'])

        # Build pagination URLs
        previous_url = None
        next_url = None
        page = int(request.GET.get('page', '1'))
        request_uri = request.build_absolute_uri()
        if paginated_content['previous']:
            previous_url = utils.update_query_parameters(request_uri, {'page': page - 1})
        if paginated_content['next']:
            next_url = utils.update_query_parameters(request_uri, {'page': page + 1})

        representation['count'] = count
        representation['previous'] = previous_url
        representation['next'] = next_url
        representation['results'] = search_results

        return representation


class EnterpriseCustomerUserReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerUser model.
    """

    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'id', 'enterprise_customer', 'active', 'user_id', 'user', 'data_sharing_consent_records', 'groups'
        )

    user = UserSerializer()
    enterprise_customer = EnterpriseCustomerSerializer()
    data_sharing_consent_records = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()

    def get_data_sharing_consent_records(self, obj):
        """
        Return serialization of EnterpriseCustomerUser.data_sharing_consent_records property.

        Arguments:
            EnterpriseCustomerUser: The EnterpriseCustomerUser.

        Returns:
            list of dict: The serialized DataSharingConsent records associated with the EnterpriseCustomerUser.
        """
        return [record.serialize() for record in obj.data_sharing_consent_records]

    def get_groups(self, obj):
        """
        Return the enterprise related django groups that this user is a part of.
        """
        if obj.user:
            return [group.name for group in obj.user.groups.filter(name__in=ENTERPRISE_PERMISSION_GROUPS)]
        return []


class EnterpriseCustomerUserWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for writing to the EnterpriseCustomerUser model.
    """

    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'enterprise_customer', 'username', 'active'
        )

    username = serializers.CharField(max_length=30)
    active = serializers.BooleanField(required=False, default=True)
    user = None

    def validate_username(self, value):
        """
        Verify that the username has a matching user.
        """
        try:
            self.user = User.objects.get(username=value)
        except User.DoesNotExist:
            error_message = ('[Enterprise API] Saving to EnterpriseCustomerUser failed'
                             ' due to non-existing user. User: {}').format(value)
            LOGGER.error(error_message)
            raise serializers.ValidationError("User does not exist")

        return value

    def save(self):  # pylint: disable=arguments-differ
        """
        Save the EnterpriseCustomerUser.
        """
        enterprise_customer = self.validated_data['enterprise_customer']
        active = self.validated_data.get('active', True)
        defaults = {'active': active}

        __, created = models.EnterpriseCustomerUser.objects.update_or_create(
            user_id=self.user.pk,
            enterprise_customer=enterprise_customer,
            defaults=defaults,
        )
        if not created and active:
            # if learner has activated enterprise we need to de-activate other enterprises learner is linked to
            models.EnterpriseCustomerUser.inactivate_other_customers(self.user.pk, enterprise_customer)


class PendingEnterpriseCustomerUserSerializer(serializers.ModelSerializer):
    """
    Serializer for writing to the PendingEnterpriseCustomerUser model.
    """

    class Meta:
        model = models.PendingEnterpriseCustomerUser
        fields = (
            'enterprise_customer', 'user_email'
        )

    def validate(self, attrs):
        """
        Validate if the EnterpriseCustomerUser record already exists.
        """
        enterprise_customer = attrs.get('enterprise_customer')
        user_email = attrs.get('user_email')
        try:
            user = User.objects.get(email=user_email)
            models.EnterpriseCustomerUser.objects.get(
                user_id=user.pk,
                enterprise_customer=enterprise_customer
            )
        except (User.DoesNotExist, models.EnterpriseCustomerUser.DoesNotExist):
            pass
        else:
            raise serializers.ValidationError('EnterpriseCustomerUser record already exists')

        return attrs

    def save(self):  # pylint: disable=arguments-differ
        """
        Save the PendingEnterpriseCustomerUser, or EnterpriseCustomerUser
        if a user with the validated_email already exists.
        """
        enterprise_customer = self.validated_data['enterprise_customer']
        user_email = self.validated_data['user_email']
        try:
            user = User.objects.get(email=user_email)
            defaults = {'active': user.is_active}
            __, created = models.EnterpriseCustomerUser.objects.update_or_create(
                user_id=user.pk,
                enterprise_customer=enterprise_customer,
                defaults=defaults,
            )
        except User.DoesNotExist:
            __, created = models.PendingEnterpriseCustomerUser.objects.update_or_create(
                user_email=user_email,
                enterprise_customer=enterprise_customer,
            )
        return created


class CourseDetailSerializer(ImmutableStateSerializer):
    """
    Serializer for course data retrieved from the discovery service course detail API endpoint.

    This serializer updates the course and course run data with the EnterpriseCustomer-specific enrollment page URL
    for the given course and course runs.
    """

    def to_representation(self, instance):
        """
        Return the updated course data dictionary.

        Arguments:
            instance (dict): The course data.

        Returns:
            dict: The updated course data.
        """
        updated_course = copy.deepcopy(instance)
        enterprise_customer_catalog = self.context['enterprise_customer_catalog']
        updated_course['enrollment_url'] = enterprise_customer_catalog.get_course_enrollment_url(
            updated_course['key']
        )
        for course_run in updated_course['course_runs']:
            course_run['enrollment_url'] = enterprise_customer_catalog.get_course_run_enrollment_url(
                course_run['key']
            )
        return updated_course


class CourseRunDetailSerializer(ImmutableStateSerializer):
    """
    Serializer for course run data retrieved from the discovery service course_run detail API endpoint.

    This serializer updates the course run data with the EnterpriseCustomer-specific enrollment page URL
    for the given course run.
    """

    def to_representation(self, instance):
        """
        Return the updated course run data dictionary.

        Arguments:
            instance (dict): The course run data.

        Returns:
            dict: The updated course run data.
        """
        updated_course_run = copy.deepcopy(instance)
        enterprise_customer_catalog = self.context['enterprise_customer_catalog']
        updated_course_run['enrollment_url'] = enterprise_customer_catalog.get_course_run_enrollment_url(
            updated_course_run['key']
        )
        return updated_course_run


class ProgramDetailSerializer(ImmutableStateSerializer):
    """
    Serializer for program data retrieved from the discovery service program detail API endpoint.

    This serializer updates the program data and child course run data with EnterpriseCustomer-specific
    enrollment page URLs for the given content types.
    """

    def to_representation(self, instance):
        """
        Return the updated program data dictionary.

        Arguments:
            instance (dict): The program data.

        Returns:
            dict: The updated program data.
        """
        updated_program = copy.deepcopy(instance)
        enterprise_customer_catalog = self.context['enterprise_customer_catalog']
        updated_program['enrollment_url'] = enterprise_customer_catalog.get_program_enrollment_url(
            updated_program['uuid']
        )
        for course in updated_program['courses']:
            course['enrollment_url'] = enterprise_customer_catalog.get_course_enrollment_url(course['key'])
            for course_run in course['course_runs']:
                course_run['enrollment_url'] = enterprise_customer_catalog.get_course_run_enrollment_url(
                    course_run['key']
                )
        return updated_program


class EnterpriseCustomerReportingConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerReportingConfiguration model.
    """
    class Meta:
        model = models.EnterpriseCustomerReportingConfiguration
        fields = (
            'enterprise_customer', 'enterprise_customer_id', 'active', 'delivery_method', 'email', 'frequency',
            'day_of_month', 'day_of_week', 'hour_of_day', 'include_date', 'encrypted_password', 'sftp_hostname',
            'sftp_port', 'sftp_username', 'encrypted_sftp_password', 'sftp_file_path', 'data_type', 'report_type',
            'pgp_encryption_key', 'enterprise_customer_catalogs', 'uuid'
        )

    encrypted_password = serializers.CharField(required=False, allow_blank=False, read_only=False)
    encrypted_sftp_password = serializers.CharField(required=False, allow_blank=False, read_only=False)
    enterprise_customer = EnterpriseCustomerSerializer(read_only=True)
    enterprise_customer_id = serializers.PrimaryKeyRelatedField(
        queryset=models.EnterpriseCustomer.objects.all(),  # pylint: disable=no-member
        source='enterprise_customer',
        write_only=True
    )
    enterprise_customer_catalogs = EnterpriseCustomerCatalogSerializer(many=True, read_only=True)
    email = serializers.ListField(
        child=serializers.EmailField()
    )


# pylint: disable=abstract-method
class EnterpriseCustomerCourseEnrollmentsListSerializer(serializers.ListSerializer):
    """
    Serializes a list of enrollment requests.

    Meant to be used in conjunction with EnterpriseCustomerCourseEnrollmentsSerializer.
    """

    def to_internal_value(self, data):
        """
        This implements the same relevant logic as ListSerializer except that if one or more items fail validation,
        processing for other items that did not fail will continue.
        """

        if not isinstance(data, list):
            message = self.error_messages['not_a_list'].format(
                input_type=type(data).__name__
            )
            raise serializers.ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: [message]
            })

        ret = []

        for item in data:
            try:
                validated = self.child.run_validation(item)
            except serializers.ValidationError as exc:
                ret.append(exc.detail)
            else:
                ret.append(validated)

        return ret

    def create(self, validated_data):
        """
        This selectively calls the child create method based on whether or not validation failed for each payload.
        """
        ret = []
        for attrs in validated_data:
            if 'non_field_errors' not in attrs and not any(isinstance(attrs[field], list) for field in attrs):
                ret.append(self.child.create(attrs))
            else:
                ret.append(attrs)

        return ret

    def to_representation(self, data):
        """
        This selectively calls to_representation on each result that was processed by create.
        """
        return [
            self.child.to_representation(item) if 'detail' in item else item for item in data
        ]


# pylint: disable=abstract-method
class EnterpriseCustomerCourseEnrollmentsSerializer(serializers.Serializer):
    """Serializes enrollment information for a collection of students/emails.

    This is mainly useful for implementing validation when performing enrollment operations.
    """

    class Meta:
        list_serializer_class = EnterpriseCustomerCourseEnrollmentsListSerializer

    lms_user_id = serializers.CharField(required=False, write_only=True)
    tpa_user_id = serializers.CharField(required=False, write_only=True)
    user_email = serializers.EmailField(required=False, write_only=True)
    course_run_id = serializers.CharField(required=True, write_only=True)
    cohort = serializers.CharField(required=False, write_only=True)
    course_mode = serializers.ChoiceField(
        choices=(
            ('audit', 'audit'),
            ('verified', 'verified'),
            ('professional', 'professional')
        ),
        required=True,
        write_only=True,
    )
    email_students = serializers.BooleanField(default=False, required=False, write_only=True)
    detail = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(required=False, default=True, write_only=True)

    def create(self, validated_data):
        """
        Perform the enrollment for existing enterprise customer users, or create the pending objects for new users.
        """
        enterprise_customer = self.context.get('enterprise_customer')
        lms_user = validated_data.get('lms_user_id')
        tpa_user = validated_data.get('tpa_user_id')
        user_email = validated_data.get('user_email')
        course_run_id = validated_data.get('course_run_id')
        course_mode = validated_data.get('course_mode')
        cohort = validated_data.get('cohort')
        email_students = validated_data.get('email_students')
        is_active = validated_data.get('is_active')

        enterprise_customer_user = lms_user or tpa_user or user_email

        if isinstance(enterprise_customer_user, models.EnterpriseCustomerUser):
            validated_data['enterprise_customer_user'] = enterprise_customer_user
            try:
                if is_active:
                    enterprise_customer_user.enroll(
                        course_run_id,
                        course_mode,
                        cohort=cohort,
                        source_slug=models.EnterpriseEnrollmentSource.API
                    )
                else:
                    enterprise_customer_user.unenroll(course_run_id)
            except (CourseEnrollmentDowngradeError, CourseEnrollmentPermissionError, HttpClientError) as exc:
                error_message = (
                    '[Enterprise API] An exception occurred while enrolling the user.'
                    ' EnterpriseCustomer: {enterprise_customer}, LmsUser: {lms_user}, TpaUser: {tpa_user},'
                    ' UserEmail: {user_email}, CourseRun: {course_run_id}, CourseMode {course_mode}, Message: {exc}.'
                ).format(
                    enterprise_customer=enterprise_customer,
                    lms_user=lms_user,
                    tpa_user=tpa_user,
                    user_email=user_email,
                    course_run_id=course_run_id,
                    course_mode=course_mode,
                    exc=str(exc)
                )
                LOGGER.error(error_message)
                validated_data['detail'] = str(exc)
                return validated_data

            if is_active:
                track_enrollment('enterprise-customer-enrollment-api', enterprise_customer_user.user_id, course_run_id)
        else:
            if is_active:
                enterprise_customer_user = enterprise_customer.enroll_user_pending_registration(
                    user_email,
                    course_mode,
                    course_run_id,
                    cohort=cohort,
                    enrollment_source=models.EnterpriseEnrollmentSource.get_source(
                        models.EnterpriseEnrollmentSource.API
                    )
                )
            else:
                enterprise_customer.clear_pending_registration(user_email, course_run_id)

        if email_students:
            enterprise_customer.notify_enrolled_learners(
                self.context.get('request_user'),
                course_run_id,
                [enterprise_customer_user]
            )

        validated_data['detail'] = 'success'

        return validated_data

    def validate_lms_user_id(self, value):
        """
        Validates the lms_user_id, if is given, to see if there is an existing EnterpriseCustomerUser for it.
        """
        enterprise_customer = self.context.get('enterprise_customer')

        try:
            # Ensure the given user is associated with the enterprise.
            return models.EnterpriseCustomerUser.objects.get(
                user_id=value,
                enterprise_customer=enterprise_customer
            )
        except models.EnterpriseCustomerUser.DoesNotExist:
            pass

        return None

    def validate_tpa_user_id(self, value):
        """
        Validates the tpa_user_id, if is given, to see if there is an existing EnterpriseCustomerUser for it.

        It first uses the third party auth api to find the associated username to do the lookup.
        """
        enterprise_customer = self.context.get('enterprise_customer')

        try:
            tpa_client = ThirdPartyAuthApiClient(self.context['request_user'])
            username = tpa_client.get_username_from_remote_id(
                enterprise_customer.identity_provider, value
            )
            user = User.objects.get(username=username)
            return models.EnterpriseCustomerUser.objects.get(
                user_id=user.id,
                enterprise_customer=enterprise_customer
            )
        except (models.EnterpriseCustomerUser.DoesNotExist, User.DoesNotExist):
            pass

        return None

    def validate_user_email(self, value):
        """
        Validates the user_email, if given, to see if an existing EnterpriseCustomerUser exists for it.

        If it does not, it does not fail validation, unlike for the other field validation methods above.
        """
        enterprise_customer = self.context.get('enterprise_customer')

        try:
            user = User.objects.get(email=value)
            return models.EnterpriseCustomerUser.objects.get(
                user_id=user.id,
                enterprise_customer=enterprise_customer
            )
        except (models.EnterpriseCustomerUser.DoesNotExist, User.DoesNotExist):
            pass

        return value

    def validate_course_run_id(self, value):
        """
        Validates that the course run id is part of the Enterprise Customer's catalog.
        """
        enterprise_customer = self.context.get('enterprise_customer')

        if not enterprise_customer.catalog_contains_course(value):
            error_message = ('[Enterprise API] The course run id is not in the catalog for the Enterprise Customer.'
                             ' EnterpriseCustomer: {enterprise_uuid}, EnterpriseName: {enterprise_name},'
                             ' CourseRun: {course_run_id}').format(
                                 course_run_id=value,
                                 enterprise_uuid=enterprise_customer.uuid,
                                 enterprise_name=enterprise_customer.name)
            LOGGER.warning(error_message)
            raise serializers.ValidationError(
                'The course run id {course_run_id} is not in the catalog '
                'for Enterprise Customer {enterprise_customer}'.format(
                    course_run_id=value,
                    enterprise_customer=enterprise_customer.name,
                )
            )

        return value

    def validate(self, data):  # pylint: disable=arguments-differ
        """
        Validate that at least one of the user identifier fields has been passed in.
        """
        lms_user_id = data.get('lms_user_id')
        tpa_user_id = data.get('tpa_user_id')
        user_email = data.get('user_email')
        if not lms_user_id and not tpa_user_id and not user_email:
            error_message = ('[Enterprise API] ID missing for mapping to an EnterpriseCustomerUser.'
                             ' LmsUser: {lms_user_id}, TpaUser: {tpa_user_id}, UserEmail: {user_email}').format(
                                 lms_user_id=lms_user_id,
                                 tpa_user_id=tpa_user_id,
                                 user_email=user_email)
            LOGGER.error(error_message)
            raise serializers.ValidationError(
                'At least one of the following fields must be specified and map to an EnterpriseCustomerUser: '
                'lms_user_id, tpa_user_id, user_email'
            )

        return data
