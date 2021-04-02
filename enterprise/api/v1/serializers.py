# -*- coding: utf-8 -*-
"""
Serializers for enterprise api version 1.
"""

import copy
from logging import getLogger

from edx_rest_api_client.exceptions import HttpClientError
from rest_framework import serializers
from rest_framework.settings import api_settings

from django.contrib import auth
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

from enterprise import models, utils
from enterprise.api.v1.fields import Base64EmailCSVField
from enterprise.api_client.lms import ThirdPartyAuthApiClient
from enterprise.constants import ENTERPRISE_PERMISSION_GROUPS, DefaultColors
from enterprise.models import EnterpriseCustomerIdentityProvider
from enterprise.utils import (
    CourseEnrollmentDowngradeError,
    CourseEnrollmentPermissionError,
    get_last_course_run_end_date,
    has_course_run_available_for_enrollment,
    track_enrollment,
)

LOGGER = getLogger(__name__)
User = auth.get_user_model()


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

    enterprise_customer = serializers.SerializerMethodField()
    enterprise_slug = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    primary_color = serializers.SerializerMethodField()
    secondary_color = serializers.SerializerMethodField()
    tertiary_color = serializers.SerializerMethodField()

    def get_enterprise_customer(self, obj):
        """
        Return a string representation of the associated enterprise customer's UUID.
        """
        return str(obj.enterprise_customer.uuid)

    def get_enterprise_slug(self, obj):
        """
        Return the slug of the associated enterprise customer.
        """
        return obj.enterprise_customer.slug

    def get_logo(self, obj):
        """
        Use EnterpriseCustomerBrandingConfiguration.safe_logo_url to return an absolute
        URL for either the saved customer logo or the platform logo by default
        """
        return obj.safe_logo_url

    def get_primary_color(self, obj):
        """
        Return the primary color of the branding config OR the default primary color code
        """
        return obj.primary_color if obj.primary_color else DefaultColors.PRIMARY

    def get_secondary_color(self, obj):
        """
        Return the secondary color of the branding config OR the default secondary color code
        """
        return obj.secondary_color if obj.secondary_color else DefaultColors.SECONDARY

    def get_tertiary_color(self, obj):
        """
        Return the tertiary color of the branding config OR the default tertiary color code
        """
        return obj.tertiary_color if obj.tertiary_color else DefaultColors.TERTIARY


class EnterpriseCustomerIdentityProviderSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerIdentityProvider model.
    """

    class Meta:
        model = EnterpriseCustomerIdentityProvider
        fields = ('provider_id', 'default_provider')


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
            'enable_portal_subscription_management_screen', 'hide_course_original_price', 'enable_analytics_screen',
            'enable_integrated_customer_learner_portal_search',
            'enable_portal_lms_configurations_screen', 'sender_alias', 'identity_providers',
        )

    identity_providers = EnterpriseCustomerIdentityProviderSerializer(many=True, read_only=True)
    site = SiteSerializer()
    branding_configuration = serializers.SerializerMethodField()

    def get_branding_configuration(self, obj):
        """
        Return the serialized branding configuration object OR default object if null
        """
        return EnterpriseCustomerBrandingConfigurationSerializer(obj.safe_branding_configuration).data


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
        except User.DoesNotExist as no_user_error:
            error_message = ('[Enterprise API] The username for creating an EnterpriseCourseEnrollment'
                             ' record does not exist. User: {}').format(value)
            LOGGER.error(error_message)
            raise serializers.ValidationError("User does not exist") from no_user_error

        try:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.get(user_id=user.pk)
        except models.EnterpriseCustomerUser.DoesNotExist as no_user_error:
            error_message = '[Enterprise API] User has no EnterpriseCustomerUser. User: {}'.format(value)
            LOGGER.error(error_message)
            raise serializers.ValidationError("User has no EnterpriseCustomerUser") from no_user_error

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


class LicensedEnterpriseCourseEnrollmentReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for LicensedEnterpriseCourseEnrollment model.
    """

    enterprise_course_enrollment = EnterpriseCourseEnrollmentReadOnlySerializer(read_only=True)

    class Meta:
        model = models.LicensedEnterpriseCourseEnrollment
        fields = (
            'enterprise_course_enrollment', 'license_uuid'
        )


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

        representation = super().to_representation(instance)

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
                item['end_date'] = get_last_course_run_end_date(item['course_runs'])
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
    USER_DOES_NOT_EXIST = "User does not exist"

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
            raise serializers.ValidationError(self.USER_DOES_NOT_EXIST) from None

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

    def to_representation(self, instance):
        '''
        Because we are returning whether or not the instance was created from the create method, we must use the
        instance for to_representation and ignore the "created" half of the tuple
        '''
        return super().to_representation(instance[0])

    def create(self, attrs):  # pylint: disable=arguments-differ
        """
        Create the PendingEnterpriseCustomerUser, or EnterpriseCustomerUser
        if a user with the validated_email already exists.
        """
        enterprise_customer = attrs['enterprise_customer']
        user_email = attrs['user_email']
        try:
            user = User.objects.get(email=user_email)
            defaults = {'active': user.is_active}
            new_user, created = models.EnterpriseCustomerUser.objects.update_or_create(
                user_id=user.pk,
                enterprise_customer=enterprise_customer,
                defaults=defaults,
            )
        except User.DoesNotExist:
            new_user, created = models.PendingEnterpriseCustomerUser.objects.update_or_create(
                user_email=user_email,
                enterprise_customer=enterprise_customer,
            )
        return new_user, created


class LinkLearnersSerializer(PendingEnterpriseCustomerUserSerializer):
    """
    Extends the PendingEnterpriseCustomerSerializer to validate that the enterprise customer uuid
    matches the uuid the user has permissions to update
    """
    NOT_AUTHORIZED_ERROR = 'Not authorized for this enterprise'

    def validate_enterprise_customer(self, value):
        """
        Check that the enterprise customer is the same as the one the user has permissions for
        The value recieved is an EnterpriseCustomer object
        """

        if str(value.uuid) != self.context.get('enterprise_customer__uuid'):
            raise serializers.ValidationError(self.NOT_AUTHORIZED_ERROR)
        return value


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
            'pgp_encryption_key', 'enterprise_customer_catalogs', 'uuid', 'enterprise_customer_catalog_uuids',
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
    enterprise_customer_catalog_uuids = serializers.ListField(  # pylint: disable=invalid-name
        write_only=True,
        child=serializers.UUIDField(),
        default=[]
    )
    email = serializers.ListField(
        default=[],
        child=serializers.EmailField()
    )

    def create(self, validated_data):
        """
        Perform the creation of model instance and link the enterprise customer catalogs.

        Arguments:
            validated_data (dict): A dictionary containing serializer's validated data.

        Returns:
            (EnterpriseCustomerReportingConfiguration): Instance of the newly created enterprise customer
                reporting configuration.
        """
        ec_catalog_uuids = validated_data.pop('enterprise_customer_catalog_uuids', [])
        instance = super().create(validated_data)

        # update enterprise customer catalogs on the reporting configuration instance
        instance.enterprise_customer_catalogs.set(ec_catalog_uuids)
        return instance

    def update(self, instance, validated_data):
        """
        Update the instance of enterprise customer reporting configuration and link the enterprise customer catalogs.

        Arguments:
            instance (EnterpriseCustomerReportingConfiguration): Instance of the enterprise customer reporting
                configuration being updated.
            validated_data (dict): A dictionary containing serializer's validated data.

        Returns:
            (EnterpriseCustomerReportingConfiguration): Instance of the newly created enterprise customer
                reporting configuration.

        """
        ec_catalog_uuids = validated_data.pop('enterprise_customer_catalog_uuids', [])
        instance = super().update(instance, validated_data)

        # update enterprise customer catalogs on the reporting configuration instance
        instance.enterprise_customer_catalogs.set(ec_catalog_uuids)
        return instance

    def validate(self, data):  # pylint: disable=arguments-differ
        delivery_method = data.get('delivery_method')
        if not delivery_method and self.instance:
            delivery_method = self.instance.delivery_method

        # in case of email delivery, email field should be populated with valid email(s)
        if delivery_method == models.EnterpriseCustomerReportingConfiguration.DELIVERY_METHOD_EMAIL:
            if 'email' in data and not bool(data['email']):
                raise serializers.ValidationError({'email': ['This field is required']})

        # validate that enterprise customer catalogs exist in the system.
        ec_catalog_uuids = data.get('enterprise_customer_catalog_uuids')
        enterprise_customer = data['enterprise_customer']
        if ec_catalog_uuids:
            catalog_count = enterprise_customer.enterprise_customer_catalogs.filter(
                uuid__in=ec_catalog_uuids
            ).count()

            if catalog_count != len(ec_catalog_uuids):
                raise serializers.ValidationError({
                    'enterprise_customer_catalog_uuids': [
                        'Only those catalogs can be linked that belong to the enterprise customer.',
                    ]
                })

        return data


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
        discount = enterprise_customer.default_contract_discount or 0
        LOGGER.info(
            "[Enrollment-API] Received a call with the following parameters. lms_user: [{lms_user}], "
            "tpa_user: [{tpa_user}], user_email: {user_email}, course_run_id: {course_run_id}, "
            "course_mode: {course_mode}, is_active: {is_active}, discount: {discount}".format(
                lms_user=lms_user.id if lms_user else None,
                tpa_user=tpa_user.id if tpa_user else None,
                user_email=user_email.id if isinstance(user_email, models.EnterpriseCustomerUser) else user_email,
                course_run_id=course_run_id,
                course_mode=course_mode,
                is_active=is_active,
                discount=discount
            )
        )

        enterprise_customer_user = lms_user or tpa_user or user_email

        if isinstance(enterprise_customer_user, models.EnterpriseCustomerUser):
            validated_data['enterprise_customer_user'] = enterprise_customer_user
            try:
                if is_active:
                    LOGGER.info(
                        "[Enrollment-API] Enrolling the enterprise learner [{learner_id}] in course [{course_run_id}] "
                        "in [{course_mode}] mode".format(
                            learner_id=enterprise_customer_user.id,
                            course_run_id=course_run_id,
                            course_mode=course_mode
                        )
                    )
                    enterprise_customer_user.enroll(
                        course_run_id,
                        course_mode,
                        cohort=cohort,
                        source_slug=models.EnterpriseEnrollmentSource.API,
                        discount_percentage=discount
                    )
                else:
                    LOGGER.info(
                        "[Enrollment-API] Un-enrolling the enterprise learner [{learner_id}] in course "
                        "[{course_run_id}]".format(
                            learner_id=enterprise_customer_user.id,
                            course_run_id=course_run_id,
                        )
                    )
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
                LOGGER.info(
                    "[Enrollment-API] Creating the pending enrollment for [{email}] in course [{course_run_id}] "
                    "in [{course_mode}] mode".format(
                        email=user_email,
                        course_run_id=course_run_id,
                        course_mode=course_mode
                    )
                )
                enterprise_customer_user = enterprise_customer.enroll_user_pending_registration(
                    user_email,
                    course_mode,
                    course_run_id,
                    cohort=cohort,
                    enrollment_source=models.EnterpriseEnrollmentSource.get_source(
                        models.EnterpriseEnrollmentSource.API
                    ),
                    discount=discount
                )
            else:
                LOGGER.info(
                    "[Enrollment-API] Removing the pending enrollment for [{email}] in course [{course_run_id}]".format(
                        email=user_email,
                        course_run_id=course_run_id
                    )
                )
                enterprise_customer.clear_pending_registration(user_email, course_run_id)

        if email_students:
            enterprise_customer.notify_enrolled_learners(
                self.context.get('request_user'),
                course_run_id,
                [enterprise_customer_user]
            )

        validated_data['detail'] = 'success'
        LOGGER.info(
            "[Enrollment-API] Returning success for a call with the following parameters. lms_user: [{lms_user}], "
            "tpa_user: [{tpa_user}], user_email: {user_email}, course_run_id: {course_run_id}, "
            "course_mode: {course_mode}, is_active: {is_active}".format(
                lms_user=lms_user.id if lms_user else None,
                tpa_user=tpa_user.id if tpa_user else None,
                user_email=user_email.id if isinstance(user_email, models.EnterpriseCustomerUser) else user_email,
                course_run_id=course_run_id,
                course_mode=course_mode,
                is_active=is_active
            )
        )

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


# pylint: disable=abstract-method
class EnterpriseCustomerBulkEnrollmentsSerializer(serializers.Serializer):
    """
    Serializes a email_csv or email field for bulk enrollment requests.
    """
    email = serializers.CharField(required=False)
    email_csv = Base64EmailCSVField(required=False)
    course_run_key = serializers.CharField(required=False)
    course_mode = serializers.ChoiceField(
        choices=[
            ("audit", _("Audit")),
            ("verified", _("Verified")),
            ("professional", _("Professional Education")),
            ("no-id-professional", _("Professional Education (no ID)")),
            ("credit", _("Credit")),
            ("honor", _("Honor")),
        ],
        required=False,
    )
    reason = serializers.CharField(required=False)
    salesforce_id = serializers.CharField(required=False)
    discount = serializers.DecimalField(None, 5, required=False)
    notify = serializers.BooleanField(default=False)

    def create(self, validated_data):
        return validated_data

    def validate(self, data):  # pylint: disable=arguments-differ
        if not data.get('email') and not data.get('email_csv'):
            raise serializers.ValidationError('Must include either email or email_csv in request.')
        return data


class LicensesInfoSerializer(serializers.Serializer):
    """
    Nested serializer class to allow for many license info dictionaries.
    """
    email = serializers.CharField(required=False)
    course_run_key = serializers.CharField(required=False)
    license_uuid = serializers.CharField(required=False)

    def create(self, validated_data):
        return validated_data

    def validate(self, data):  # pylint: disable=arguments-differ
        missing_fields = []
        for key in self.fields.keys():
            if not data.get(key):
                missing_fields.append(key)

        if missing_fields:
            raise serializers.ValidationError('Found missing licenses_info field(s): {}.'.format(missing_fields))

        return data


# pylint: disable=abstract-method
class EnterpriseCustomerBulkSubscriptionEnrollmentsSerializer(serializers.Serializer):
    """
    Serializes a licenses info field for bulk enrollment requests.
    """
    licenses_info = LicensesInfoSerializer(many=True, required=False)
    reason = serializers.CharField(required=False)
    salesforce_id = serializers.CharField(required=False)
    discount = serializers.DecimalField(None, 5, required=False)
    notify = serializers.BooleanField(default=False)

    def create(self, validated_data):
        return validated_data

    def validate(self, data):  # pylint: disable=arguments-differ
        if data.get('licenses_info') is None:
            raise serializers.ValidationError(
                'Must include the "licenses_info" parameter in request.'
            )
        return data
