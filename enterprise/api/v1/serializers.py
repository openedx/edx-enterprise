"""
Serializers for enterprise api version 1.
"""

import copy
import datetime
from collections import defaultdict
from collections.abc import Iterable

import pytz
from oauth2_provider.generators import generate_client_id, generate_client_secret
from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.settings import api_settings
from slumber.exceptions import HttpClientError

from django.contrib import auth
from django.contrib.sites.models import Site
from django.core import exceptions as django_exceptions
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _

from enterprise import models, utils  # pylint: disable=cyclic-import
from enterprise.api.utils import CourseRunProgressStatuses  # pylint: disable=cyclic-import
from enterprise.api.v1.fields import Base64EmailCSVField
from enterprise.api_client.lms import ThirdPartyAuthApiClient
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_PERMISSION_GROUPS,
    EXEC_ED_COURSE_TYPE,
    GROUP_MEMBERSHIP_ACCEPTED_STATUS,
    PRODUCT_SOURCE_2U,
    DefaultColors,
)
from enterprise.logging import getEnterpriseLogger
from enterprise.models import (
    AdminNotification,
    AdminNotificationRead,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseCustomerUser,
    PendingEnterpriseCustomerAdminUser,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.utils import (
    CourseEnrollmentDowngradeError,
    CourseEnrollmentPermissionError,
    get_active_sso_configurations_for_customer,
    get_integrations_for_customers,
    get_last_course_run_end_date,
    get_pending_enterprise_customer_users,
    has_course_run_available_for_enrollment,
    track_enrollment,
)
from enterprise.validators import validate_pgp_key

try:
    from federated_content_connector.models import CourseDetails
except ImportError:
    CourseDetails = None

try:
    from lms.djangoapps.certificates.api import get_certificate_for_user
except ImportError:
    get_certificate_for_user = None
    get_course_run_url = None
    get_emails_enabled = None

LOGGER = getEnterpriseLogger(__name__)
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


class AdminNotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for AdminNotification model.
    """

    class Meta:
        model = AdminNotification
        fields = ('id', 'title', 'text')


class SiteField(serializers.Field):
    """
    Custom Site field to facilitate with creation of parent objects, while also keeping output pretty.

    When used in a ModelSerializer, the site field can be provided to the create() REST API endpoint as follows, which
    performs a lookup for a site with the domain "example.com"::

      "site": {"domain": "example.com"}

    Output serializations render sites with all Site fields.
    """

    def to_representation(self, value):
        return SiteSerializer(value).data

    def to_internal_value(self, data):
        try:
            return Site.objects.get(domain=data["domain"])
        except (AttributeError, KeyError, TypeError) as exc:
            raise serializers.ValidationError({"domain": "This field is required."}) from exc
        except Site.DoesNotExist as exc:
            raise serializers.ValidationError({"domain": "No Site with the provided domain was found."}) from exc


class EnterpriseCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomer model.
    """

    class Meta:
        model = models.EnterpriseCustomer
        fields = (
            'uuid', 'name', 'slug', 'active', 'auth_org_id', 'site', 'enable_data_sharing_consent',
            'enforce_data_sharing_consent', 'branding_configuration', 'disable_expiry_messaging_for_learner_credit',
            'identity_provider', 'enable_audit_enrollment', 'replace_sensitive_sso_username',
            'enable_portal_code_management_screen', 'sync_learner_profile_data', 'enable_audit_data_reporting',
            'enable_learner_portal', 'enable_learner_portal_offers', 'enable_portal_learner_credit_management_screen',
            'enable_executive_education_2U_fulfillment', 'enable_portal_reporting_config_screen',
            'enable_portal_saml_configuration_screen', 'contact_email',
            'enable_portal_subscription_management_screen', 'hide_course_original_price', 'enable_analytics_screen',
            'enable_integrated_customer_learner_portal_search', 'enable_generation_of_api_credentials',
            'enable_portal_lms_configurations_screen', 'sender_alias', 'identity_providers',
            'enterprise_customer_catalogs', 'reply_to', 'enterprise_notification_banner', 'hide_labor_market_data',
            'modified', 'enable_universal_link', 'enable_browse_and_request', 'admin_users',
            'enable_learner_portal_sidebar_message', 'learner_portal_sidebar_content',
            'enable_pathways', 'enable_programs', 'enable_demo_data_for_analytics_and_lpr', 'enable_academies',
            'enable_one_academy', 'active_integrations', 'show_videos_in_learner_portal_search_results',
            'default_language', 'country', 'enable_slug_login',
        )

    identity_providers = EnterpriseCustomerIdentityProviderSerializer(many=True, read_only=True)
    site = SiteField(required=True)
    branding_configuration = serializers.SerializerMethodField()
    enterprise_customer_catalogs = serializers.SerializerMethodField()
    enterprise_notification_banner = serializers.SerializerMethodField()
    admin_users = serializers.SerializerMethodField()
    active_integrations = serializers.SerializerMethodField()

    def get_active_integrations(self, obj):
        return get_integrations_for_customers(obj.uuid)

    def get_branding_configuration(self, obj):
        """
        Return the serialized branding configuration object OR default object if null
        """
        return EnterpriseCustomerBrandingConfigurationSerializer(obj.safe_branding_configuration).data

    def _get_admin_users_by_enterprise_customer_uuid(self, enterprise_customers):
        """
        Get admin users for each enterprise customer.
        """

        admin_users_by_enterprise_uuid = defaultdict(list)
        enterprise_customer_uuids = [enterprise_customer.uuid for enterprise_customer in enterprise_customers]
        admin_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            role__name=ENTERPRISE_ADMIN_ROLE,
            enterprise_customer_id__in=enterprise_customer_uuids
        ).select_related('user')

        for role_assignment in admin_role_assignments:
            admin_users_by_enterprise_uuid[role_assignment.enterprise_customer_id].append({
                'email': role_assignment.user.email,
                'lms_user_id': role_assignment.user.id,
            })

        return admin_users_by_enterprise_uuid

    def __init__(self, instance=None, data=empty, **kwargs):
        """
        Compute admin users for for all EnterpriseCustomer(s) during initialization
        to prevent making queries for each instance.
        """

        super().__init__(instance=instance, data=data, **kwargs)

        if instance:
            self.admin_users_by_enterprise_uuid = self._get_admin_users_by_enterprise_customer_uuid(
                instance if isinstance(instance, Iterable) else [instance]
            )
        else:
            self.admin_users_by_enterprise_uuid = defaultdict(list)

    def get_admin_users(self, obj):
        return self.admin_users_by_enterprise_uuid[obj.uuid]

    def get_enterprise_customer_catalogs(self, obj):
        """
        Return list of catalog uuids associated with the enterprise customer.
        """
        return [str(catalog.uuid) for catalog in obj.enterprise_customer_catalogs.all()]

    def get_enterprise_notification_banner(self, obj):
        """
        Return the notification text if exist OR None
        """

        try:
            # this serializer is also called from tpa_pipeline and request is not available in the first place there.
            request = self.context['request']
            user_id = request.user.id
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error('[Admin Notification API] Get enterprise notification banner request object not found,'
                         ' Enterprise Customer :{} Exception: {}'.format(obj.slug, exc))
            return None
        now = datetime.datetime.now(pytz.UTC)
        read = True
        notification_queryset = None

        notification = AdminNotification.objects.filter(
            start_date__lte=now,
            expiration_date__gte=now,
            is_active=True
        ).first()
        if notification:
            try:
                # verify that user didn't read the notification
                enterprise_customer_user = EnterpriseCustomerUser.objects.get(
                    enterprise_customer=obj,
                    user_id=user_id,
                )
                read = AdminNotificationRead.objects.filter(
                    enterprise_customer_user=enterprise_customer_user,
                    is_read=True,
                    admin_notification=notification
                ).exists()
            except (TypeError, ValueError, EnterpriseCustomerUser.DoesNotExist):
                error_message = ('[Admin Notification API] EnterpriseCustomerUser does not exist for User: {}, '
                                 ' EnterpriseCustomer:{}').format(user_id, obj.slug)
                LOGGER.error(error_message)

        if not read:
            notification_queryset = notification
            filters = notification.admin_notification_filter.all()
            for notification_filter in filters:
                # if filter didn't match to filters in enterprise_customer OR filter is not checked in
                # enterprise_customer then return None
                if not getattr(obj, notification_filter.filter, None):
                    notification_queryset = None
        return AdminNotificationSerializer(notification_queryset).data


class EnterpriseCustomerSupportToolSerializer(EnterpriseCustomerSerializer):
    """
    Extends the EnterpriseCustomerSerializer with additional fields to needed in the
    MFE Support tool.
    """
    class Meta:
        model = models.EnterpriseCustomer
        fields = (
            'uuid', 'name', 'slug', 'active', 'auth_org_id', 'site', 'enable_data_sharing_consent',
            'enforce_data_sharing_consent', 'branding_configuration', 'disable_expiry_messaging_for_learner_credit',
            'identity_provider', 'enable_audit_enrollment', 'replace_sensitive_sso_username',
            'enable_portal_code_management_screen', 'sync_learner_profile_data', 'enable_audit_data_reporting',
            'enable_learner_portal', 'enable_learner_portal_offers', 'enable_portal_learner_credit_management_screen',
            'enable_executive_education_2U_fulfillment', 'enable_portal_reporting_config_screen',
            'enable_portal_saml_configuration_screen', 'contact_email',
            'enable_portal_subscription_management_screen', 'hide_course_original_price', 'enable_analytics_screen',
            'enable_integrated_customer_learner_portal_search', 'enable_generation_of_api_credentials',
            'enable_portal_lms_configurations_screen', 'sender_alias', 'identity_providers',
            'enterprise_customer_catalogs', 'reply_to', 'enterprise_notification_banner', 'hide_labor_market_data',
            'modified', 'enable_universal_link', 'enable_browse_and_request', 'admin_users',
            'enable_learner_portal_sidebar_message', 'learner_portal_sidebar_content',
            'enable_pathways', 'enable_programs', 'enable_demo_data_for_analytics_and_lpr', 'enable_academies',
            'enable_one_academy', 'active_integrations', 'show_videos_in_learner_portal_search_results',
            'default_language', 'country', 'enable_slug_login', 'active_sso_configurations', 'created',
        )

    active_sso_configurations = serializers.SerializerMethodField()

    def get_active_sso_configurations(self, obj):
        return get_active_sso_configurations_for_customer(obj.uuid)


class EnterpriseCustomerBasicSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomer model only for name and id fields.
    """

    class Meta:
        model = models.EnterpriseCustomer
        fields = ('id', 'name')

    id = serializers.CharField(source='uuid')


class EnterpriseCourseEnrollmentReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCourseEnrollment model.
    """

    class Meta:
        model = models.EnterpriseCourseEnrollment
        fields = (
            'enterprise_customer_user', 'course_id', 'unenrolled_at', 'created',
        )


class EnterpriseCourseEnrollmentWithAdditionalFieldsReadOnlySerializer(EnterpriseCourseEnrollmentReadOnlySerializer):
    """
    Serializer for EnterpriseCourseEnrollment model with additional fields.
    """

    class Meta:
        model = models.EnterpriseCourseEnrollment
        fields = (
            'enterprise_customer_user',
            'course_id',
            'created',
            'unenrolled_at',
            'enrollment_date',
            'enrollment_track',
            'user_email',
            'course_start',
            'course_end',
        )

    enrollment_track = serializers.CharField()
    enrollment_date = serializers.DateTimeField()
    user_email = serializers.EmailField()
    course_start = serializers.DateTimeField()
    course_end = serializers.DateTimeField()


class EnterpriseCourseEnrollmentAdminViewSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCourseEnrollment model.
    """
    class Meta:
        model = models.EnterpriseCourseEnrollment
        fields = '__all__'

    def to_representation(self, instance):
        """
        Convert the `EnterpriseCourseEnrollment` instance into a dictionary representation.

        Args:
            instance (EnterpriseCourseEnrollment): The enrollment instance being serialized.

        Returns:
            dict: A dictionary representation of the enrollment data.
        """
        representation = super().to_representation(instance)
        course_run_id = instance.course_id
        user = self.context['enterprise_customer_user']
        course_overview = self._get_course_overview(course_run_id)

        certificate_info = get_certificate_for_user(user.username, course_run_id) or {}

        representation['course_run_id'] = course_run_id
        representation['course_run_status'] = self._get_course_run_status(
            course_overview,
            certificate_info,
            instance
        )
        representation['created'] = instance.created.isoformat()
        representation['start_date'] = course_overview['start']
        representation['end_date'] = course_overview['end']
        representation['display_name'] = course_overview['display_name_with_default']
        representation['org_name'] = course_overview['display_org_with_default']
        representation['pacing'] = course_overview['pacing']
        representation['is_revoked'] = instance.license.is_revoked if instance.license else False
        representation['is_enrollment_active'] = instance.is_active
        representation['mode'] = instance.mode

        if CourseDetails:
            course_details = CourseDetails.objects.filter(id=course_run_id).first()
            if course_details:
                representation['course_key'] = course_details.course_key
                representation['course_type'] = course_details.course_type
                representation['product_source'] = course_details.product_source
                representation['start_date'] = course_details.start_date or representation['start_date']
                representation['end_date'] = course_details.end_date or representation['end_date']
                representation['enroll_by'] = course_details.enroll_by

                if (course_details.product_source == PRODUCT_SOURCE_2U and
                        course_details.course_type == EXEC_ED_COURSE_TYPE):
                    representation['course_run_status'] = self._get_exec_ed_course_run_status(
                        course_details,
                        certificate_info,
                        instance
                    )
        return representation

    def _get_course_overview(self, course_run_id):
        """
        Get the appropriate course overview from the context.
        """
        for overview in self.context['course_overviews']:
            if overview['id'] == course_run_id:
                return overview

        return None

    def _get_exec_ed_course_run_status(self, course_details, certificate_info, enterprise_enrollment):
        """
        Get the status of a exec ed course run, given the state of a user's certificate in the course.

        A run is considered "complete" when either the course run has ended OR the user has earned a
        passing certificate.

        Arguments:
            course_details : the details for the exececutive education course run
            certificate_info: A dict containing the following key:
                ``is_passing``: whether the  user has a passing certificate in the course run

        Returns:
            status: one of (
                CourseRunProgressStatuses.SAVED_FOR_LATER,
                CourseRunProgressStatuses.COMPLETE,
                CourseRunProgressStatuses.IN_PROGRESS,
                CourseRunProgressStatuses.UPCOMING,
            )
        """
        if enterprise_enrollment and enterprise_enrollment.saved_for_later:
            return CourseRunProgressStatuses.SAVED_FOR_LATER

        is_certificate_passing = certificate_info.get('is_passing', False)
        start_date = course_details.start_date
        end_date = course_details.end_date

        has_started = datetime.now(pytz.utc) > start_date if start_date is not None else True
        has_ended = datetime.now(pytz.utc) > end_date if end_date is not None else False

        if has_ended or is_certificate_passing:
            return CourseRunProgressStatuses.COMPLETED
        if has_started:
            return CourseRunProgressStatuses.IN_PROGRESS
        return CourseRunProgressStatuses.UPCOMING

    def _get_course_run_status(self, course_overview, certificate_info, enterprise_enrollment):
        """
        Get the status of a course run, given the state of a user's certificate in the course.

        A run is considered "complete" when either the course run has ended OR the user has earned a
        passing certificate.

        Arguments:
            course_overview (CourseOverview): the overview for the course run
            certificate_info: A dict containing the following key:
                ``is_passing``: whether the  user has a passing certificate in the course run

        Returns:
            status: one of (
                CourseRunProgressStatuses.SAVED_FOR_LATER,
                CourseRunProgressStatuses.COMPLETE,
                CourseRunProgressStatuses.IN_PROGRESS,
                CourseRunProgressStatuses.UPCOMING,
            )
        """
        if enterprise_enrollment and enterprise_enrollment.saved_for_later:
            return CourseRunProgressStatuses.SAVED_FOR_LATER

        is_certificate_passing = certificate_info.get('is_passing', False)

        if course_overview['has_ended'] or is_certificate_passing:
            return CourseRunProgressStatuses.COMPLETED
        if course_overview['has_started']:
            return CourseRunProgressStatuses.IN_PROGRESS
        return CourseRunProgressStatuses.UPCOMING


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


class LearnerCreditEnterpriseCourseEnrollmentReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for LearnerCreditEnterpriseCourseEnrollment model.
    """
    enterprise_course_enrollment = EnterpriseCourseEnrollmentReadOnlySerializer(read_only=True)

    class Meta:
        model = models.LearnerCreditEnterpriseCourseEnrollment
        fields = (
            'enterprise_course_enrollment', 'transaction_id', 'uuid',
        )


class LicensedEnterpriseCourseEnrollmentReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for LicensedEnterpriseCourseEnrollment model.
    """

    enterprise_course_enrollment = EnterpriseCourseEnrollmentReadOnlySerializer(read_only=True)

    class Meta:
        model = models.LicensedEnterpriseCourseEnrollment
        fields = (
            'enterprise_course_enrollment', 'license_uuid', 'uuid',
        )


class EnterpriseCustomerCatalogSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCustomerCatalog`` model.
    """

    class Meta:
        model = models.EnterpriseCustomerCatalog
        fields = (
            'uuid', 'title', 'enterprise_customer', 'enterprise_catalog_query', 'created', 'modified',
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


class EnterpriseCustomerSsoConfiguration(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCustomerSsoConfiguration`` model.
    """
    class Meta:
        model = models.EnterpriseCustomerSsoConfiguration
        fields = '__all__'

    is_pending_configuration = serializers.SerializerMethodField()
    enterprise_customer = serializers.SerializerMethodField()

    def get_enterprise_customer(self, obj):
        """
        Return a string representation of the associated enterprise customer's UUID.
        """
        return str(obj.enterprise_customer.uuid)

    def get_is_pending_configuration(self, obj):
        """
        Return whether the SSO configuration is pending configuration.
        """
        return obj.is_pending_configuration()


class EnterpriseCustomerCatalogWriteOnlySerializer(EnterpriseCustomerCatalogSerializer):
    """
    Serializer for the ``EnterpriseCustomerCatalog`` model which includes
    the catalog's discovery service search query results.
    """

    class Meta:
        model = models.EnterpriseCustomerCatalog
        fields = (
            'uuid',
            'title',
            'enterprise_customer',
            'enterprise_catalog_query'
        )
        extra_kwargs = {
            'uuid': {'required': False},
            'title': {'required': True},
            'enterprise_customer': {'required': True},
            'enterprise_catalog_query': {'required': False}
        }


class EnterpriseGroupSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseGroup model.
    """
    class Meta:
        model = models.EnterpriseGroup
        fields = (
            'enterprise_customer', 'name', 'uuid',
            'accepted_members_count', 'group_type', 'created')

    accepted_members_count = serializers.SerializerMethodField()

    def get_accepted_members_count(self, obj):
        "Returns count for accepted members"
        accepted_members = obj.get_all_learners().filter(status=GROUP_MEMBERSHIP_ACCEPTED_STATUS)
        return len(accepted_members)


class EnterpriseGroupMembershipSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseGroupMembership model.
    """
    enterprise_customer_user_id = serializers.IntegerField(source='enterprise_customer_user.id', allow_null=True)
    lms_user_id = serializers.IntegerField(source='enterprise_customer_user.user_id', allow_null=True)
    pending_enterprise_customer_user_id = serializers.IntegerField(
        source='pending_enterprise_customer_user.id', allow_null=True
    )
    enterprise_group_membership_uuid = serializers.UUIDField(source='uuid', allow_null=True, read_only=True)
    activated_at = serializers.DateTimeField(required=False)
    group_name = serializers.CharField(source='group.name')
    group_uuid = serializers.CharField(source='group.uuid')
    member_details = serializers.SerializerMethodField()
    recent_action = serializers.SerializerMethodField()
    status = serializers.CharField(required=False)
    enrollments = serializers.SerializerMethodField()

    class Meta:
        model = models.EnterpriseGroupMembership
        fields = (
            'enterprise_customer_user_id',
            'lms_user_id',
            'pending_enterprise_customer_user_id',
            'enterprise_group_membership_uuid',
            'member_details',
            'recent_action',
            'status',
            'activated_at',
            'enrollments',
            'group_name',
            'group_uuid',
        )

    def get_member_details(self, obj):
        """
        Return either the member's name and email if it's the case that the member is realized, otherwise just email
        """
        if user := obj.enterprise_customer_user:
            return {"user_email": user.user_email, "user_name": user.name}
        return {"user_email": obj.pending_enterprise_customer_user.user_email}

    def get_recent_action(self, obj):
        """
        Return the timestamp and name of the most recent action associated with the membership.
        """
        if obj.errored_at:
            return f"Errored: {obj.errored_at.strftime('%B %d, %Y')}"
        if obj.is_removed:
            return f"Removed: {obj.removed_at.strftime('%B %d, %Y')}"
        if obj.enterprise_customer_user and obj.activated_at:
            return f"Accepted: {obj.activated_at.strftime('%B %d, %Y')}"
        return f"Invited: {obj.created.strftime('%B %d, %Y')}"

    def get_enrollments(self, obj):
        """
        Fetch all of user's enterprise enrollments
        """
        if user := obj.enterprise_customer_user:
            enrollments = models.EnterpriseCourseEnrollment.objects.filter(
                enterprise_customer_user=user.user_id,
            )
            return len(enrollments)
        return 0


class EnterpriseCustomerUserReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerUser model.
    """

    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'id',
            'enterprise_customer',
            'active',
            'user_id',
            'user',
            'data_sharing_consent_records',
            'groups',
            'created',
            'invite_key',
            'role_assignments',
            'enterprise_group',
        )

    user = UserSerializer()
    enterprise_customer = serializers.SerializerMethodField()
    data_sharing_consent_records = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    role_assignments = serializers.SerializerMethodField()
    enterprise_group = serializers.SerializerMethodField()

    def _get_role_assignments_by_ecu_id(self, enterprise_customer_users):
        """
        Get enterprise role assignments for each enterprise customer user.
        """

        user_ids = [ecu.user_id for ecu in enterprise_customer_users]
        role_assignments = models.SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user_id__in=user_ids
        ).select_related('role')

        role_assignments_by_ecu_id = {
            ecu.id: [
                role_assignment.role.name for role_assignment in role_assignments if
                role_assignment.user_id == ecu.user_id and
                role_assignment.enterprise_customer_id == ecu.enterprise_customer_id
            ] for ecu in enterprise_customer_users
        }

        return role_assignments_by_ecu_id

    def __init__(self, instance=None, data=empty, **kwargs):
        super().__init__(instance=instance, data=data, **kwargs)

        if instance:
            role_assignments_by_ecu_id = self._get_role_assignments_by_ecu_id(
                instance if isinstance(instance, Iterable) else [instance]
            )
            self.role_assignments_by_ecu_id = role_assignments_by_ecu_id

    def get_enterprise_customer(self, obj):
        """
        Return serialization of EnterpriseCustomer associated with the EnterpriseCustomerUser.
        """
        return EnterpriseCustomerSerializer(
            instance=obj.enterprise_customer,
            context=self.context
        ).data

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

    def get_role_assignments(self, obj):
        """
        Return the enterprise role assignments for this enterprise customer user.
        """
        return self.role_assignments_by_ecu_id.get(obj.id, [])

    def get_enterprise_group(self, obj):
        """
        Return the enterprise group membership for this enterprise customer user.
        """
        enterprise_groups_from_memberships = obj.memberships.select_related('group').all().values_list(
            'group',
            flat=True
        )
        group_uuids = set(enterprise_groups_from_memberships)
        return list(group_uuids)


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

    def create(self, attrs):  # pylint: disable=arguments-renamed
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
            'enable_compression',
        )

    encrypted_password = serializers.CharField(required=False, allow_blank=False, read_only=False)
    encrypted_sftp_password = serializers.CharField(required=False, allow_blank=False, read_only=False)
    enterprise_customer = EnterpriseCustomerSerializer(read_only=True)
    enterprise_customer_id = serializers.PrimaryKeyRelatedField(
        queryset=models.EnterpriseCustomer.objects.all(),
        source='enterprise_customer',
        write_only=True
    )
    enterprise_customer_catalogs = EnterpriseCustomerCatalogSerializer(many=True, read_only=True)
    enterprise_customer_catalog_uuids = serializers.ListField(
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

    def validate_pgp_encryption_key(self, value):
        """
        Validate that pgp_encryption_key is correctly set or left empty.
        """
        if value:
            try:
                validate_pgp_key(value)
            except django_exceptions.ValidationError as error:
                raise serializers.ValidationError('Please enter a valid PGP key.') from error
        return value

    def validate(self, data):  # pylint: disable=arguments-renamed
        error = EnterpriseCustomerReportingConfiguration.validate_compression(
            data.get('enable_compression'),
            data.get('data_type'),
            data.get('delivery_method')
        )
        if error:
            raise serializers.ValidationError(error)

        delivery_method = data.get('delivery_method')
        create_report = data.get('uuid') is not None
        if create_report:
            delivery_method_error = self.instance.validate_delivery_method(
                data.get('uuid'),
                delivery_method
            )
            if delivery_method_error:
                raise serializers.ValidationError(delivery_method_error)

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

    def validate(self, data):  # pylint: disable=arguments-renamed
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
            ("unpaid-executive-education", _("Unpaid Executive Education")),
        ],
        required=False,
    )
    reason = serializers.CharField(required=False)
    salesforce_id = serializers.CharField(required=False)
    discount = serializers.DecimalField(None, 5, required=False)
    notify = serializers.BooleanField(default=False)

    def create(self, validated_data):
        return validated_data

    def validate(self, data):  # pylint: disable=arguments-renamed
        if not data.get('email') and not data.get('email_csv'):
            raise serializers.ValidationError('Must include either email or email_csv in request.')
        return data


class EnrollmentsInfoSerializer(serializers.Serializer):
    """
    Nested serializer class to allow for many license info dictionaries.
    """
    user_id = serializers.IntegerField(required=False)
    email = serializers.CharField(required=False)
    course_run_key = serializers.CharField(required=True)
    license_uuid = serializers.CharField(required=False)
    transaction_id = serializers.CharField(required=False)
    force_enrollment = serializers.BooleanField(
        required=False,
        help_text='Enroll even if enrollment deadline is expired.',
    )
    is_default_auto_enrollment = serializers.BooleanField(
        required=False,
        help_text='Auto-enrollment for default enterprise enrollment intention.',
    )

    def create(self, validated_data):
        return validated_data

    def validate(self, data):  # pylint: disable=arguments-renamed
        # Validate that at least one user identifier was provided.  Providing both will not fail validation, so the
        # burden is on the caller to validate that they match.
        user_id = data.get('user_id')
        email = data.get('email')
        if not user_id and not email:
            raise serializers.ValidationError(
                "At least one user identifier field [user_id or email] required."
            )
        # Validate that one and only one subsidy info field was provided:
        license_uuid = data.get('license_uuid')
        transaction_id = data.get('transaction_id')
        if not license_uuid and not transaction_id:
            raise serializers.ValidationError(
                "At least one subsidy info field [license_uuid or transaction_id] required."
            )
        if license_uuid and transaction_id:
            raise serializers.ValidationError(
                "Enrollment info contains conflicting subsidy information: `license_uuid` and `transaction_id` found"
            )
        return data


# pylint: disable=abstract-method
class EnterpriseCustomerBulkSubscriptionEnrollmentsSerializer(serializers.Serializer):
    """
    Serializes a licenses info field for bulk enrollment requests.
    """
    licenses_info = EnrollmentsInfoSerializer(many=True, required=False)
    enrollments_info = EnrollmentsInfoSerializer(many=True, required=False)
    reason = serializers.CharField(required=False)
    salesforce_id = serializers.CharField(required=False)
    discount = serializers.DecimalField(None, 5, required=False)
    notify = serializers.BooleanField(default=False)

    def create(self, validated_data):
        return validated_data

    def validate(self, data):  # pylint: disable=arguments-renamed
        licenses_info = data.get('licenses_info')
        enrollments_info = data.get('enrollments_info')
        if bool(licenses_info) == bool(enrollments_info):
            if licenses_info:
                raise serializers.ValidationError(
                    '`licenses_info` must be ommitted if `enrollments_info` is present.'
                )
            raise serializers.ValidationError(
                'Must include the `enrollment_info` parameter in request.'
            )
        return data


class BaseEnterpriseCustomerInviteKeySerializer(serializers.ModelSerializer):
    """
    Base serializer for writing to the EnterpriseCustomerInviteKey model.
    """

    class Meta:
        model = models.EnterpriseCustomerInviteKey
        fields = (
            'uuid',
            'enterprise_customer_uuid',
            'usage_limit',
            'expiration_date',
            'is_active',
            'is_valid',
        )


class EnterpriseCustomerInviteKeyWriteSerializer(BaseEnterpriseCustomerInviteKeySerializer):
    """
    Serializer for writing to the EnterpriseCustomerInviteKey model.
    """

    uuid = serializers.UUIDField(read_only=True)
    enterprise_customer_uuid = serializers.UUIDField()
    usage_limit = serializers.IntegerField(required=False)
    expiration_date = serializers.DateTimeField(required=False)
    is_active = serializers.BooleanField(read_only=True)

    def validate_enterprise_customer_uuid(self, value):
        """
        Validates an EnterpriseCustomer with the given enterprise_customer_uuid exists.
        """
        try:
            models.EnterpriseCustomer.objects.get(
                uuid=value
            )
        except models.EnterpriseCustomer.DoesNotExist as no_enterprise_customer_error:
            msg = f"EnterpriseCustomer with uuid {value} does not exist."
            raise serializers.ValidationError(msg) from no_enterprise_customer_error

        return value

    def save(self):  # pylint: disable=arguments-differ
        args = dict(self.validated_data)
        enterprise_customer_uuid = args.pop('enterprise_customer_uuid')
        obj = models.EnterpriseCustomerInviteKey.objects.create(
            enterprise_customer_id=enterprise_customer_uuid,
            **args
        )
        self.validated_data['uuid'] = obj.uuid


class EnterpriseCustomerInviteKeyPartialUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating the EnterpriseCustomerInviteKey model.
    """

    expiration_date = serializers.DateTimeField(required=False)
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = models.EnterpriseCustomerInviteKey
        fields = (
            'expiration_date',
            'is_active',
        )


class EnterpriseCustomerInviteKeyReadOnlySerializer(BaseEnterpriseCustomerInviteKeySerializer):
    """
    Serializer for reading the EnterpriseCustomerInviteKey model.
    """

    class Meta(BaseEnterpriseCustomerInviteKeySerializer.Meta):
        additional_fields = ('enterprise_customer_name', 'usage_count', 'created')
        fields = BaseEnterpriseCustomerInviteKeySerializer.Meta.fields + additional_fields

    enterprise_customer_uuid = serializers.SerializerMethodField()
    enterprise_customer_name = serializers.SerializerMethodField()

    def get_enterprise_customer_uuid(self, obj):
        return obj.enterprise_customer.uuid

    def get_enterprise_customer_name(self, obj):
        return obj.enterprise_customer.name


class EnterpriseCustomerToggleUniversalLinkSerializer(serializers.Serializer):
    """
    Serializer for toggling an EnterpriseCustomer enable_universal_link field.
    """

    enable_universal_link = serializers.BooleanField(required=True)
    expiration_date = serializers.DateTimeField(required=False)


class EnterpriseCustomerUnlinkUsersSerializer(serializers.Serializer):
    """
    Serializer for the ``EnterpriseCustomerViewSet`` unlink_users action.
    """

    user_emails = serializers.ListField(
        child=serializers.EmailField(
            allow_blank=False,
        ),
        allow_empty=False,
    )

    is_relinkable = serializers.BooleanField(
        required=False,
        default=False,
    )


class EnterpriseCatalogQuerySerializer(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCatalogQuery`` model.
    """

    class Meta:
        model = models.EnterpriseCatalogQuery
        fields = '__all__'

    # Parses from a dictionary to JSON
    content_filter = serializers.JSONField(required=False)


class PendingEnterpriseCustomerAdminUserSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``PendingEnterpriseCustomerAdminUser`` model.
    """

    class Meta:
        model = PendingEnterpriseCustomerAdminUser
        fields = (
            'id', 'enterprise_customer', 'user_email'
        )

    def validate(self, attrs):
        """
        Validate the pending enterprise customer admin user data.
        """
        instance = self.instance
        user_email = attrs.get('user_email', instance.user_email if instance else None)
        enterprise_customer = attrs.get('enterprise_customer', instance.enterprise_customer if instance else None)

        admin_instance = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            role__name=ENTERPRISE_ADMIN_ROLE, user__email=user_email, enterprise_customer=enterprise_customer
        )

        if admin_instance.exists():
            raise serializers.ValidationError(
                'A user with this email and enterprise customer already has admin permission.'
            )

        return attrs

    def save(self, **kwargs):
        """
        Attempts to save the pending enterprise customer admin user data while handling potential integrity errors.
        """
        try:
            with transaction.atomic():
                return super().save(**kwargs)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                'A pending user with this email and enterprise customer already exists.'
            ) from exc
        except Exception as e:
            error_message = f"An unexpected error occurred while saving PendingEnterpriseCustomerAdminUser: {e}"
            data = self.validated_data
            LOGGER.error(error_message, extra={'data': data})
            raise serializers.ValidationError('An unexpected error occurred. Please try again later.')


class AnalyticsSummarySerializer(serializers.Serializer):
    """
    Serializer for the payload data of analytics summary endpoint.
    """
    class LearnerProgressSerializer(serializers.Serializer):
        """
        Serializer for the learner progress data in the analytics summary endpoint.
        """
        enterprise_customer_uuid = serializers.UUIDField(required=True)
        enterprise_customer_name = serializers.CharField(required=True)
        active_subscription_plan = serializers.BooleanField(required=True)
        assigned_licenses = serializers.IntegerField(required=True)
        activated_licenses = serializers.IntegerField(required=True)
        assigned_licenses_percentage = serializers.FloatField(required=True)
        activated_licenses_percentage = serializers.FloatField(required=True)
        active_enrollments = serializers.IntegerField(required=True)
        at_risk_enrollment_less_than_one_hour = serializers.IntegerField(required=True)
        at_risk_enrollment_end_date_soon = serializers.IntegerField(required=True)
        at_risk_enrollment_dormant = serializers.IntegerField(required=True)

    class LearnerEngagementSerializer(serializers.Serializer):
        """
        Serializer for the summary related data in the analytics summary endpoint.
        """
        enterprise_customer_uuid = serializers.UUIDField(required=True)
        enterprise_customer_name = serializers.CharField(required=True)
        enrolls = serializers.IntegerField(required=True)
        enrolls_prior = serializers.IntegerField(required=True)
        passed = serializers.IntegerField(required=True)
        passed_prior = serializers.IntegerField(required=True)
        engage = serializers.IntegerField(required=True)
        engage_prior = serializers.IntegerField(required=True)
        hours = serializers.IntegerField(required=True)
        hours_prior = serializers.IntegerField(required=True)
        active_contract = serializers.BooleanField(required=True)

    learner_progress = LearnerProgressSerializer()
    learner_engagement = LearnerEngagementSerializer()


class EnterpriseCustomerApiCredentialSerializer(serializers.Serializer):
    """
    Serializer for the ``EnterpriseCustomerApiCredential``
    """
    class Meta:
        lookup_field = 'user'

    id = serializers.IntegerField(required=False, read_only=True)
    name = serializers.CharField(required=False)

    client_id = serializers.CharField(read_only=True, default=generate_client_id())
    client_secret = serializers.CharField(read_only=True, default=generate_client_secret())
    authorization_grant_type = serializers.CharField(required=False)
    client_type = serializers.CharField(required=False)
    created = serializers.DateTimeField(required=False, read_only=True)
    updated = serializers.DateTimeField(required=False, read_only=True)
    redirect_uris = serializers.CharField(required=False)
    user = UserSerializer(read_only=True)

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.authorization_grant_type = validated_data.get('authorization_grant_type',
                                                               instance.authorization_grant_type)
        instance.client_type = validated_data.get('client_type', instance.client_type)
        instance.redirect_uris = validated_data.get('redirect_uris', instance.redirect_uris)
        instance.save()
        return instance


class EnterpriseCustomerApiCredentialRegeneratePatchSerializer(serializers.Serializer):
    """
    Serializer for the ``EnterpriseCustomerApiCredential``
    """
    class Meta:
        lookup_field = 'user'

    name = serializers.CharField(required=False)
    client_id = serializers.CharField(read_only=True, default=generate_client_id())
    client_secret = serializers.CharField(read_only=True, default=generate_client_secret())
    redirect_uris = serializers.CharField(required=False)
    updated = serializers.DateTimeField(required=False, read_only=True)


class EnterpriseGroupRequestDataSerializer(serializers.Serializer):
    """
    Serializer for the Enterprise Group Assign Learners endpoint query params
    """
    catalog_uuid = serializers.UUIDField(required=False, allow_null=True)
    act_by_date = serializers.DateTimeField(required=False, allow_null=True)
    learner_emails = serializers.ListField(
        child=serializers.EmailField(required=True),
        allow_empty=False,
        required=False,
    )
    remove_all = serializers.BooleanField(required=False, default=False)


class EnterpriseGroupLearnersRequestQuerySerializer(serializers.Serializer):
    """
    Serializer for the Enterprise Group Learners endpoint query filter
    """
    user_query = serializers.CharField(required=False, max_length=320)
    sort_by = serializers.ChoiceField(
        choices=[
            ('member_details', 'member_details'),
            ('status', 'status'),
            ('recent_action', 'recent_action')
        ],
        required=False,
    )
    pending_users_only = serializers.BooleanField(required=False, default=False)
    show_removed = serializers.BooleanField(required=False, default=False)
    is_reversed = serializers.BooleanField(required=False, default=False)
    page = serializers.IntegerField(required=False)
    learners = serializers.ListField(
        child=serializers.EmailField(required=True),
        required=False,
    )


class EnterpriseUserSerializer(serializers.Serializer):
    """
    Serializer for EnterpriseCustomerUser model with additions.
    """
    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'enterprise_customer_user'
            'pending_enterprise_customer_user',
            'role_assignments'
            'is_admin'
        )

    enterprise_customer_user = UserSerializer(source="user", required=False, default=None)
    pending_enterprise_customer_user = serializers.SerializerMethodField(required=False, default=None)
    role_assignments = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    def get_pending_enterprise_customer_user(self, obj):
        """
        Return either the pending user info
        """
        enterprise_customer_uuid = obj.enterprise_customer.uuid
        # if the obj has a user id, this means that it is a realized user, not pending
        if hasattr(obj, 'user_id'):
            return None
        return get_pending_enterprise_customer_users(obj.user_email, enterprise_customer_uuid)

    def get_is_admin(self, obj):
        """
        Make admin determination based on Enterprise role in SystemWideEnterpriseUserRoleAssignment
        """
        enterprise_customer_uuid = obj.enterprise_customer.uuid
        user_email = obj.user_email
        admin_instance = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            role__name=ENTERPRISE_ADMIN_ROLE,
            enterprise_customer_id=enterprise_customer_uuid,
            user__email=user_email
        )
        return admin_instance.exists()

    def get_role_assignments(self, obj):
        """
        Fetch user's role assignments
        """
        if hasattr(obj, 'user_id'):
            user_id = obj.user_id
            enterprise_customer_uuid = obj.enterprise_customer.uuid

            role_assignments = models.SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user_id=user_id
            ).select_related('role')
            role_assignments_by_ecu_id = [
                role_assignment.role.name for role_assignment in role_assignments if
                role_assignment.user_id == user_id and
                role_assignment.enterprise_customer_id == enterprise_customer_uuid
            ]
            return role_assignments_by_ecu_id
        else:
            return None


class EnterpriseCustomerMembersRequestQuerySerializer(serializers.Serializer):
    """
    Serializer for the Enterprise Customer Members endpoint query filter
    """
    user_query = serializers.CharField(required=False, max_length=250)
    sort_by = serializers.ChoiceField(
        choices=[
            ('name', 'name'),
            ('joined_org', 'joined_org'),
        ],
        required=False,
    )
    is_reversed = serializers.BooleanField(required=False, default=False)
    user_id = serializers.IntegerField(required=False)


class EnterpriseMembersSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerUser model with additions.
    """
    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'enterprise_customer_user',
            'enrollments',
        )

    enterprise_customer_user = serializers.SerializerMethodField()
    enrollments = serializers.SerializerMethodField()

    def get_enrollments(self, obj):
        """
        Fetch all of user's enterprise enrollments
        """
        if user := obj:
            user_id = user[0]
            enrollments = models.EnterpriseCourseEnrollment.objects.filter(
                enterprise_customer_user=user_id,
            )
            return len(enrollments)
        return 0

    def get_enterprise_customer_user(self, obj):
        """
        Return either the member's name and email if it's the case that the member is realized, otherwise just email
        """
        if user := obj:
            return {
                "user_id": user[0],
                "email": user[1],
                "joined_org": user[2].strftime("%b %d, %Y"),
                "name": user[3],
            }
        return None


class DefaultEnterpriseEnrollmentIntentionSerializer(serializers.ModelSerializer):
    """
    Serializer for the DefaultEnterpriseEnrollmentIntention model.
    """

    course_run_key = serializers.SerializerMethodField()
    is_course_run_enrollable = serializers.SerializerMethodField()
    course_run_normalized_metadata = serializers.SerializerMethodField()
    applicable_enterprise_catalog_uuids = serializers.SerializerMethodField()

    class Meta:
        model = models.DefaultEnterpriseEnrollmentIntention
        fields = (
            'uuid',
            'content_key',
            'enterprise_customer',
            'course_key',
            'course_run_key',
            'is_course_run_enrollable',
            'best_mode_for_course_run',
            'applicable_enterprise_catalog_uuids',
            'course_run_normalized_metadata',
            'created',
            'modified',
        )

    def get_course_run_key(self, obj):
        """
        Get the course run key for the enrollment intention
        """
        return obj.course_run_key

    def get_is_course_run_enrollable(self, obj):
        """
        Get the course run enrollable status for the enrollment intention
        """
        return obj.is_course_run_enrollable

    def get_course_run_normalized_metadata(self, obj):
        """
        Get the course run for the enrollment intention
        """
        return obj.course_run_normalized_metadata

    def get_applicable_enterprise_catalog_uuids(self, obj):
        return obj.applicable_enterprise_catalog_uuids

    def get_best_mode_for_course_run(self, obj):
        """
        Get the best course mode for the course run.
        """
        return obj.best_mode_for_course_run


class DefaultEnterpriseEnrollmentIntentionWithEnrollmentStateSerializer(DefaultEnterpriseEnrollmentIntentionSerializer):
    """
    Serializer for the DefaultEnterpriseEnrollmentIntention model with enrollment state.
    """
    has_existing_enrollment = serializers.SerializerMethodField()
    is_existing_enrollment_active = serializers.SerializerMethodField()
    is_existing_enrollment_audit = serializers.SerializerMethodField()

    class Meta(DefaultEnterpriseEnrollmentIntentionSerializer.Meta):
        fields = DefaultEnterpriseEnrollmentIntentionSerializer.Meta.fields + (
            'has_existing_enrollment',
            'is_existing_enrollment_active',
            'is_existing_enrollment_audit',
        )

    def get_has_existing_enrollment(self, obj):  # pylint: disable=unused-argument
        return bool(self.context.get('existing_enrollment', None))

    def get_is_existing_enrollment_active(self, obj):  # pylint: disable=unused-argument
        existing_enrollment = self.context.get('existing_enrollment', None)
        if not existing_enrollment:
            return None
        return existing_enrollment.is_active

    def get_is_existing_enrollment_audit(self, obj):  # pylint: disable=unused-argument
        existing_enrollment = self.context.get('existing_enrollment', None)
        if not existing_enrollment:
            return None
        return existing_enrollment.is_audit_enrollment


class DefaultEnterpriseEnrollmentIntentionLearnerStatusSerializer(serializers.Serializer):
    """
    Serializer for the DefaultEnterpriseEnrollmentIntentionLearnerStatus model.
    """

    lms_user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    enterprise_customer_uuid = serializers.UUIDField()
    enrollment_statuses = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()

    def needs_enrollment_counts(self):
        """
        Return the counts of needs_enrollment.
        """
        needs_enrollment = self.context.get('needs_enrollment', {})
        needs_enrollment_enrollable = needs_enrollment.get('enrollable', [])
        needs_enrollment_not_enrollable = needs_enrollment.get('not_enrollable', [])

        return {
            'enrollable': len(needs_enrollment_enrollable),
            'not_enrollable': len(needs_enrollment_not_enrollable),
        }

    def already_enrolled_count(self):
        """
        Return the count of already enrolled.
        """
        already_enrolled = self.context.get('already_enrolled', {})
        return len(already_enrolled)

    def total_default_enrollment_intention_count(self):
        """
        Return the total count of default enrollment intentions.
        """
        needs_enrollment_counts = self.needs_enrollment_counts()
        total_needs_enrollment_enrollable = needs_enrollment_counts['enrollable']
        total_needs_enrollment_not_enrollable = needs_enrollment_counts['not_enrollable']
        return total_needs_enrollment_enrollable + total_needs_enrollment_not_enrollable + self.already_enrolled_count()

    def serialize_intentions(self, default_enrollment_intentions):
        """
        Helper function to handle tuple unpacking and serialization.
        """
        serialized_data = []
        for intention_tuple in default_enrollment_intentions:
            intention, existing_enrollment = intention_tuple
            data = DefaultEnterpriseEnrollmentIntentionWithEnrollmentStateSerializer(
                intention,
                context={'existing_enrollment': existing_enrollment},
            ).data
            serialized_data.append(data)
        return serialized_data

    def get_enrollment_statuses(self, obj):  # pylint: disable=unused-argument
        """
        Return default enterprise enrollment intentions partitioned by
        the enrollment statuses for the learner.
        """
        needs_enrollment = self.context.get('needs_enrollment', {})
        needs_enrollment_enrollable = needs_enrollment.get('enrollable', [])
        needs_enrollment_not_enrollable = needs_enrollment.get('not_enrollable', [])
        already_enrolled = self.context.get('already_enrolled', {})

        needs_enrollment_enrollable_data = self.serialize_intentions(needs_enrollment_enrollable)
        needs_enrollment_not_enrollable_data = self.serialize_intentions(needs_enrollment_not_enrollable)
        already_enrolled_data = self.serialize_intentions(already_enrolled)

        return {
            'needs_enrollment': {
                'enrollable': needs_enrollment_enrollable_data,
                'not_enrollable': needs_enrollment_not_enrollable_data,
            },
            'already_enrolled': already_enrolled_data,
        }

    def get_metadata(self, obj):  # pylint: disable=unused-argument
        """
        Return the metadata for the default enterprise enrollment intention, including
        number of default enterprise enrollment intentions that need enrollment, are already
        enrolled by the learner.
        """
        return {
            'total_default_enterprise_enrollment_intentions': self.total_default_enrollment_intention_count(),
            'total_needs_enrollment': self.needs_enrollment_counts(),
            'total_already_enrolled': self.already_enrolled_count(),
        }
