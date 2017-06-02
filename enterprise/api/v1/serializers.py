"""
Serializers for enterprise api version 1.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework import serializers

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

from enterprise import models, utils


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
            'enterprise_customer_users', 'branding_configuration', 'enterprise_customer_entitlements',
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
            'enterprise_customer_user', 'consent_granted', 'course_id'
        )


class EnterpriseCourseEnrollmentWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for writing to the EnterpriseCourseEnrollment model.
    """
    class Meta:
        model = models.EnterpriseCourseEnrollment
        fields = (
            'username', 'course_id', 'consent_granted'
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

    def save(self):
        """
        Save the model with the found EnterpriseCustomerUser.
        """
        course_id = self.validated_data['course_id']
        consent_granted = self.validated_data['consent_granted']

        models.EnterpriseCourseEnrollment.objects.get_or_create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_id,
            consent_granted=consent_granted,
        )


class UserDataSharingConsentAuditSerializer(serializers.ModelSerializer):
    """
    Serializer for UserDataSharingConsentAudit model.
    """
    class Meta:
        model = models.UserDataSharingConsentAudit
        fields = (
            'user', 'state', 'enabled'
        )


class EnterpriseCustomerUserReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerUser model.
    """
    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'id', 'enterprise_customer', 'user_id', 'user', 'data_sharing_consent'
        )

    user = UserSerializer()
    enterprise_customer = EnterpriseCustomerSerializer()
    data_sharing_consent = UserDataSharingConsentAuditSerializer(many=True)


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

    def save(self):
        """
        Save the EnterpriseCustomerUser.
        """
        enterprise_customer = self.validated_data['enterprise_customer']

        ecu = models.EnterpriseCustomerUser(
            user_id=self.user.pk,
            enterprise_customer=enterprise_customer,
        )
        ecu.save()


class EnterpriseCustomerUserEntitlementSerializer(serializers.Serializer):
    """
    Serializer for the entitlements of EnterpriseCustomerUser.

    This Serializer is for read only endpoint of enterprise learner's entitlements
    It will ignore any state changing requests like POST, PUT and PATCH.
    """
    entitlements = serializers.ListField(
        child=serializers.DictField()
    )

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
    user = UserSerializer(read_only=True)
    enterprise_customer = EnterpriseCustomerSerializer(read_only=True)
    data_sharing_consent = UserDataSharingConsentAuditSerializer(many=True, read_only=True)


class EnterpriseCourseCatalogReadOnlySerializer(serializers.Serializer):
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


class EnterpriseCatalogCoursesReadOnlySerializer(serializers.Serializer):
    """
    Serializer for enterprise customer catalog courses.
    """
    count = serializers.IntegerField(read_only=True, help_text=_('Total count of catalog courses.'))
    next = serializers.CharField(read_only=True, help_text=_("URL to fetch next page of courses."))
    previous = serializers.CharField(read_only=True, help_text=_("URL to fetch previous page of courses."))
    results = serializers.ListField(read_only=True, help_text=_("list of courses."))

    def update_enterprise_courses(self, request, catalog_id):
        """
        This method adds enterprise specific metadata for each course.

        We are adding following field in all the courses.
            tpa_hint: a string for identifying Identity Provider.
        """
        courses = []
        enterprise_customer = utils.get_enterprise_customer_for_user(request.user)

        global_context = {
            'tpa_hint': enterprise_customer and enterprise_customer.identity_provider,
            'enterprise_id': enterprise_customer and enterprise_customer.uuid,
            'catalog_id': catalog_id,
        }

        for course in self.data['results']:
            courses.append(
                self.update_course(course, catalog_id, enterprise_customer, global_context)
            )
        self.data['results'] = courses

    def update_course(self, course, catalog_id, enterprise_customer, global_context):
        """
        Update course metadata of the given course and return updated course.

        Arguments:
            course (dict): Course Metadata returned by course catalog API
            catalog_id (int): identifier of the catalog given course belongs to.
            enterprise_customer (EnterpriseCustomer): enterprise customer instance.
            global_context (dict): Global attributes that should be added to all the courses.

        Returns:
            (dict): Updated course metadata
        """
        # extract course runs from course metadata and
        # Replace course's course runs with the updated course runs
        course['course_runs'] = self.update_course_runs(
            course_runs=course.get('course_runs') or [],
            catalog_id=catalog_id,
            enterprise_customer=enterprise_customer,
        )

        # Update marketing urls in course metadata to include enterprise related info.
        if course.get('marketing_url'):
            course.update({
                "marketing_url": utils.update_query_parameters(
                    course.get('marketing_url'),
                    {
                        'tpa_hint': enterprise_customer and enterprise_customer.identity_provider,
                        'enterprise_id': enterprise_customer and enterprise_customer.uuid,
                        'catalog_id': catalog_id,
                    },
                ),
            })

        # now add global context to the course.
        course.update(global_context)
        return course

    def update_course_runs(self, course_runs, catalog_id, enterprise_customer):
        """
        Update Marketing urls in course metadata adn return updated course.

        Arguments:
            course_runs (list): List of course runs.
            catalog_id (int): Course catalog identifier.
            enterprise_customer (EnterpriseCustomer): enterprise customer instance.

        Returns:
            (dict): Dictionary containing updated course metadata.
        """
        updated_course_runs = []

        query_parameters = {
            'tpa_hint': enterprise_customer and enterprise_customer.identity_provider,
            'enterprise_id': enterprise_customer and enterprise_customer.uuid,
            'catalog_id': catalog_id,
        }

        for course_run in course_runs:
            track_selection_url = utils.get_course_track_selection_url(
                course_run=course_run,
                query_parameters=query_parameters,
            )

            enrollment_url = enterprise_customer.get_course_enrollment_url(course_run.get('key'))

            # Add/update track selection url in course run metadata.
            course_run.update({
                'track_selection_url': track_selection_url,
                'enrollment_url': enrollment_url
            })

            # Update marketing urls in course metadata to include enterprise related info.
            if course_run.get('marketing_url'):
                course_run.update({
                    "marketing_url": utils.update_query_parameters(
                        course_run.get('marketing_url'), query_parameters
                    ),
                })

            # Add updated course run to the list.
            updated_course_runs.append(course_run)

        return updated_course_runs

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
