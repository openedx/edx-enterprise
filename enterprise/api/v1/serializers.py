# -*- coding: utf-8 -*-
"""
Serializers for enterprise api version 1.
"""
from __future__ import absolute_import, unicode_literals

import copy

from rest_framework import serializers

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

from enterprise import models, utils
from enterprise.api.v1.mixins import EnterpriseCourseContextSerializerMixin


class ImmutableStateSerializer(serializers.Serializer):
    """
    Base serializer for any serializer that inhibits state changing requests.
    """

    def create(self, validated_data):
        """
        Do not perform any operations for state changing requests.
        """
        pass

    def update(self, instance, validated_data):
        """
        Do not perform any operations for state changing requests.
        """
        pass


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
            'enterprise_customer', 'logo'
        )


class EnterpriseCustomerEntitlementSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerEntitlement model.
    """

    class Meta:
        model = models.EnterpriseCustomerEntitlement
        fields = (
            'enterprise_customer', 'entitlement_id'
        )


class EnterpriseCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomer model.
    """

    class Meta:
        model = models.EnterpriseCustomer
        fields = (
            'uuid', 'name', 'catalog', 'active', 'site', 'enable_data_sharing_consent', 'enforce_data_sharing_consent',
            'branding_configuration', 'enterprise_customer_entitlements',
            'enable_audit_enrollment'
        )

    site = SiteSerializer()
    branding_configuration = EnterpriseCustomerBrandingConfigurationSerializer()
    enterprise_customer_entitlements = EnterpriseCustomerEntitlementSerializer(  # pylint: disable=invalid-name
        many=True,
    )


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
            raise serializers.ValidationError("User does not exist")

        try:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.get(user_id=user.pk)
        except models.EnterpriseCustomerUser.DoesNotExist:
            raise serializers.ValidationError("User has no EnterpriseCustomerUser")

        self.enterprise_customer_user = enterprise_customer_user
        return value

    def save(self):  # pylint: disable=arguments-differ
        """
        Save the model with the found EnterpriseCustomerUser.
        """
        course_id = self.validated_data['course_id']

        models.EnterpriseCourseEnrollment.objects.get_or_create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_id,
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
            'id', 'enterprise_customer', 'user_id', 'user', 'data_sharing_consent_records'
        )

    user = UserSerializer()
    enterprise_customer = EnterpriseCustomerSerializer()
    data_sharing_consent_records = serializers.SerializerMethodField()

    def get_data_sharing_consent_records(self, obj):
        """
        Return serialization of EnterpriseCustomerUser.data_sharing_consent_records property.

        Arguments:
            EnterpriseCustomerUser: The EnterpriseCustomerUser.

        Returns:
            list of dict: The serialized DataSharingConsent records associated with the EnterpriseCustomerUser.
        """
        return [record.serialize() for record in obj.data_sharing_consent_records]


class EnterpriseCustomerUserWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for writing to the EnterpriseCustomerUser model.
    """

    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'enterprise_customer', 'username'
        )

    username = serializers.CharField(max_length=30)
    user = None

    def validate_username(self, value):
        """
        Verify that the username has a matching user.
        """
        try:
            self.user = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")

        return value

    def save(self):  # pylint: disable=arguments-differ
        """
        Save the EnterpriseCustomerUser.
        """
        enterprise_customer = self.validated_data['enterprise_customer']

        ecu = models.EnterpriseCustomerUser(
            user_id=self.user.pk,
            enterprise_customer=enterprise_customer,
        )
        ecu.save()


class EnterpriseCustomerUserEntitlementSerializer(ImmutableStateSerializer):
    """
    Serializer for the entitlements of EnterpriseCustomerUser.

    This Serializer is for read only endpoint of enterprise learner's entitlements
    It will ignore any state changing requests like POST, PUT and PATCH.
    """

    entitlements = serializers.ListField(
        child=serializers.DictField()
    )

    user = UserSerializer(read_only=True)
    enterprise_customer = EnterpriseCustomerSerializer(read_only=True)


class CourseCatalogApiResponseReadOnlySerializer(ImmutableStateSerializer):
    """
    Serializer for enterprise customer catalog.
    """

    # pylint: disable=invalid-name
    id = serializers.IntegerField(read_only=True, help_text=_('Enterprise course catalog primary key.'))
    name = serializers.CharField(help_text=_('Catalog name'))
    query = serializers.CharField(help_text=_('Query to retrieve catalog contents'))
    courses_count = serializers.IntegerField(read_only=True, help_text=_('Number of courses contained in this catalog'))
    viewers = serializers.ListField(
        allow_null=True, allow_empty=True, required=False,
        help_text=_('Usernames of users with explicit access to view this catalog'),
        style={'base_template': 'input.html'},
        child=serializers.CharField(),
    )


class EnterpriseCatalogCoursesReadOnlySerializer(ResponsePaginationSerializer, EnterpriseCourseContextSerializerMixin):
    """
    Serializer for enterprise customer catalog courses.
    """
    pass


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
        enterprise_customer = self.context['enterprise_customer']
        updated_course_run['enrollment_url'] = enterprise_customer.get_course_run_enrollment_url(
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
        enterprise_customer = self.context['enterprise_customer']
        updated_program['enrollment_url'] = enterprise_customer.get_program_enrollment_url(updated_program['uuid'])
        for course in updated_program['courses']:
            for course_run in course['course_runs']:
                course_run['enrollment_url'] = enterprise_customer.get_course_run_enrollment_url(course_run['key'])
        return updated_program


class EnterpriseCustomerReportingConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerReportingConfiguration model.
    """

    class Meta:
        model = models.EnterpriseCustomerReportingConfiguration
        fields = (
            'enterprise_customer', 'active', 'delivery_method', 'email', 'frequency', 'day_of_month', 'day_of_week',
            'hour_of_day', 'initialization_vector', 'password'
        )

    enterprise_customer = EnterpriseCustomerSerializer()
